"""Standalone Spire.Presentation probe -> semantic XML, matching pptx_converter_v4 / pdf_extractor.

Spire only, no LLM. Same XML shape as the real extractors:
    <document index="1" filename="ppt_1_<hash>.txt" data-type="PPT">
      <metadata><source_file>…</source_file><slides>…</slides>…</metadata>
      <slide number="1">
        <text>native text…</text>
        <figure id="1">[image image/png 1007x598]</figure>   <-- info, not an AI description
      </slide>
    </document>

Because there is no describer, each <figure> shows the image's MIME + dimensions instead of a
description. Use it to see WHAT Spire extracts and WHERE (placement), in the pipeline's format.

    python spire_check.py deck.pptx                  # -> <stem>_spire.xml
    python spire_check.py deck.pptx --out out.xml    # choose the path
    python spire_check.py deck.pptx --save saved.pptx  # also SaveToFile then render the watermarked
                                                       # file's xml (the watermark shows up as <text>)
"""
import argparse
import hashlib
import sys
from pathlib import Path

from spire.presentation import Presentation, FillFormatType

WATERMARK_HINTS = ("evaluation warning", "created with spire", "e-iceblue")
MIME_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg",
            "image/gif": "gif", "image/webp": "webp", "image/bmp": "bmp"}
MIN_IMAGE_DIM = 150


def xml_attr(value) -> str:
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def xml_text(value) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def doc_name(data_type, index, path) -> str:
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:24]
    return f"{data_type.lower()}_{index}_{digest}.txt"


def _dt(dt) -> str:
    try:
        return f"{dt.Year:04d}-{dt.Month:02d}-{dt.Day:02d}"
    except Exception:
        return ""


def _sort_key(shape) -> tuple[float, float]:
    try: top = float(shape.Top)
    except Exception: top = 0.0
    try: left = float(shape.Left)
    except Exception: left = 0.0
    return top, left


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


def image_data(shape):
    """(blob, content_type, width, height) for a picture shape, else None."""
    picture_fill = getattr(shape, "PictureFill", None)
    if picture_fill is None:
        try:
            picture_fill = shape.Fill.PictureFill
        except Exception:
            return None
    try:
        ed = picture_fill.Picture.EmbedImage
        return bytes(ed.Image.ToArray()), ed.ContentType, ed.Width, ed.Height
    except Exception:
        return None


def collect_blocks(shapes, registry, stats):
    """Yield ('text', str) / ('image', id) in reading order; registry dedups images by content."""
    ordered = sorted((shapes[j] for j in range(shapes.Count)), key=_sort_key)
    for shape in ordered:
        if type(shape).__name__ == "GroupShape":
            yield from collect_blocks(shape.Shapes, registry, stats)
            continue
        if is_picture(shape):
            data = image_data(shape)
            if data is None:
                continue
            blob, content_type, w, h = data
            if MIME_EXT.get((content_type or "").strip().lower()) is None:
                stats["vector"] += 1
            elif w and h and min(w, h) < MIN_IMAGE_DIM:
                stats["small"] += 1
            else:
                digest = hashlib.sha1(blob).hexdigest()
                info = registry.get(digest)
                if info is None:
                    info = registry[digest] = {"id": len(registry) + 1,
                                               "ct": content_type, "w": w, "h": h}
                yield "image", info["id"]
            continue
        text = shape_text(shape)
        if text:
            yield "text", text


def build(path):
    """Return (slides, by_id, metadata, stats) for a .ppt/.pptx via Spire."""
    prs = Presentation()
    prs.LoadFromFile(path)
    registry, stats = {}, {"vector": 0, "small": 0}
    slides = [(i + 1, list(collect_blocks(prs.Slides[i].Shapes, registry, stats)))
              for i in range(prs.Slides.Count)]
    dp = prs.DocumentProperty
    metadata = {"source_file": Path(path).name, "slides": str(len(slides)),
                "images": str(len(registry)), "title": dp.Title or "", "author": dp.Author or "",
                "last_modified_by": dp.LastSavedBy or "", "created": _dt(dp.CreatedTime),
                "modified": _dt(dp.LastSavedTime),
                "revision": str(dp.RevisionNumber) if dp.RevisionNumber else ""}
    prs.Dispose()
    by_id = {info["id"]: info for info in registry.values()}
    return slides, by_id, metadata, stats


def render_xml(slides, by_id, filename, data_type, metadata, index=1) -> str:
    lines = [f'<document index="{index}" filename="{xml_attr(filename)}"'
             f' data-type="{xml_attr(data_type)}">']
    lines.append("  <metadata>")
    for key, value in metadata.items():
        if value:
            lines.append(f"    <{key}>{xml_text(value)}</{key}>")
    lines.append("  </metadata>")

    for number, blocks in slides:
        lines.append(f'  <slide number="{number}">')
        text_buf = []

        def flush_text():
            if text_buf:
                lines.append(f"    <text>{xml_text(chr(10).join(text_buf))}</text>")
                text_buf.clear()

        for kind, value in blocks:
            if kind == "text":
                text_buf.append(value)
            else:
                flush_text()
                info = by_id[value]
                lines.append(f'    <figure id="{value}">'
                             f'[image {info["ct"]} {info["w"]}x{info["h"]}]</figure>')
        flush_text()
        lines.append("  </slide>")

    lines.append("</document>")
    return "\n".join(lines) + "\n"


def _watermark_count(slides) -> int:
    return sum(1 for _, blocks in slides for kind, value in blocks
               if kind == "text" and any(h in value.lower() for h in WATERMARK_HINTS))


def convert(path, data_type, out_path):
    slides, by_id, metadata, stats = build(path)
    words = sum(len(v.split()) for _, blocks in slides for k, v in blocks if k == "text")
    wm = _watermark_count(slides)
    print(f"LOADED: {len(slides)} slides, {len(by_id)} images "
          f"({stats['vector']} vector + {stats['small']} small skipped), {words} words")
    print("READ content CLEAN — no watermark." if not wm else f"!! {wm} watermark text blocks")
    xml = render_xml(slides, by_id, doc_name(data_type, 1, path), data_type, metadata)
    Path(out_path).write_text(xml, encoding="utf-8")
    print(f"wrote {out_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Spire.Presentation -> semantic XML (matches v4 / pdf_extractor).")
    parser.add_argument("file", help=".ppt or .pptx file")
    parser.add_argument("--out", metavar="XML", help="output path (default: <stem>_spire.xml)")
    parser.add_argument("--save", metavar="OUT", help="also SaveToFile then render the watermarked file's xml")
    args = parser.parse_args(argv)

    kind = "PPT" if args.file.lower().endswith(".ppt") else "PPTX"
    convert(args.file, kind, args.out or f"{Path(args.file).stem}_spire.xml")

    if args.save:
        print("-" * 60)
        from spire.presentation import FileFormat
        prs = Presentation()
        prs.LoadFromFile(args.file)
        print(f"SAVING to {args.save} (write path — injects the watermark)...")
        prs.SaveToFile(args.save, FileFormat.Pptx2013)
        prs.Dispose()
        convert(args.save, "PPTX", f"{Path(args.save).stem}_spire.xml")


if __name__ == "__main__":
    main()
