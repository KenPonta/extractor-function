"""Clone of pptx_converter.py with the requested change:

parse_ppt() places each image on the slide its loop iteration came from (imitating the
.pptx / placeholder method), instead of deferring placement to the LLM (match_slides).
No LLM slide-matching is used here. Everything else is identical.
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


# --- .pptx parsing (unchanged) ---------------------------------------------- #
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


# --- .ppt parsing (CHANGED: place each image on its own unit) --------------- #
def parse_ppt(path, registry) -> list:
    """Place each image on the slide its loop iteration came from (no LLM placement)."""
    import sharepoint2text
    content = next(sharepoint2text.read_file(str(path)))
    slides = []
    skipped_vector = skipped_small = 0
    for unit in content.iterate_units():
        blocks = []
        if unit.title:
            blocks.append(("text", unit.title.strip()))
        if (unit.text or "").strip():
            blocks.append(("text", unit.text.strip()))
        for image in unit.get_images():
            ext = ext_from_mime(image.get_content_type())
            w, h = image.width or 0, image.height or 0
            if ext is None:
                skipped_vector += 1
            elif MIN_IMAGE_DIM and w and h and min(w, h) < MIN_IMAGE_DIM:
                skipped_small += 1
            elif (blob := image.get_bytes().read()):
                blocks.append(("image", registry.register(blob, ext)))  # <-- placed on THIS slide
        slides.append(Slide(unit.slide_number, blocks))
    log_parse("ppt", slides, registry, skipped_vector, skipped_small)
    return slides


# --- rendering (unchanged) -------------------------------------------------- #
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


def pptx_converter(file_path, output_dir=None, *, model=DEFAULT_MODEL,
                   max_workers=DEFAULT_MAX_WORKERS, prompt=IMAGE_PROMPT,
                   data_type=None, client=None, describe=True) -> str:
    path, kind = validate_file(file_path)
    registry = ImageRegistry()
    slides = parse_pptx(path, registry) if kind == "pptx" else parse_ppt(path, registry)

    images = registry.images
    if images and describe:
        client = llm.get_client(client)
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
    parser = argparse.ArgumentParser(description="Convert .ppt/.pptx to placeholder XML (loop-place variant).")
    parser.add_argument("file", type=Path, help=".ppt or .pptx file")
    parser.add_argument("-o", "--out", type=Path, default="output", help="output directory")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL)
    parser.add_argument("--data-type", default=None)
    parser.add_argument("--no-describe", action="store_true", help="skip the vision calls (placement only)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        pptx_converter(args.file, args.out, model=args.model, data_type=args.data_type,
                       describe=not args.no_describe)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
