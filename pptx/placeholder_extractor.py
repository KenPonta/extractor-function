from __future__ import annotations

import argparse
import base64
import hashlib
import logging
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

__all__ = ["PlaceholderExtractor", "ExtractorConfig", "pptx_to_xml", "pptx_to_markdown"]

logger = logging.getLogger(__name__)

# OOXML/enum constants
_MSO_FILL_PICTURE = 6                       # MSO_FILL.PICTURE: a shape filled with an image
_RASTER_EXT = {"png", "jpg", "jpeg", "gif", "webp"}   # formats the vision API accepts directly
_IMAGE_DETAIL = "high"                      # vision detail level; "high" reads dense charts best

_IMAGE_PROMPT = (
    "This image was taken from a presentation slide. If it is a chart, graph, table, "
    "diagram, or figure, extract its content as clean Markdown: title, axis labels and "
    "ranges, legend/series, and the data, trends, or relationships it conveys. If it is a "
    "logo, icon, or purely decorative background carrying no information, reply with exactly: "
    "(decorative — no data). Do not invent anything not visible. "
    "Output raw Markdown only; do not wrap your answer in a code fence."
)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
class ExtractorConfig:
    """Tunable settings for an extraction run (defaults live as class attributes)."""

    model = "gpt-4.1"               # any vision-capable OpenAI model
    max_workers = 8                 # images described concurrently
    prompt = _IMAGE_PROMPT

    # __init__ defaults reuse the class attributes above, so there is no duplication
    # and main() can still read e.g. ExtractorConfig.model.
    def __init__(self, model=model, max_workers=max_workers, prompt=prompt):
        self.model = model
        self.max_workers = max_workers
        self.prompt = prompt


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
# A slide's content is a list of (kind, value) tuples:
#   ("text",  str)  -> a run of native text
#   ("image", int)  -> a placeholder pointing at a unique image by its id
class ImageRef:
    """One unique image and the description the model produced for it."""

    def __init__(self, image_id: int, blob: bytes, ext: str, description: str = ""):
        self.image_id = image_id
        self.blob = blob
        self.ext = ext
        self.description = description


class Slide:
    """An ordered list of text/image blocks for a single slide."""

    def __init__(self, number: int, blocks: list | None = None):
        self.number = number
        # `blocks or []` would be wrong if an empty list were passed intentionally,
        # so use an explicit None check to give each Slide its own fresh list.
        self.blocks = blocks if blocks is not None else []


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #
def _validate_pptx(path) -> Path:
    """Return `path` as a Path if it is a real PowerPoint (.pptx), else raise.

    A .pptx is a ZIP of OOXML parts. We confirm three things, cheap to strict:
      1. the file exists,
      2. it has a .pptx extension,
      3. it is a valid ZIP that contains ``ppt/presentation.xml`` — the part that
         makes it a *presentation* (a .docx/.xlsx is also an OOXML ZIP but lacks it,
         and a non-Office file renamed to .pptx is not a ZIP at all).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if path.suffix.lower() != ".pptx":
        raise ValueError(f"expected a .pptx file, got: {path.name}")
    if not zipfile.is_zipfile(path):
        raise ValueError(f"not a valid .pptx (not an OOXML/ZIP package): {path.name}")
    with zipfile.ZipFile(path) as archive:
        if "ppt/presentation.xml" not in archive.namelist():
            raise ValueError(
                f"file is a ZIP but not a PowerPoint presentation "
                f"(missing ppt/presentation.xml): {path.name}")
    return path


def _xml_attr(value) -> str:
    """Escape a value for safe use inside an XML attribute (filename, data-type)."""
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


# --------------------------------------------------------------------------- #
# Image extraction — reads bytes from the .pptx package, no rendering
# --------------------------------------------------------------------------- #
def _image_from_shape(shape) -> tuple[bytes, str] | None:
    """Return ``(blob, ext)`` if the shape carries a picture, else ``None``.

    Handles two cases: a true ``PICTURE`` shape, and a picture used as a shape
    *fill* (common for charts) which the standard ``shape.image`` API misses.
    """
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        try:
            image = shape.image
            return image.blob, image.ext.lower()
        except Exception:                                   # corrupt/linked picture
            return None

    try:
        if int(shape.fill.type) == _MSO_FILL_PICTURE:
            blip = shape._element.find(".//" + qn("a:blip"))
            if blip is not None:
                rid = blip.get(qn("r:embed"))
                part = shape.part.related_part(rid)
                return part.blob, part.partname.split(".")[-1].lower()
    except Exception:                                       # no fill / unreadable relationship
        return None
    return None


def _sort_key(shape) -> tuple[int, int]:
    """Approximate visual reading order: top-to-bottom, then left-to-right."""
    top = shape.top if isinstance(shape.top, int) else 0
    left = shape.left if isinstance(shape.left, int) else 0
    return top, left


def _iter_blocks(shapes, register):
    """Yield ("text", str) / ("image", id) tuples per shape in reading order, recursing groups.

    ``register`` deduplicates an image and returns its stable ``image_id``.
    """
    for shape in sorted(shapes, key=_sort_key):
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_blocks(shape.shapes, register)
            continue

        image = _image_from_shape(shape)
        if image is not None:
            yield ("image", register(*image))
            continue

        if getattr(shape, "has_text_frame", False):
            text = shape.text_frame.text.strip()
            if text:
                yield ("text", text)

        if getattr(shape, "has_table", False):
            rows = [" | ".join(c.text.strip() for c in row.cells)
                    for row in shape.table.rows
                    if any(c.text.strip() for c in row.cells)]
            if rows:
                yield ("text", "\n".join(rows))


# --------------------------------------------------------------------------- #
# Image -> data URL (vision APIs accept raster only; SVG is rasterized first)
# --------------------------------------------------------------------------- #
def _svg_to_png(svg_bytes: bytes) -> bytes:
    import fitz  # PyMuPDF — imported lazily so text-only / SVG-free decks need no dependency
    return fitz.open(stream=svg_bytes, filetype="svg")[0].get_pixmap().tobytes("png")


def _data_url(blob: bytes, ext: str) -> str:
    if ext == "svg":
        blob, ext = _svg_to_png(blob), "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext if ext in _RASTER_EXT else "png")
    return f"data:image/{mime};base64,{base64.b64encode(blob).decode('ascii')}"


# --------------------------------------------------------------------------- #
# Extractor
# --------------------------------------------------------------------------- #
class PlaceholderExtractor:
    """Convert a ``.pptx`` to Markdown: native text inline, images described by a model."""

    def __init__(self, config: ExtractorConfig | None = None):
        self.config = config or ExtractorConfig()

    def extract(self, pptx_path: Path) -> str:
        """Return the full deck as Markdown."""
        slides, by_id = self._run(pptx_path)
        return self._render(slides, by_id)

    def extract_xml(self, pptx_path: Path, data_type: str = "PPTX") -> str:
        """Return the full deck as XML in the <documents>/<document> template."""
        slides, by_id = self._run(pptx_path)
        return self._render_xml(slides, by_id, Path(pptx_path).name, data_type=data_type)

    def _run(self, pptx_path: Path) -> tuple[list[Slide], dict[int, ImageRef]]:
        """Parse the deck, then describe its images. Returns (slides, {image_id: ImageRef})."""
        pptx_path = _validate_pptx(pptx_path)           # gate: must be a real .pptx
        slides, images = self._parse(pptx_path)
        if images:
            self._describe_all(images)
        return slides, {img.image_id: img for img in images}

    # -- 1. parse: collect slides and the set of unique images -------------- #
    def _parse(self, pptx_path: Path) -> tuple[list[Slide], list[ImageRef]]:
        registry: dict[str, ImageRef] = {}

        def register(blob: bytes, ext: str) -> int:
            digest = hashlib.sha1(blob).hexdigest()         # dedup identical images
            ref = registry.get(digest)
            if ref is None:
                ref = ImageRef(len(registry) + 1, blob, ext)
                registry[digest] = ref
            return ref.image_id

        presentation = Presentation(str(pptx_path))
        slides = [
            Slide(number, list(_iter_blocks(slide.shapes, register)))
            for number, slide in enumerate(presentation.slides, start=1)
        ]
        images = list(registry.values())
        placements = sum(kind == "image" for s in slides for kind, _ in s.blocks)
        logger.info("%d slides, %d unique images (%d placements)",
                    len(slides), len(images), placements)
        return slides, images

    # -- 2. describe: one model call per unique image, concurrently --------- #
    def _describe_all(self, images: list[ImageRef]) -> None:
        from openai import OpenAI            # lazy import keeps text-only runs light
        client = OpenAI()                    # reads OPENAI_API_KEY from the environment
        workers = min(self.config.max_workers, len(images))
        logger.info("describing %d images via %s (%d concurrent)",
                    len(images), self.config.model, workers)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pool.map(lambda img: self._describe(client, img), images)

    def _describe(self, client, image: ImageRef) -> None:
        try:
            response = client.responses.create(
                model=self.config.model,
                input=[{"role": "user", "content": [
                    {"type": "input_text", "text": self.config.prompt},
                    {"type": "input_image",
                     "image_url": _data_url(image.blob, image.ext),
                     "detail": _IMAGE_DETAIL}]}],
            )
            image.description = (response.output_text or "").strip()
        except Exception as exc:                            # isolate per-image failures
            logger.warning("image %d failed: %s", image.image_id, exc)
            image.description = f"_[image description failed: {exc}]_"

    # -- 3. render: stitch text and resolved image descriptions ------------- #
    def _render(self, slides: list[Slide], by_id: dict[int, ImageRef]) -> str:
        sections = []
        for slide in slides:
            parts = []
            for kind, value in slide.blocks:
                if kind == "text":
                    parts.append(value)
                else:
                    desc = by_id[value].description or "_[no description]_"
                    parts.append(f"**[Image {value}]**\n\n{desc}")
            body = "\n\n".join(parts) if parts else "_[no content]_"
            sections.append(f"## Slide {slide.number}\n\n{body}")
        return "\n\n---\n\n".join(sections) + "\n"

    def _render_xml(self, slides: list[Slide], by_id: dict[int, ImageRef],
                    filename: str, index: int = 1, data_type: str = "PPTX") -> str:
        """Wrap the extracted content in the <documents>/<document> template.

        Attributes (filename, data-type) are escaped; the body is the slide content
        from the Markdown renderer, kept raw to match the reference template.
        """
        body = self._render(slides, by_id)                  # slide text + image descriptions
        return (
            "<documents>\n"
            f'  <document index="{index}" filename="{_xml_attr(filename)}"'
            f' data-type="{_xml_attr(data_type)}">\n'
            f"{body}"
            "  </document>\n"
            "</documents>\n"
        )


# --------------------------------------------------------------------------- #
# Convenience functions — import these from another module
# --------------------------------------------------------------------------- #
def pptx_to_xml(file_path, output_dir, config: ExtractorConfig | None = None,
                data_type: str = "PPTX") -> Path:
    """Extract `file_path` to XML and write `<output_dir>/<name>.xml`. Returns the output path."""
    src = Path(file_path)
    text = PlaceholderExtractor(config).extract_xml(src, data_type=data_type)
    return _write(text, output_dir, src.stem, ".xml")


def pptx_to_markdown(file_path, output_dir, config: ExtractorConfig | None = None) -> Path:
    """Extract `file_path` to Markdown and write `<output_dir>/<name>.md`. Returns the output path."""
    src = Path(file_path)
    text = PlaceholderExtractor(config).extract(src)
    return _write(text, output_dir, src.stem, ".md")


def _write(text: str, output_dir, stem: str, ext: str) -> Path:
    out_path = Path(output_dir) / f"{stem}{ext}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pptx", type=Path, help="path to the .pptx file")
    parser.add_argument("-o", "--out", type=Path,
                        help="output path (default: output/<name>.<format>)")
    parser.add_argument("-m", "--model", default=ExtractorConfig.model, help="OpenAI model")
    parser.add_argument("--format", default="xml", choices=["xml", "md"],
                        help="output format (default: xml)")
    parser.add_argument("--data-type", default="PPTX",
                        help="value for the <document data-type> attribute (default: PPTX)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)    # mute per-request HTTP noise

    out_path = args.out or Path("output") / f"{args.pptx.stem}.{args.format}"
    config = ExtractorConfig(model=args.model)
    extractor = PlaceholderExtractor(config)
    try:
        text = (extractor.extract_xml(args.pptx, data_type=args.data_type)
                if args.format == "xml" else extractor.extract(args.pptx))
    except (FileNotFoundError, ValueError) as exc:      # bad/missing/non-pptx input
        parser.error(str(exc))                          # clean "error: …", no traceback

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    logger.info("written to %s", out_path)


if __name__ == "__main__":
    main()
