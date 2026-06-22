#!/usr/bin/env python3
"""Extract a PowerPoint deck to Markdown using native text + image placeholders.

Strategy
--------
Text is read directly from the file with ``python-pptx`` (free, lossless). Every
embedded image is replaced, in reading order, with an ``[[IMAGE_n]]`` placeholder;
each unique image is described once by an OpenAI vision model and spliced back into
its slot. The model is therefore used *only* for images — never to re-transcribe
text it could already read — which keeps output (the dominant cost) small.

Images are read straight out of the ``.pptx`` package (a ZIP of OOXML parts). This
catches both true picture shapes and pictures used as a shape *fill* (how many decks
store charts), neither of which requires rendering the slide.

Public API
----------
    from placeholder_extractor import PlaceholderExtractor
    md = PlaceholderExtractor().extract(Path("deck.pptx"))

Dependencies
------------
    pip install python-pptx pymupdf openai      # pymupdf only used when a deck has SVGs

Environment
-----------
    OPENAI_API_KEY   required only if the deck contains images
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

__all__ = ["PlaceholderExtractor", "ExtractorConfig"]

logger = logging.getLogger(__name__)

# OOXML/enum constants
_MSO_FILL_PICTURE = 6                       # MSO_FILL.PICTURE: a shape filled with an image
_RASTER_EXT = {"png", "jpg", "jpeg", "gif", "webp"}   # formats the vision API accepts directly

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
@dataclass(frozen=True)
class ExtractorConfig:
    """Tunable settings for an extraction run."""

    model: str = "gpt-4.1"          # any vision-capable OpenAI model
    image_detail: str = "high"      # "low" | "high" | "auto" — "high" reads dense charts better
    max_workers: int = 8            # images described concurrently
    prompt: str = _IMAGE_PROMPT


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TextBlock:
    """A run of native text pulled from the slide."""

    text: str


@dataclass(frozen=True)
class ImageBlock:
    """A reference to a deduplicated image, resolved to a description after the model runs."""

    image_id: int


@dataclass
class ImageRef:
    """One unique image and the description the model produced for it."""

    image_id: int
    blob: bytes
    ext: str
    description: str = ""


@dataclass
class Slide:
    """An ordered list of text/image blocks for a single slide."""

    number: int
    blocks: list[TextBlock | ImageBlock] = field(default_factory=list)


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
    """Yield TextBlock/ImageBlock for each shape in reading order, recursing groups.

    ``register`` deduplicates an image and returns its stable ``image_id``.
    """
    for shape in sorted(shapes, key=_sort_key):
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_blocks(shape.shapes, register)
            continue

        image = _image_from_shape(shape)
        if image is not None:
            yield ImageBlock(register(*image))
            continue

        if getattr(shape, "has_text_frame", False):
            text = shape.text_frame.text.strip()
            if text:
                yield TextBlock(text)

        if getattr(shape, "has_table", False):
            rows = [" | ".join(c.text.strip() for c in row.cells)
                    for row in shape.table.rows
                    if any(c.text.strip() for c in row.cells)]
            if rows:
                yield TextBlock("\n".join(rows))


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
        slides, images = self._parse(pptx_path)
        if images:
            self._describe_all(images)
        return self._render(slides, {img.image_id: img for img in images})

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
        placements = sum(isinstance(b, ImageBlock) for s in slides for b in s.blocks)
        logger.info("%d slides, %d unique images (%d placements)",
                    len(slides), len(images), placements)
        return slides, images

    # -- 2. describe: one model call per unique image, concurrently --------- #
    def _describe_all(self, images: list[ImageRef]) -> None:
        client = self._client()
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
                     "detail": self.config.image_detail}]}],
            )
            image.description = (response.output_text or "").strip()
        except Exception as exc:                            # isolate per-image failures
            logger.warning("image %d failed: %s", image.image_id, exc)
            image.description = f"_[image description failed: {exc}]_"

    # -- 3. render: stitch text and resolved image descriptions ------------- #
    @staticmethod
    def _render(slides: list[Slide], by_id: dict[int, ImageRef]) -> str:
        sections = []
        for slide in slides:
            parts = []
            for block in slide.blocks:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
                else:
                    desc = by_id[block.image_id].description or "_[no description]_"
                    parts.append(f"**[Image {block.image_id}]**\n\n{desc}")
            body = "\n\n".join(parts) if parts else "_[no content]_"
            sections.append(f"## Slide {slide.number}\n\n{body}")
        return "\n\n---\n\n".join(sections) + "\n"

    @staticmethod
    def _client():
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set, but the deck has images to describe.")
        from openai import OpenAI                           # lazy import keeps text-only runs light
        return OpenAI()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pptx", type=Path, help="path to the .pptx file")
    parser.add_argument("-o", "--out", type=Path, help="output .md path (default: output/<name>.md)")
    parser.add_argument("-m", "--model", default=ExtractorConfig.model, help="OpenAI model")
    parser.add_argument("--detail", default=ExtractorConfig.image_detail,
                        choices=["low", "high", "auto"], help="image detail level")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)    # mute per-request HTTP noise
    if not args.pptx.exists():
        parser.error(f"file not found: {args.pptx}")

    out_path = args.out or Path("output") / f"{args.pptx.stem}.md"
    config = ExtractorConfig(model=args.model, image_detail=args.detail)
    markdown = PlaceholderExtractor(config).extract(args.pptx)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    logger.info("written to %s", out_path)


if __name__ == "__main__":
    main()
