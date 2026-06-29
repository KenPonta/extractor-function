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

# Saving to .ppt rasterizes vector icons into tiny PNGs the .pptx path never surfaces. Skip
# images whose smallest side is below this; real charts are far larger (0 disables the filter).
MIN_IMAGE_DIM = 150


#data model
def content_digest(blob: bytes) -> str:
    """Hash by decoded pixels so .ppt's per-slide re-encodings of one image collapse into one."""
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
    blocks: list = field(default_factory=list)  # ("text", str) | ("image", image_id)


@dataclass
class ImageRegistry:
    """Deduplicates images by content so identical pictures are described once."""
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


# --- helpers ---------------------------------------------------------------- #
def validate_file(file_path) -> tuple[Path, str]:
    """Return (path, kind) where kind is 'ppt' or 'pptx'; raise on anything else."""
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


def slide_text(slide: Slide) -> str:
    return " ".join(value for kind, value in slide.blocks if kind == "text")


def log_parse(kind, slides, registry, skipped_vector=0, skipped_small=0):
    placements = sum(k == "image" for s in slides for k, _ in s.blocks)
    logger.info("%s: %d slides, %d images, %d placements, %d vector + %d small skipped",
                kind, len(slides), len(registry.images), placements, skipped_vector, skipped_small)


# --- modern .pptx parsing (layout-aware, exact placement) ------------------- #
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


# --- legacy .ppt parsing (sharepoint-to-text) ------------------------------- #
def parse_ppt(path, registry) -> list:
    """Parse a legacy .ppt into text-only slides, registering images in deck order.

    .ppt keeps no readable picture-to-slide link and sharepoint2text spreads images
    round-robin, but image_index gives their true deck order. Images are placed later by
    place_legacy_images() (it needs the descriptions, which don't exist yet at parse time).
    """
    import sharepoint2text
    content = next(sharepoint2text.read_file(str(path)))  # one PptContent per file
    slides, pending = [], []                              # pending: (image_index, blob, ext)
    skipped_vector = skipped_small = 0
    for unit in content.iterate_units():                  # one PptUnit per slide, deck order
        blocks = []
        if unit.title:
            blocks.append(("text", unit.title.strip()))
        if (unit.text or "").strip():                     # body + other text, title excluded
            blocks.append(("text", unit.text.strip()))
        for image in unit.get_images():
            ext = ext_from_mime(image.get_content_type())
            w, h = image.width or 0, image.height or 0
            if ext is None:                               # WMF/EMF/etc. can't be rasterized
                skipped_vector += 1
            elif MIN_IMAGE_DIM and w and h and min(w, h) < MIN_IMAGE_DIM:
                skipped_small += 1                        # rasterized icon/badge/divider
            elif (blob := image.get_bytes().read()):
                pending.append((getattr(image, "image_index", 0), blob, ext))
        slides.append(Slide(unit.slide_number, blocks))
    for _, blob, ext in sorted(pending, key=lambda t: t[0]):  # register in deck order
        registry.register(blob, ext)
    log_parse("ppt", slides, registry, skipped_vector, skipped_small)
    return slides


# --- legacy .ppt image placement -------------------------------------------- #
# .ppt has no readable picture-to-slide link, so each figure is matched to its slide by the
# LLM (llm.match_slides), which builds a {image_id: slide} map. Any API/parse failure there
# propagates — there is no heuristic fallback.
def place_legacy_images(slides, images, model, client) -> None:
    """Place .ppt images inline on their LLM-inferred slide."""
    if not (slides and images):
        return
    mapping = llm.match_slides([(s.number, slide_text(s)) for s in slides],
                               [(im.image_id, im.description) for im in images],
                               model=model, client=client)
    by_number = {s.number: s for s in slides}
    for image in images:
        by_number[mapping[image.image_id]].blocks.append(("image", image.image_id))


# --- rendering -------------------------------------------------------------- #
def render_xml(slides, by_id, filename, data_type, index=1, approx_images=False) -> str:
    suffix = " (approximate slide)" if approx_images else ""  # .ppt placement is inferred
    slide_texts = []
    for slide in slides:
        parts = [f"Slide {slide.number}"]
        for kind, value in slide.blocks:
            if kind == "text":
                parts.append(value)
            else:
                desc = by_id[value].description or "(no description)"
                parts.append(f"[Image {value}{suffix}]\n{desc}")
        slide_texts.append("\n\n".join(parts))
    body = "\n\n".join(slide_texts)
    return (f'<documents>\n  <document index="{index}" filename="{xml_attr(filename)}"'
            f' data-type="{xml_attr(data_type)}">\n{body}\n  </document>\n</documents>\n')


# --- entry point ------------------------------------------------------------ #
def pptx_converter(file_path, output_dir=None, *, model=DEFAULT_MODEL,
                   max_workers=DEFAULT_MAX_WORKERS, prompt=IMAGE_PROMPT,
                   data_type=None, client=None) -> str:
    """Convert a .ppt/.pptx to placeholder XML (and write it to output_dir if given).

    .pptx places images on their exact slide; .ppt placement is inferred by the LLM in deck
    order. Pass client=... to inject a specific OpenAI/AzureOpenAI instance.
    """
    path, kind = validate_file(file_path)
    registry = ImageRegistry()
    slides = parse_pptx(path, registry) if kind == "pptx" else parse_ppt(path, registry)

    images = registry.images
    if images:
        client = client or llm.get_azure_openai_client()  # resolve once; describe + placement share it
        llm.describe_images(images, model=model, max_workers=max_workers, prompt=prompt, client=client)
        if kind == "ppt":                      # .pptx already placed images during parse
            place_legacy_images(slides, images, model, client)

    by_id = {image.image_id: image for image in images}
    xml = render_xml(slides, by_id, path.name, data_type or kind.upper(), approx_images=(kind == "ppt"))
    if output_dir is not None:
        out_path = Path(output_dir) / f"{path.stem}.xml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml, encoding="utf-8")
        logger.info("written to %s", out_path)
    return xml


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert .ppt/.pptx to placeholder XML.")
    parser.add_argument("file", type=Path, help=".ppt or .pptx file")
    parser.add_argument("-o", "--out", type=Path, default="output", help="output directory")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL)
    parser.add_argument("--data-type", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        pptx_converter(args.file, args.out, model=args.model, data_type=args.data_type)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
