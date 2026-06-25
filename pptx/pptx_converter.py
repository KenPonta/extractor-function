import argparse
import base64
import hashlib
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4.1"
DEFAULT_MAX_WORKERS = 8
IMAGE_DETAIL = "high"
MSO_FILL_PICTURE = 6 

RASTER_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

# A legacy PptImage reports a MIME type; map the rasterizable ones to an extension.
RASTER_MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
}

IMAGE_PROMPT = (
    "This image was taken from a presentation slide. If it is a chart, graph, table, "
    "diagram, or figure, describe its content as plain text: title, axis labels and "
    "ranges, legend/series, and the data, trends, or relationships it conveys. If it is "
    "a logo, icon, or purely decorative background with no information, reply with exactly: "
    "(decorative, no data). Do not invent anything not visible, and do not wrap your reply "
    "in a code fence."
)


# --- data model ------------------------------------------------------------- #
@dataclass
class ImageRef:
    image_id: int
    blob: bytes
    ext: str
    description: str = ""


@dataclass
class Slide:
    number: int
    blocks: list = field(default_factory=list)  # list of ("text", str) | ("image", image_id)


@dataclass
class ImageRegistry:
    """Deduplicates images by content so identical pictures are described once."""

    by_digest: dict = field(default_factory=dict)

    def register(self, blob: bytes, ext: str) -> int:
        digest = hashlib.sha1(blob).hexdigest()
        ref = self.by_digest.get(digest)
        if ref is None:
            ref = ImageRef(len(self.by_digest) + 1, blob, ext)
            self.by_digest[digest] = ref
        return ref.image_id

    @property
    def images(self) -> list:
        return list(self.by_digest.values())


# --- validation & small helpers --------------------------------------------- #
def validate_file(file_path) -> tuple[Path, str]:
    """Return (path, kind) where kind is 'pptx' or 'ppt'; raise on anything else."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        return path, "pptx"
    if suffix == ".ppt":
        return path, "ppt"
    raise ValueError(f"unsupported file type: {path.name} (expected .ppt or .pptx)")


def ext_from_mime(content_type: str) -> str | None:
    """Map a legacy image MIME type to a raster extension, or None if unsupported."""
    return RASTER_MIME_EXT.get((content_type or "").strip().lower())


def xml_attr(value) -> str:
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def svg_to_png(svg_bytes: bytes) -> bytes:
    import fitz
    return fitz.open(stream=svg_bytes, filetype="svg")[0].get_pixmap().tobytes("png")


def data_url(blob: bytes, ext: str) -> str:
    if ext == "svg":
        blob, ext = svg_to_png(blob), "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext if ext in RASTER_EXT else "png")
    return f"data:image/{mime};base64,{base64.b64encode(blob).decode('ascii')}"


# --- modern .pptx parsing (python-pptx, layout-aware) ----------------------- #
def shape_sort_key(shape) -> tuple[int, int]:
    top = shape.top if isinstance(shape.top, int) else 0
    left = shape.left if isinstance(shape.left, int) else 0
    return top, left


def image_from_shape(shape) -> tuple[bytes, str] | None:
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from pptx.oxml.ns import qn

    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        try:
            image = shape.image
            return image.blob, image.ext.lower()
        except Exception:
            return None
    try:
        if int(shape.fill.type) == MSO_FILL_PICTURE:
            blip = shape._element.find(".//" + qn("a:blip"))
            if blip is not None:
                rid = blip.get(qn("r:embed"))
                part = shape.part.related_part(rid)
                return part.blob, part.partname.split(".")[-1].lower()
    except Exception:
        return None
    return None


def iter_pptx_blocks(shapes, registry: ImageRegistry):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for shape in sorted(shapes, key=shape_sort_key):
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_pptx_blocks(shape.shapes, registry)
            continue

        image = image_from_shape(shape)
        if image is not None:
            yield "image", registry.register(*image)
            continue

        if getattr(shape, "has_text_frame", False):
            text = shape.text_frame.text.strip()
            if text:
                yield "text", text

        if getattr(shape, "has_table", False):
            rows = [" | ".join(cell.text.strip() for cell in row.cells)
                    for row in shape.table.rows
                    if any(cell.text.strip() for cell in row.cells)]
            if rows:
                yield "text", "\n".join(rows)


def parse_pptx(path: Path, registry: ImageRegistry) -> list:
    from pptx import Presentation

    presentation = Presentation(str(path))
    slides = [Slide(number, list(iter_pptx_blocks(slide.shapes, registry)))
              for number, slide in enumerate(presentation.slides, start=1)]
    log_parse("pptx", slides, registry)
    return slides


# --- legacy .ppt parsing (sharepoint-to-text) ------------------------------- #
def parse_ppt(path: Path, registry: ImageRegistry) -> list:
    import sharepoint2text

    content = next(sharepoint2text.read_file(str(path)))  # one PptContent per file
    slides = []
    skipped_vector = 0
    for unit in content.iterate_units():                  # PptUnit per slide, deck order
        blocks = []
        if unit.title:
            blocks.append(("text", unit.title.strip()))
        text = (unit.text or "").strip()                  # body + other text, title excluded
        if text:
            blocks.append(("text", text))
        for image in unit.get_images():                   # PptImage
            ext = ext_from_mime(image.get_content_type())
            if ext is None:
                skipped_vector += 1                        # WMF/EMF/etc. cannot be rasterized
                continue
            blob = image.get_bytes().read()
            if blob:
                blocks.append(("image", registry.register(blob, ext)))
        slides.append(Slide(unit.slide_number, blocks))
    log_parse("ppt", slides, registry, skipped_vector)
    return slides


def log_parse(kind: str, slides: list, registry: ImageRegistry, skipped_vector: int = 0):
    placements = sum(k == "image" for s in slides for k, _ in s.blocks)
    logger.info("%s: %d slides, %d unique images (%d placements), %d vector images skipped",
                kind, len(slides), len(registry.images), placements, skipped_vector)


# --- vision image description ----------------------------------------------- #
def describe_images(images: list, model: str, max_workers: int, prompt: str):
    """Fill each ImageRef.description in place via a vision model (concurrent)."""
    from openai import OpenAI

    client = OpenAI()
    workers = min(max_workers, len(images))
    logger.info("describing %d images via %s (%d concurrent)", len(images), model, workers)

    def describe(image: ImageRef):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": data_url(image.blob, image.ext), "detail": IMAGE_DETAIL}},
                ]}],
            )
            image.description = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("image %d failed: %s", image.image_id, exc)
            image.description = f"[image description failed: {exc}]"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        pool.map(describe, images)


# --- rendering -------------------------------------------------------------- #
def render_xml(slides: list, by_id: dict, filename: str, data_type: str, index: int = 1) -> str:
    slide_texts = []
    for slide in slides:
        parts = [f"Slide {slide.number}"]
        for kind, value in slide.blocks:
            if kind == "text":
                parts.append(value)
            else:
                description = by_id[value].description or "(no description)"
                parts.append(f"[Image {value}]\n{description}")
        slide_texts.append("\n\n".join(parts))
    body = "\n\n".join(slide_texts)
    return (
        "<documents>\n"
        f'  <document index="{index}" filename="{xml_attr(filename)}"'
        f' data-type="{xml_attr(data_type)}">\n'
        f"{body}\n"
        "  </document>\n"
        "</documents>\n"
    )


# --- public entry point ----------------------------------------------------- #
def pptx_converter(file_path, output_dir=None, *, model: str = DEFAULT_MODEL,
                   max_workers: int = DEFAULT_MAX_WORKERS, prompt: str = IMAGE_PROMPT,
                   data_type: str | None = None) -> str:
    """Convert a .ppt or .pptx file to placeholder XML and return it as a string.

    Args:
        file_path: path to a .ppt or .pptx file.
        output_dir: if given, the XML is also written to ``<output_dir>/<stem>.xml``.
        model: vision model used to describe images.
        max_workers: max concurrent image-description requests.
        prompt: instruction sent to the vision model for each image.
        data_type: value for the document's ``data-type`` attribute
            (defaults to "PPTX" or "PPT" based on the detected format).

    Returns:
        The rendered <documents> XML string.
    """
    path, kind = validate_file(file_path)
    registry = ImageRegistry()
    slides = parse_pptx(path, registry) if kind == "pptx" else parse_ppt(path, registry)

    images = registry.images
    if images:
        describe_images(images, model=model, max_workers=max_workers, prompt=prompt)
    by_id = {image.image_id: image for image in images}

    xml = render_xml(slides, by_id, path.name, data_type=data_type or kind.upper())
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
