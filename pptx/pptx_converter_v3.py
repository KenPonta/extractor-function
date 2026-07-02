"""pptx_converter_v3.py — .ppt image placement via Spire (exact), no LLM slide-matching.

Both formats now get EXACT image placement:
  .pptx -> python-pptx
  .ppt  -> Spire.Presentation (correct image->slide association) + sharepoint2text (text)

So there is no round-robin and no LLM placement step. The vision client is chosen by
--provider: 'openai' for this dev box (OPENAI_API_KEY in .env, model gpt-4.1) and 'azure'
for the real device (AzureOpenAI, deployment name). Default is azure so a production pull
runs unchanged; pass --provider openai here.
"""
import argparse
import hashlib
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import llm_ref as llm
from llm_ref import DEFAULT_MAX_WORKERS, DEFAULT_MODEL, IMAGE_PROMPT

logger = logging.getLogger(__name__)

MSO_FILL_PICTURE = 6
RASTER_MIME_EXT = {
    "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg",
    "image/gif": "gif", "image/webp": "webp", "image/bmp": "bmp",
}
MIN_IMAGE_DIM = 150


def content_digest(blob: bytes) -> str:
    try:
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(blob)) as im:
            buf = BytesIO()
            im.convert("RGB").save(buf, "PNG")
            return hashlib.sha1(buf.getvalue()).hexdigest()
    except Exception:
        return hashlib.sha1(blob).hexdigest()


@dataclass
class ImageRef:
    image_id: int
    blob: bytes
    ext: str
    description: str = ""


@dataclass
class Slide:
    number: int
    blocks: list = field(default_factory=list)


@dataclass
class ImageRegistry:
    by_digest: dict = field(default_factory=dict)

    def register(self, blob: bytes, ext: str) -> int:
        digest = content_digest(blob)
        ref = self.by_digest.get(digest)
        if ref is None:
            ref = self.by_digest[digest] = ImageRef(len(self.by_digest) + 1, blob, ext)
        return ref.image_id

    @property
    def images(self) -> list:
        return list(self.by_digest.values())


def validate_file(file_path) -> tuple[Path, str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    kind = {".ppt": "ppt", ".pptx": "pptx"}.get(path.suffix.lower())
    if kind is None:
        raise ValueError(f"unsupported file type: {path.name} (expected .ppt or .pptx)")
    return path, kind


def ext_from_mime(content_type: str) -> str | None:
    return RASTER_MIME_EXT.get((content_type or "").strip().lower())


def xml_attr(value) -> str:
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def log_parse(kind, slides, registry, skipped_vector=0, skipped_small=0):
    placements = sum(k == "image" for s in slides for k, _ in s.blocks)
    logger.info("%s: %d slides, %d images, %d placements, %d vector + %d small skipped",
                kind, len(slides), len(registry.images), placements, skipped_vector, skipped_small)


# --- .pptx parsing (python-pptx, exact) ------------------------------------- #
def shape_sort_key(shape) -> tuple[int, int]:
    top = shape.top if isinstance(shape.top, int) else 0
    left = shape.left if isinstance(shape.left, int) else 0
    return top, left


def image_from_shape(shape) -> tuple[bytes, str] | None:
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from pptx.oxml.ns import qn
    try:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            return shape.image.blob, shape.image.ext.lower()
        if int(shape.fill.type) == MSO_FILL_PICTURE:
            blip = shape._element.find(".//" + qn("a:blip"))
            if blip is not None:
                part = shape.part.related_part(blip.get(qn("r:embed")))
                return part.blob, part.partname.split(".")[-1].lower()
    except Exception:
        return None
    return None


def iter_pptx_blocks(shapes, registry):
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    for shape in sorted(shapes, key=shape_sort_key):
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_pptx_blocks(shape.shapes, registry)
            continue
        image = image_from_shape(shape)
        if image is not None:
            yield "image", registry.register(*image)
            continue
        if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
            yield "text", shape.text_frame.text.strip()
        if getattr(shape, "has_table", False):
            rows = [" | ".join(c.text.strip() for c in row.cells)
                    for row in shape.table.rows if any(c.text.strip() for c in row.cells)]
            if rows:
                yield "text", "\n".join(rows)


def parse_pptx(path, registry) -> list:
    from pptx import Presentation
    slides = [Slide(n, list(iter_pptx_blocks(slide.shapes, registry)))
              for n, slide in enumerate(Presentation(str(path)).slides, start=1)]
    log_parse("pptx", slides, registry)
    return slides


# --- .ppt parsing (Spire images, exact placement + sharepoint2text text) ---- #
def _spire_picture_shapes(shapes):
    """Yield picture shapes (SlidePicture or picture-fill autoshape), recursing groups."""
    from spire.presentation import FillFormatType
    for j in range(shapes.Count):
        shape = shapes[j]
        name = type(shape).__name__
        is_pic = name == "SlidePicture"
        if not is_pic:
            try:
                is_pic = shape.Fill.FillType == FillFormatType.Picture
            except Exception:
                is_pic = False
        if is_pic:
            yield shape
        if name == "GroupShape":
            yield from _spire_picture_shapes(shape.Shapes)


def _spire_image(shape):
    """Return (blob, content_type, width, height) for a Spire picture shape, else None."""
    picture_fill = getattr(shape, "PictureFill", None)       # SlidePicture
    if picture_fill is None:
        try:
            picture_fill = shape.Fill.PictureFill            # picture-fill autoshape
        except Exception:
            return None
    try:
        image_data = picture_fill.Picture.EmbedImage
        return (bytes(image_data.Image.ToArray()), image_data.ContentType,
                image_data.Width, image_data.Height)
    except Exception:
        return None


def parse_ppt(path, registry) -> list:
    """Text per slide from sharepoint2text; images per slide from Spire (exact placement)."""
    import sharepoint2text
    from spire.presentation import Presentation

    content = next(sharepoint2text.read_file(str(path)))
    text_by_slide = {}
    for unit in content.iterate_units():
        blocks = []
        if unit.title:
            blocks.append(("text", unit.title.strip()))
        if (unit.text or "").strip():
            blocks.append(("text", unit.text.strip()))
        text_by_slide[unit.slide_number] = blocks

    prs = Presentation()
    prs.LoadFromFile(str(path))
    slides = []
    skipped_vector = skipped_small = 0
    for i in range(prs.Slides.Count):
        blocks = list(text_by_slide.get(i + 1, []))          # text first, then images
        for shape in _spire_picture_shapes(prs.Slides[i].Shapes):
            info = _spire_image(shape)
            if info is None:
                continue
            blob, content_type, w, h = info
            ext = ext_from_mime(content_type)
            if ext is None:
                skipped_vector += 1
            elif MIN_IMAGE_DIM and w and h and min(w, h) < MIN_IMAGE_DIM:
                skipped_small += 1
            else:
                blocks.append(("image", registry.register(blob, ext)))
        slides.append(Slide(i + 1, blocks))
    prs.Dispose()
    log_parse("ppt", slides, registry, skipped_vector, skipped_small)
    return slides


# --- rendering (exact placement for both formats) --------------------------- #
def render_xml(slides, by_id, filename, data_type, index=1) -> str:
    slide_texts = []
    for slide in slides:
        parts = [f"Slide {slide.number}"]
        for kind, value in slide.blocks:
            if kind == "text":
                parts.append(value)
            else:
                desc = by_id[value].description or "(no description)"
                parts.append(f"[Image {value}]\n{desc}")
        slide_texts.append("\n\n".join(parts))
    body = "\n\n".join(slide_texts)
    return (f'<documents>\n  <document index="{index}" filename="{xml_attr(filename)}"'
            f' data-type="{xml_attr(data_type)}">\n{body}\n  </document>\n</documents>\n')


# --- entry point ------------------------------------------------------------ #
def pptx_converter(file_path, output_dir=None, *, model=DEFAULT_MODEL,
                   max_workers=DEFAULT_MAX_WORKERS, prompt=IMAGE_PROMPT,
                   data_type=None, client=None) -> str:
    path, kind = validate_file(file_path)
    registry = ImageRegistry()
    slides = parse_pptx(path, registry) if kind == "pptx" else parse_ppt(path, registry)

    images = registry.images
    if images:
        client = client or llm.get_azure_openai_client()   # default: real device (Azure)
        llm.describe_images(images, model=model, max_workers=max_workers, prompt=prompt, client=client)

    by_id = {image.image_id: image for image in images}
    xml = render_xml(slides, by_id, path.name, data_type or kind.upper())
    if output_dir is not None:
        out_path = Path(output_dir) / f"{path.stem}.xml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml, encoding="utf-8")
        logger.info("written to %s", out_path)
    return xml


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert .ppt/.pptx to placeholder XML (Spire placement).")
    parser.add_argument("file", type=Path, help=".ppt or .pptx file")
    parser.add_argument("-o", "--out", type=Path, default="output", help="output directory")
    parser.add_argument("--provider", choices=["azure", "openai"], default="azure",
                        help="azure (real device, default) or openai (dev box)")
    parser.add_argument("-m", "--model", default=None, help="override model / deployment name")
    parser.add_argument("--data-type", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.provider == "openai":
        from openai import OpenAI
        client = OpenAI()                       # reads OPENAI_API_KEY (llm_ref loaded .env)
        model = args.model or "gpt-4.1"
    else:
        client = None                           # -> AzureOpenAI inside pptx_converter
        model = args.model or DEFAULT_MODEL

    try:
        pptx_converter(args.file, args.out, model=model, client=client, data_type=args.data_type)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
