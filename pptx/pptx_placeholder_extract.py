#!/usr/bin/env python3
"""
pptx_placeholder_extract.py
===========================
Element-level PPTX extraction with image placeholders.

Instead of routing whole slides to a vision model, this keeps the text and the
images on separate, cheaper paths and stitches them back together:

  1. Native text  -> pulled directly from text frames / tables with python-pptx
                     (free, fast, lossless — no transcription drift).
  2. Each image   -> replaced in reading order with an ``[[IMAGE_n]]`` placeholder,
                     described ONCE by an OpenAI model, then spliced back into its slot.

The catch this script handles: in many decks the charts are pasted as a *picture
fill on a shape* rather than as a real ``PICTURE`` shape, so both ``shape_type ==
PICTURE`` and ``shape.image`` miss them. We pull the blob from the shape's fill
``<a:blip r:embed>`` relationship instead, so picture-fill charts are captured too.

Because only the images hit the model (and identical images are described once),
output tokens — the dominant cost — stay tiny: the model never re-transcribes text
it can already read on the slide.

Dependencies
------------
    pip install python-pptx pymupdf openai      # pymupdf only needed if the deck has SVGs

Usage
-----
    export OPENAI_API_KEY="sk-..."
    python pptx_placeholder_extract.py deck.pptx -o output/deck.md
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
MODEL = "gpt-4.1"
MAX_WORKERS = 8                         # unique images described concurrently
IMAGE_DETAIL = "high"
PICTURE_FILL = 6                        # MSO_FILL.PICTURE enum value
_EMBED_RE = re.compile(r'embed="(rId\d+)"')
_RASTER = {"png", "jpg", "jpeg", "gif", "webp"}

IMAGE_PROMPT = (
    "This image was taken from a presentation slide. If it is a chart, graph, table, "
    "diagram, or figure, extract its content as clean Markdown: title, axis labels and "
    "ranges, legend/series, and the data, trends, or relationships it conveys. If it is "
    "a logo, icon, or purely decorative background carrying no information, reply with "
    "exactly: (decorative — no data). Do not invent anything that is not visible."
)


# --------------------------------------------------------------------------- #
# Image extraction (handles both PICTURE shapes and picture-FILL shapes)
# --------------------------------------------------------------------------- #
def image_of(shape) -> tuple[bytes, str] | None:
    """Return (blob, ext) if the shape carries a picture, else None."""
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:        # true <p:pic> shape
        try:
            img = shape.image
            return img.blob, img.ext.lower()
        except Exception:
            pass
    try:                                                  # picture used as a shape FILL
        if int(shape.fill.type) == PICTURE_FILL:
            m = _EMBED_RE.search(shape._element.xml)
            if m:
                part = shape.part.related_part(m.group(1))
                ext = part.partname.split(".")[-1].lower()
                return part.blob, ext
    except Exception:
        pass
    return None


def _emu(v) -> int:
    return v if isinstance(v, int) else 0


# --------------------------------------------------------------------------- #
# Per-slide collection: ordered list of ("text", str) / ("image", (blob, ext))
# --------------------------------------------------------------------------- #
def collect_slide(slide) -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = []

    def walk(shapes):
        # Approximate visual reading order: top-to-bottom, then left-to-right.
        for s in sorted(shapes, key=lambda x: (_emu(getattr(x, "top", 0)),
                                               _emu(getattr(x, "left", 0)))):
            if s.shape_type == MSO_SHAPE_TYPE.GROUP:
                walk(s.shapes)
                continue
            pic = image_of(s)
            if pic is not None:
                items.append(("image", pic))
                continue
            if getattr(s, "has_text_frame", False):
                txt = s.text_frame.text.strip()
                if txt:
                    items.append(("text", txt))
            if getattr(s, "has_table", False):
                rows = []
                for row in s.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    items.append(("text", "\n".join(rows)))

    walk(slide.shapes)

    if slide.has_notes_slide:
        notes = slide.notes_slide.notes_text_frame.text.strip()
        if notes:
            items.append(("text", "**Speaker notes:** " + notes))
    return items


# --------------------------------------------------------------------------- #
# Vision: describe one image (converting SVG -> PNG first if needed)
# --------------------------------------------------------------------------- #
def _svg_to_png(svg_bytes: bytes) -> bytes:
    import fitz  # PyMuPDF
    doc = fitz.open(stream=svg_bytes, filetype="svg")
    return doc[0].get_pixmap().tobytes("png")


def _data_url(blob: bytes, ext: str) -> str:
    ext = ext.lower()
    if ext == "svg":
        blob, ext = _svg_to_png(blob), "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext if ext in _RASTER else "png")
    return f"data:image/{mime};base64,{base64.b64encode(blob).decode('utf-8')}"


def describe_image(client, blob: bytes, ext: str, model: str = MODEL) -> str:
    resp = client.responses.create(
        model=model,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": IMAGE_PROMPT},
            {"type": "input_image", "image_url": _data_url(blob, ext),
             "detail": IMAGE_DETAIL}]}],
    )
    return (resp.output_text or "").strip()


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def process_pptx(pptx_path: Path, out_path: Path | None = None,
                 model: str = MODEL) -> str:
    prs = Presentation(str(pptx_path))

    # 1) Collect every slide; register unique images (dedup identical blobs).
    registry: dict[str, dict] = {}        # sha1 -> {id, blob, ext, desc}
    by_id: dict[int, dict] = {}
    per_slide: list[tuple[int, list]] = []

    for i, slide in enumerate(prs.slides, start=1):
        rendered: list[tuple[str, object]] = []
        for kind, val in collect_slide(slide):
            if kind == "text":
                rendered.append(("text", val))
                continue
            blob, ext = val                                  # type: ignore[misc]
            h = hashlib.sha1(blob).hexdigest()
            if h not in registry:
                entry = {"id": len(registry) + 1, "blob": blob, "ext": ext, "desc": ""}
                registry[h] = entry
                by_id[entry["id"]] = entry
            rendered.append(("image", registry[h]["id"]))
        per_slide.append((i, rendered))

    n_img = len(registry)
    n_refs = sum(1 for _, items in per_slide for k, _ in items if k == "image")
    print(f"{len(per_slide)} slides: {n_img} unique images "
          f"({n_refs} placements{f', {n_refs - n_img} deduped' if n_refs > n_img else ''})",
          file=sys.stderr)

    # 2) Describe each unique image once, concurrently.
    if registry:
        if not os.environ.get("OPENAI_API_KEY"):
            sys.exit("OPENAI_API_KEY is not set, but the deck has images to describe.")
        from openai import OpenAI
        client = OpenAI()

        def run(entry: dict) -> None:
            try:
                entry["desc"] = describe_image(client, entry["blob"], entry["ext"], model)
            except Exception as exc:                         # keep going on per-image failures
                entry["desc"] = f"_[image description failed: {exc}]_"

        workers = min(MAX_WORKERS, n_img)
        print(f"  describing {n_img} images -> {model} ({workers} concurrent)", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(run, registry.values()))

    # 3) Stitch each slide: text inline, placeholders replaced by descriptions.
    blocks: list[str] = []
    for i, items in per_slide:
        parts: list[str] = []
        for kind, val in items:
            if kind == "text":
                parts.append(str(val))
            else:
                desc = by_id[val]["desc"] or "_[no description]_"
                parts.append(f"**[Image {val}]**\n\n{desc}")
        body = "\n\n".join(parts) if parts else "_[no content]_"
        blocks.append(f"## Slide {i}\n\n{body}")
    result = "\n\n---\n\n".join(blocks) + "\n"

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result, encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Extract a PPTX with native text + per-image placeholders described by a model."
    )
    ap.add_argument("pptx", help="path to the .pptx file")
    ap.add_argument("-o", "--out", help="output .md path (default: output/<pptx name>.md)")
    ap.add_argument("-m", "--model", default=MODEL, help=f"OpenAI model (default: {MODEL})")
    args = ap.parse_args()

    pptx_path = Path(args.pptx)
    if not pptx_path.exists():
        sys.exit(f"File not found: {pptx_path}")
    out_path = Path(args.out) if args.out else Path("output") / (pptx_path.stem + ".md")

    process_pptx(pptx_path, out_path, model=args.model)
    print(f"[written to {out_path}]", file=sys.stderr)


if __name__ == "__main__":
    main()
