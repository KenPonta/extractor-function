"""Standalone Spire.Presentation probe — test read limits & watermark. Spire only, no LLM.

    python spire_check.py deck.pptx                  # READ test: slide count, text, images, watermark
    python spire_check.py deck.pptx --save out.pptx  # also SAVE (write path) and re-check for watermark

Read test tells you:
  - how many slides Spire actually loads (compare to the real count -> is there a read cap?)
  - per-slide text words + image count (is anything silently dropped on big decks?)
  - whether any 'Evaluation Warning' watermark text leaked into the READ content (should be none)

--save also does SaveToFile (a WRITE op) and reloads it to show the watermark Spire injects on save.
"""
import argparse
import sys

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


def read_test(path: str) -> None:
    prs = Presentation()
    prs.LoadFromFile(path)
    n = prs.Slides.Count
    print(f"LOADED: {n} slides\n")

    total_words = total_images = 0
    watermark_hits = []
    for i in range(n):
        words = images = 0
        for shape in walk_shapes(prs.Slides[i].Shapes):
            text = shape_text(shape)
            if text:
                words += len(text.split())
                if any(h in text.lower() for h in WATERMARK_HINTS):
                    watermark_hits.append((i + 1, text))
            if is_picture(shape):
                images += 1
        total_words += words
        total_images += images
        print(f"  slide {i + 1:>3}: {words:>4} words, {images} image-shapes")

    print(f"\nTOTAL: {n} slides, {total_words} words, {total_images} image-shapes")

    dp = prs.DocumentProperty
    print(f"metadata: title={dp.Title!r} author={dp.Author!r} last_saved_by={dp.LastSavedBy!r}")
    prs.Dispose()

    print()
    if watermark_hits:
        print(f"!! WATERMARK text found in READ content ({len(watermark_hits)} shapes):")
        for slide_no, text in watermark_hits[:5]:
            print(f"   slide {slide_no}: {text!r}")
    else:
        print("READ content is CLEAN — no evaluation watermark text in extracted content.")


def save_test(path: str, out: str) -> None:
    from spire.presentation import FileFormat
    prs = Presentation()
    prs.LoadFromFile(path)
    print(f"SAVING to {out} (write path — this should inject the watermark)...")
    prs.SaveToFile(out, FileFormat.Pptx2013)
    prs.Dispose()

    check = Presentation()
    check.LoadFromFile(out)
    slide_count = check.Slides.Count            # capture before Dispose (freed objects raise)
    hits = 0
    for i in range(slide_count):
        for shape in walk_shapes(check.Slides[i].Shapes):
            if any(h in shape_text(shape).lower() for h in WATERMARK_HINTS):
                hits += 1
                break
    check.Dispose()
    print(f"watermark shapes in the SAVED file: {hits} / {slide_count} slides "
          f"({'present' if hits else 'none'})")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Probe Spire.Presentation read limits & watermark (Spire only).")
    parser.add_argument("file", help=".ppt or .pptx file")
    parser.add_argument("--save", metavar="OUT", help="also SaveToFile to OUT and re-check for the watermark")
    args = parser.parse_args(argv)

    read_test(args.file)
    if args.save:
        print("-" * 60)
        save_test(args.file, args.save)


if __name__ == "__main__":
    main()
