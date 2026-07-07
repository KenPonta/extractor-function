"""Inspect what PyMuPDF extracts from a PDF — text blocks, image blocks, vector drawings.

A read-only diagnostic tool: NO LLM, NO XML output. It shows the *middle* of extraction so you
can see, page by page, exactly which text comes out and which images come out (and how the main
extractor would classify each page). Nothing is sent anywhere.

Usage:
    python pdf/inspect_pdf.py file.pdf                 # print the breakdown
    python pdf/inspect_pdf.py file.pdf --full          # print full text (not previews)
    python pdf/inspect_pdf.py file.pdf --dump imgs/    # also save every extracted image to imgs/
"""

import argparse
import hashlib
import sys
from pathlib import Path

import fitz  # PyMuPDF

# Same classification signals the real extractor (pdf_extractor.py) uses, inlined so this tool
# stays standalone (only PyMuPDF, no Azure/.env). Shown here only to explain each page's routing.
SCANNED_TEXT_MAX_CHARS = 20
SCANNED_IMAGE_COVER = 0.60
VECTOR_MIN_PATHS = 8
VECTOR_COVER = 0.20
VECTOR_MAX_TEXT = 400


# Functionality: Join a "dict" text block's spans/lines into one string.
def block_text(block: dict) -> str:
    lines = []
    for line in block.get("lines", []):
        text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


# Functionality: Decide how the main extractor would route a page, from the same signals.
# Return: a short verdict string.
def classify(text_len, image_area, page_area, n_draw, draw_cover, has_image) -> str:
    if text_len <= SCANNED_TEXT_MAX_CHARS and image_area / page_area >= SCANNED_IMAGE_COVER:
        return "SCANNED  -> render whole page + TRANSCRIBE (OCR)"
    if text_len == 0 and not has_image and n_draw == 0:
        return "EMPTY    -> render (fallback) + transcribe"
    if (not has_image and n_draw >= VECTOR_MIN_PATHS and draw_cover >= VECTOR_COVER
            and text_len < VECTOR_MAX_TEXT):
        return "VECTOR DIAGRAM -> render whole page + DESCRIBE as a figure"
    return "NORMAL   -> extract text, embedded images become figures"


# Functionality: Print the extraction breakdown for one page (and optionally dump images).
def inspect_page(page, number, dump_dir: Path | None, full_text: bool):
    data = page.get_text("dict")
    pw, ph = page.rect.width, page.rect.height
    page_area = (pw * ph) or 1.0

    text_blocks, image_blocks = [], []
    text_len, image_area = 0, 0.0
    for block in data.get("blocks", []):
        x0, y0, x1, y1 = (round(v) for v in block["bbox"])
        if block["type"] == 0:
            text = block_text(block)
            if text:
                text_blocks.append(((x0, y0, x1, y1), text))
                text_len += len(text)
        elif block["type"] == 1 and block.get("image"):
            image_blocks.append(((x0, y0, x1, y1), block))
            image_area += max(0, x1 - x0) * max(0, y1 - y0)

    drawings = page.get_drawings()
    union = None
    for d in drawings:
        r = fitz.Rect(d["rect"])
        union = r if union is None else (union | r)
    draw_cover = (abs(union) / page_area) if union else 0.0

    print(f"\n──────── Page {number} ── {pw:.0f} x {ph:.0f} pt ────────")

    # --- TEXT that gets extracted ---
    print(f"  TEXT blocks: {len(text_blocks)}  (total {text_len} chars)")
    for k, (bbox, text) in enumerate(text_blocks):
        if full_text:
            print(f"    [t{k}] bbox={bbox} chars={len(text)}")
            for line in text.splitlines():
                print(f"          {line}")
        else:
            preview = text.replace("\n", " ")
            preview = preview[:90] + ("…" if len(preview) > 90 else "")
            print(f'    [t{k}] bbox={bbox} chars={len(text)}  "{preview}"')

    # --- IMAGES that get extracted ---
    print(f"  IMAGE blocks: {len(image_blocks)}")
    for k, (bbox, block) in enumerate(image_blocks):
        blob = block["image"]
        sha = hashlib.sha256(blob).hexdigest()[:8]
        line = (f"    [i{k}] {block.get('ext','?'):>4}  {block.get('width')}x{block.get('height')} px  "
                f"bbox={bbox}  {len(blob):,} bytes  sha={sha}")
        if dump_dir is not None:
            out = dump_dir / f"page{number}_img{k}.{block.get('ext','png')}"
            out.write_bytes(blob)
            line += f"  -> {out}"
        print(line)

    # --- VECTOR graphics (the third channel; not extractable as text/image) ---
    print(f"  VECTOR drawings: {len(drawings)}  (bounding box covers {draw_cover*100:.0f}% of page)")

    # --- how the real extractor would route this page ---
    verdict = classify(text_len, image_area, page_area, len(drawings), draw_cover, bool(image_blocks))
    cover_pct = image_area / page_area * 100
    print(f"  signals: text_len={text_len}  image-cover={cover_pct:.0f}%  drawings={len(drawings)}")
    print(f"  => {verdict}")

    # optionally save the whole-page render for pages that would be rendered
    if dump_dir is not None and ("render" in verdict.lower()):
        out = dump_dir / f"page{number}_rendered.png"
        out.write_bytes(page.get_pixmap(dpi=150).tobytes("png"))
        print(f"     (whole-page render that would be sent to the LLM -> {out})")


def inspect_pdf(pdf_path, dump_dir=None, full_text=False):
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"unsupported file type: {path.name} (expected .pdf)")
    if dump_dir is not None:
        dump_dir = Path(dump_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)

    with fitz.open(str(path)) as doc:
        print("=" * 64)
        print(f"FILE: {path.name}   ({doc.page_count} pages)")
        if dump_dir is not None:
            print(f"dumping extracted images to: {dump_dir}/")
        print("=" * 64)
        for i in range(doc.page_count):
            inspect_page(doc[i], i + 1, dump_dir, full_text)
        print("\n" + "=" * 64)
        print("legend: TEXT = selectable text layer | IMAGE = embedded raster | "
              "VECTOR = drawn shapes (invisible to text/image extraction)")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect PyMuPDF text/image extraction from a PDF "
                                                 "(read-only; no LLM).")
    parser.add_argument("file", type=Path, help=".pdf file")
    parser.add_argument("--full", action="store_true", help="print full text instead of previews")
    parser.add_argument("-d", "--dump", type=Path, default=None,
                        help="directory to save every extracted image (and rendered pages)")
    args = parser.parse_args(argv)
    try:
        inspect_pdf(args.file, dump_dir=args.dump, full_text=args.full)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
