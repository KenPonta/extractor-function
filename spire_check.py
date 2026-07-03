"""Standalone Spire.Presentation probe — read limits, watermark, and content dump. Spire only, no LLM.

    python spire_check.py deck.pptx                  # read + write extracted content to <stem>_spire.md
    python spire_check.py deck.pptx --md out.md      # choose the markdown path
    python spire_check.py deck.pptx --save saved.pptx  # ALSO SaveToFile (write path) and dump the
                                                       # watermarked file's content to saved_spire.md

What you get:
  - console: slide count (read-cap check), per-slide word/image counts, watermark check on read content
  - <stem>_spire.md: every slide's actual extracted text + image info, so you can eyeball the content
  - with --save: the saved file's content dumped too, where the 'Evaluation Warning' watermark IS visible
"""
import argparse
import sys
from pathlib import Path

from spire.presentation import Presentation, FillFormatType

WATERMARK_HINTS = ("evaluation warning", "created with spire", "e-iceblue")


def walk_shapes(shapes):
    """Yield every shape on a slide, recursing into groups. (Spire objects: never use `if shape:`.)"""
    for j in range(shapes.Count):
        shape = shapes[j]
        yield shape
        if type(shape).__name__ == "GroupShape":
            yield from walk_shapes(shape.Shapes)


def shape_text(shape) -> str:
    try:
        return (shape.TextFrame.Text or "").strip()
    except Exception:
        return ""


def is_picture(shape) -> bool:
    if type(shape).__name__ == "SlidePicture":
        return True
    try:
        return shape.Fill.FillType == FillFormatType.Picture
    except Exception:
        return False


def image_info(shape):
    """Return (content_type, width, height) for a picture shape, else None."""
    picture_fill = getattr(shape, "PictureFill", None)
    if picture_fill is None:
        try:
            picture_fill = shape.Fill.PictureFill
        except Exception:
            return None
    try:
        ed = picture_fill.Picture.EmbedImage
        return ed.ContentType, ed.Width, ed.Height
    except Exception:
        return None


def read_test(path: str) -> None:
    prs = Presentation()
    prs.LoadFromFile(path)
    n = prs.Slides.Count
    print(f"LOADED: {n} slides\n")

    total_words = total_images = 0
    watermark_hits = 0
    for i in range(n):
        words = images = 0
        for shape in walk_shapes(prs.Slides[i].Shapes):
            text = shape_text(shape)
            if text:
                words += len(text.split())
                if any(h in text.lower() for h in WATERMARK_HINTS):
                    watermark_hits += 1
            if is_picture(shape):
                images += 1
        total_words += words
        total_images += images
        print(f"  slide {i + 1:>3}: {words:>4} words, {images} image-shapes")

    print(f"\nTOTAL: {n} slides, {total_words} words, {total_images} image-shapes")
    dp = prs.DocumentProperty
    print(f"metadata: title={dp.Title!r} author={dp.Author!r} last_saved_by={dp.LastSavedBy!r}")
    prs.Dispose()
    print("READ content is CLEAN — no watermark." if not watermark_hits
          else f"!! {watermark_hits} watermark shapes in READ content")


def write_markdown(path: str, md_path: str) -> tuple[int, int]:
    """Dump every slide's extracted text + image info to a markdown file. Returns (slides, watermark_lines)."""
    prs = Presentation()
    prs.LoadFromFile(path)
    n = prs.Slides.Count
    dp = prs.DocumentProperty
    out = [f"# Spire extraction: {Path(path).name}", "",
           f"- **slides:** {n}",
           f"- **title:** {dp.Title}",
           f"- **author:** {dp.Author}",
           f"- **last_saved_by:** {dp.LastSavedBy}", ""]

    watermark_lines = 0
    for i in range(n):
        out.append(f"## Slide {i + 1}")
        out.append("")
        for shape in walk_shapes(prs.Slides[i].Shapes):
            text = shape_text(shape)
            if text:
                if any(h in text.lower() for h in WATERMARK_HINTS):
                    watermark_lines += 1
                    out.append(f"> ⚠️ **WATERMARK:** {text}")
                else:
                    out.append(text)
                out.append("")
            elif is_picture(shape):
                info = image_info(shape)
                if info:
                    ct, w, h = info
                    out.append(f"`[image: {ct} {w}x{h}]`")
                    out.append("")
        out.append("")
    prs.Dispose()
    Path(md_path).write_text("\n".join(out) + "\n", encoding="utf-8")
    return n, watermark_lines


def save_test(path: str, out: str) -> None:
    from spire.presentation import FileFormat
    prs = Presentation()
    prs.LoadFromFile(path)
    print(f"SAVING to {out} (write path — this should inject the watermark)...")
    prs.SaveToFile(out, FileFormat.Pptx2013)
    prs.Dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Probe Spire.Presentation read limits, watermark & content (Spire only).")
    parser.add_argument("file", help=".ppt or .pptx file")
    parser.add_argument("--md", metavar="OUT", help="markdown output path (default: <stem>_spire.md)")
    parser.add_argument("--save", metavar="OUT", help="also SaveToFile and dump the watermarked file's content")
    args = parser.parse_args(argv)

    read_test(args.file)

    md_out = args.md or f"{Path(args.file).stem}_spire.md"
    n, wm = write_markdown(args.file, md_out)
    print(f"\nwrote extracted content -> {md_out}  ({n} slides, {wm} watermark lines)")

    if args.save:
        print("-" * 60)
        save_test(args.file, args.save)
        saved_md = f"{Path(args.save).stem}_spire.md"
        n2, wm2 = write_markdown(args.save, saved_md)
        print(f"wrote SAVED (watermarked) content -> {saved_md}  ({n2} slides, {wm2} watermark lines)")


if __name__ == "__main__":
    main()
