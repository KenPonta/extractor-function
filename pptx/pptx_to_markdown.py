#!/usr/bin/env python3
"""
pptx_to_markdown.py
===================
Convert a PowerPoint deck to Markdown with one of three strategies. Each strategy
extracts what it can natively and sends only what needs a model to OpenAI.

Methods
-------
placeholder : Native text is pulled directly; every image (including charts pasted
              as a picture *fill* on a shape) is replaced with an ``[[IMAGE_n]]``
              placeholder, described once by the model, and spliced back in place.
              Cheapest when the slides' visuals are real embedded images.

routed      : Each slide is routed by a render-free heuristic. Text-heavy slides are
              extracted natively; visual slides are rendered to a single-page PDF and
              read by the model (calls run concurrently). Best on text-heavy decks.

whole       : The whole deck is rendered to one PDF and transcribed in a single call.
              Simplest; best on visual-heavy decks. (Note: one response must hold the
              entire transcript, so very long decks can hit the model's output limit.)

Dependencies
------------
    pip install python-pptx pymupdf openai
    # LibreOffice ('soffice') is required for the `routed` and `whole` methods:
    #   macOS:   brew install --cask libreoffice
    #   Debian:  sudo apt-get install libreoffice

Usage
-----
    export OPENAI_API_KEY="sk-..."
    python pptx_to_markdown.py deck.pptx --method placeholder
    python pptx_to_markdown.py deck.pptx --method routed -o out.md
    python pptx_to_markdown.py deck.pptx --method whole  -m gpt-4.1
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
MODEL = "gpt-4.1"          # any vision-capable OpenAI model
MAX_WORKERS = 8            # concurrent model calls (routed / placeholder)
IMAGE_DETAIL = "high"      # "low" | "high" | "auto"

# routed: render-free routing thresholds (tune to your decks)
WORD_CAP = 60
VISION_PIC_FRACTION = 0.45
VISION_TEXT_BELOW = 30
SPARSE_TEXT = 5
SPARSE_PIC_FRACTION = 0.10
VISION_GRAPHIC_SHAPES = 2          # >= this many vector shapes (freeform/auto) => a diagram

# placeholder: image extraction
PICTURE_FILL = 6                   # MSO_FILL.PICTURE enum value
_EMBED_RE = re.compile(r'embed="(rId\d+)"')
_RASTER = {"png", "jpg", "jpeg", "gif", "webp"}

_NO_FENCE = " Output raw Markdown only; do not wrap your answer in a code fence."

SLIDE_PROMPT = (
    "You are reading a single slide from a presentation. Transcribe everything on it "
    "as clean Markdown: every piece of text (title, bullets, labels, captions, footnotes), "
    "and for any chart, diagram, table, screenshot, or image, describe what it shows and "
    "report the data or relationships it conveys (axis values, trends, comparisons, flow). "
    "Preserve the reading order. Ignore purely decorative backgrounds. Do not add commentary "
    "and do not invent anything not visible on the slide." + _NO_FENCE
)

WHOLE_PROMPT = (
    "This is a full slide presentation exported as PDF. Transcribe every slide as clean "
    "Markdown, one '## Slide N' section per slide in order. Include all text, and describe "
    "any chart, diagram, table, or image and the data it conveys. Ignore purely decorative "
    "backgrounds. Do not invent content." + _NO_FENCE
)

IMAGE_PROMPT = (
    "This image was taken from a presentation slide. If it is a chart, graph, table, "
    "diagram, or figure, extract its content as clean Markdown: title, axis labels and "
    "ranges, legend/series, and the data, trends, or relationships it conveys. If it is a "
    "logo, icon, or purely decorative background carrying no information, reply with exactly: "
    "(decorative — no data). Do not invent anything not visible." + _NO_FENCE
)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _client():
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set.")
    from openai import OpenAI
    return OpenAI()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def render_pptx_to_pdf(pptx_path: Path, workdir: Path) -> Path:
    """Convert the whole deck to a PDF once, using headless LibreOffice."""
    soffice = shutil.which("libreoffice") or shutil.which("soffice")
    if not soffice:
        raise RuntimeError(
            "LibreOffice ('soffice') not found. Install it to render slides "
            "(macOS: `brew install --cask libreoffice`)."
        )
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(workdir), str(pptx_path)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    pdf_path = workdir / (pptx_path.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError("LibreOffice did not produce a PDF.")
    return pdf_path


def split_pages_to_pdfs(pdf_path: Path, slide_numbers: list[int],
                        workdir: Path) -> dict[int, Path]:
    """Split the requested pages (1-based) into single-page PDFs."""
    import fitz  # PyMuPDF
    fitz.TOOLS.mupdf_display_errors(False)

    out: dict[int, Path] = {}
    if not slide_numbers:
        return out
    src = fitz.open(str(pdf_path))
    try:
        for n in slide_numbers:
            idx = n - 1
            if idx < 0 or idx >= src.page_count:
                print(f"  ! slide {n}: no matching PDF page, skipping", file=sys.stderr)
                continue
            one = fitz.open()
            one.insert_pdf(src, from_page=idx, to_page=idx)
            pdf = workdir / f"slide_{n}.pdf"
            one.save(str(pdf))
            one.close()
            out[n] = pdf
    finally:
        src.close()
    return out


def extract_text(slide) -> str:
    """Pull text frames, table cells, and speaker notes from a slide."""
    chunks: list[str] = []

    def walk(shapes):
        for s in shapes:
            if s.shape_type == MSO_SHAPE_TYPE.GROUP:
                walk(s.shapes)
                continue
            if getattr(s, "has_text_frame", False):
                txt = s.text_frame.text.strip()
                if txt:
                    chunks.append(txt)
            if getattr(s, "has_table", False):
                for row in s.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        chunks.append(" | ".join(cells))

    walk(slide.shapes)
    if slide.has_notes_slide:
        notes = slide.notes_slide.notes_text_frame.text.strip()
        if notes:
            chunks.append("**Speaker notes:** " + notes)
    return "\n\n".join(chunks)


# --------------------------------------------------------------------------- #
# Model calls (the "sending" part)
# --------------------------------------------------------------------------- #
def describe_slide_pdf(client, pdf_path: Path, model: str = MODEL) -> str:
    """Send one single-page slide PDF and return its Markdown transcript."""
    resp = client.responses.create(
        model=model,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": SLIDE_PROMPT},
            {"type": "input_file", "filename": pdf_path.name,
             "file_data": f"data:application/pdf;base64,{_b64(pdf_path.read_bytes())}"}]}],
    )
    return (resp.output_text or "").strip()


def describe_whole_pdf(client, pdf_path: Path, model: str = MODEL) -> str:
    """Send the entire deck as one PDF and return the full transcript."""
    resp = client.responses.create(
        model=model,
        input=[{"role": "user", "content": [
            {"type": "input_file", "filename": pdf_path.name,
             "file_data": f"data:application/pdf;base64,{_b64(pdf_path.read_bytes())}"},
            {"type": "input_text", "text": WHOLE_PROMPT}]}],
    )
    return (resp.output_text or "").strip()


def _svg_to_png(svg_bytes: bytes) -> bytes:
    import fitz  # PyMuPDF
    return fitz.open(stream=svg_bytes, filetype="svg")[0].get_pixmap().tobytes("png")


def _data_url(blob: bytes, ext: str) -> str:
    ext = ext.lower()
    if ext == "svg":
        blob, ext = _svg_to_png(blob), "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext if ext in _RASTER else "png")
    return f"data:image/{mime};base64,{_b64(blob)}"


def describe_image(client, blob: bytes, ext: str, model: str = MODEL) -> str:
    """Send one image and return the data/context it conveys as Markdown."""
    resp = client.responses.create(
        model=model,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": IMAGE_PROMPT},
            {"type": "input_image", "image_url": _data_url(blob, ext),
             "detail": IMAGE_DETAIL}]}],
    )
    return (resp.output_text or "").strip()


# --------------------------------------------------------------------------- #
# routed: per-slide routing helpers
# --------------------------------------------------------------------------- #
def _text_weight(shape) -> float:
    if not getattr(shape, "is_placeholder", False):
        return 0.8
    t = str(getattr(shape.placeholder_format, "type", "") or "")
    if "SUBTITLE" in t:
        return 1.2
    if "TITLE" in t:
        return 1.5
    if "BODY" in t or "OBJECT" in t:
        return 1.0
    if any(k in t for k in ("FOOTER", "SLIDE_NUMBER", "DATE")):
        return 0.0
    return 0.8


def _text_score(shape) -> float:
    return _text_weight(shape) * min(len(shape.text_frame.text.split()), WORD_CAP)


def route_slide(slide, slide_area: int) -> str:
    """Return "text" or "vision" for a single slide."""
    score = 0.0
    pic_area = 0
    graphic_shapes = 0

    def walk(shapes):
        nonlocal score, pic_area, graphic_shapes
        for s in shapes:
            if s.shape_type == MSO_SHAPE_TYPE.GROUP:
                walk(s.shapes)
            elif s.shape_type == MSO_SHAPE_TYPE.PICTURE:
                pic_area += (s.width or 0) * (s.height or 0)
                graphic_shapes += 1
            elif s.shape_type in (MSO_SHAPE_TYPE.FREEFORM, MSO_SHAPE_TYPE.AUTO_SHAPE):
                graphic_shapes += 1
                if getattr(s, "has_text_frame", False):
                    score += _text_score(s)
            elif getattr(s, "has_text_frame", False):
                score += _text_score(s)

    walk(slide.shapes)
    pic_fraction = pic_area / slide_area if slide_area else 0.0

    if pic_fraction > VISION_PIC_FRACTION and score < VISION_TEXT_BELOW:
        return "vision"
    if score < SPARSE_TEXT and pic_fraction > SPARSE_PIC_FRACTION:
        return "vision"
    if graphic_shapes >= VISION_GRAPHIC_SHAPES:
        return "vision"
    return "text"


# --------------------------------------------------------------------------- #
# placeholder: image extraction (handles PICTURE shapes and picture-FILL shapes)
# --------------------------------------------------------------------------- #
def image_of(shape) -> tuple[bytes, str] | None:
    """Return (blob, ext) if the shape carries a picture, else None."""
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        try:
            img = shape.image
            return img.blob, img.ext.lower()
        except Exception:
            pass
    try:
        if int(shape.fill.type) == PICTURE_FILL:
            m = _EMBED_RE.search(shape._element.xml)
            if m:
                part = shape.part.related_part(m.group(1))
                return part.blob, part.partname.split(".")[-1].lower()
    except Exception:
        pass
    return None


def _emu(v) -> int:
    return v if isinstance(v, int) else 0


def _collect_slide(slide) -> list[tuple[str, object]]:
    """Ordered list of ("text", str) / ("image", (blob, ext)) in reading order."""
    items: list[tuple[str, object]] = []

    def walk(shapes):
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
# The three methods
# --------------------------------------------------------------------------- #
def convert_whole(pptx_path: Path, model: str = MODEL) -> str:
    """Render the whole deck to one PDF and transcribe it in a single call."""
    client = _client()
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = render_pptx_to_pdf(pptx_path, Path(tmp))
        print(f"whole: 1 deck PDF -> {model}", file=sys.stderr)
        return describe_whole_pdf(client, pdf_path, model=model).strip() + "\n"


def convert_routed(pptx_path: Path, model: str = MODEL,
                   max_workers: int = MAX_WORKERS) -> str:
    """Route each slide; extract text natively, send visual slides as PDFs (concurrent)."""
    prs = Presentation(str(pptx_path))
    area = (prs.slide_width or 1) * (prs.slide_height or 1)

    routed: list[tuple[int, str, str | None]] = []
    for i, slide in enumerate(prs.slides, start=1):
        kind = route_slide(slide, area)
        routed.append((i, kind, extract_text(slide) if kind == "text" else None))

    vision_pages = [i for i, kind, _ in routed if kind == "vision"]
    print(f"routed: {len(routed)} slides, {len(routed) - len(vision_pages)} text, "
          f"{len(vision_pages)} vision {vision_pages or ''}", file=sys.stderr)

    vision_text: dict[int, str] = {}
    if vision_pages:
        client = _client()
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            pdf_path = render_pptx_to_pdf(pptx_path, workdir)
            slide_pdfs = split_pages_to_pdfs(pdf_path, vision_pages, workdir)

            def run(n: int) -> tuple[int, str]:
                if n not in slide_pdfs:
                    return n, "_[slide could not be rendered]_"
                try:
                    return n, describe_slide_pdf(client, slide_pdfs[n], model=model)
                except Exception as exc:
                    return n, f"_[vision call failed: {exc}]_"

            workers = min(max_workers, len(vision_pages))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for n, text in ex.map(run, vision_pages):
                    vision_text[n] = text

    blocks: list[str] = []
    for i, kind, text in routed:
        body = (text if kind == "text" else vision_text.get(i, "")) or "_[no content]_"
        blocks.append(f"## Slide {i}  ({kind})\n\n{body.strip()}")
    return "\n\n---\n\n".join(blocks) + "\n"


def convert_placeholder(pptx_path: Path, model: str = MODEL,
                        max_workers: int = MAX_WORKERS) -> str:
    """Extract text natively; describe each unique image once and splice it back."""
    prs = Presentation(str(pptx_path))

    registry: dict[str, dict] = {}        # sha1 -> {id, blob, ext, desc}
    by_id: dict[int, dict] = {}
    per_slide: list[tuple[int, list]] = []

    for i, slide in enumerate(prs.slides, start=1):
        rendered: list[tuple[str, object]] = []
        for kind, val in _collect_slide(slide):
            if kind == "text":
                rendered.append(("text", val))
                continue
            blob, ext = val                                   # type: ignore[misc]
            h = hashlib.sha1(blob).hexdigest()
            if h not in registry:
                entry = {"id": len(registry) + 1, "blob": blob, "ext": ext, "desc": ""}
                registry[h] = entry
                by_id[entry["id"]] = entry
            rendered.append(("image", registry[h]["id"]))
        per_slide.append((i, rendered))

    n_img = len(registry)
    n_refs = sum(1 for _, items in per_slide for k, _ in items if k == "image")
    print(f"placeholder: {len(per_slide)} slides, {n_img} unique images "
          f"({n_refs} placements)", file=sys.stderr)

    if registry:
        client = _client()

        def run(entry: dict) -> None:
            try:
                entry["desc"] = describe_image(client, entry["blob"], entry["ext"], model)
            except Exception as exc:
                entry["desc"] = f"_[image description failed: {exc}]_"

        with ThreadPoolExecutor(max_workers=min(max_workers, n_img)) as ex:
            list(ex.map(run, registry.values()))

    blocks: list[str] = []
    for i, items in per_slide:
        parts: list[str] = []
        for kind, val in items:
            if kind == "text":
                parts.append(str(val))
            else:
                parts.append(f"**[Image {val}]**\n\n{by_id[val]['desc'] or '_[no description]_'}")
        blocks.append(f"## Slide {i}\n\n" + ("\n\n".join(parts) if parts else "_[no content]_"))
    return "\n\n---\n\n".join(blocks) + "\n"


METHODS = {
    "placeholder": convert_placeholder,
    "routed": convert_routed,
    "whole": convert_whole,
}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="Convert a PPTX to Markdown.")
    ap.add_argument("pptx", help="path to the .pptx file")
    ap.add_argument("--method", choices=list(METHODS), default="placeholder",
                    help="extraction strategy (default: placeholder)")
    ap.add_argument("-o", "--out", help="output .md path (default: output/<name>.md)")
    ap.add_argument("-m", "--model", default=MODEL, help=f"OpenAI model (default: {MODEL})")
    args = ap.parse_args()

    pptx_path = Path(args.pptx)
    if not pptx_path.exists():
        sys.exit(f"File not found: {pptx_path}")
    out_path = Path(args.out) if args.out else Path("output") / (pptx_path.stem + ".md")

    markdown = METHODS[args.method](pptx_path, model=args.model)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    print(f"[{args.method} -> {out_path}]", file=sys.stderr)


if __name__ == "__main__":
    main()
