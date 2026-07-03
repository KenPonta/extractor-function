"""pptx_converter_v4.py — .ppt parsed with Spire ONLY (no sharepoint2text).

Spire supplies text, images (exact placement) AND tables for .ppt, walking the shape tree
in reading order just like the .pptx path. Uses the same llm_ref for descriptions.

Client via --provider: 'openai' (dev box, gpt-4.1) or 'azure' (real device, deployment name).
Default is azure so a production pull runs unchanged.
"""
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
MIN_IMAGE_DIM = 150


def content_digest(blob: bytes) -> str:
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
    blocks: list = field(default_factory=list)


@dataclass
class ImageRegistry:
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


def validate_file(file_path) -> tuple[Path, str]:
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


def xml_text(value) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- metadata --------------------------------------------------------------- #
def _spire_dt(dt) -> str:
    try:
        return f"{dt.Year:04d}-{dt.Month:02d}-{dt.Day:02d}"
    except Exception:
        return ""


def _pptx_metadata(prs) -> dict:
    cp = prs.core_properties
    return {"title": cp.title or "", "author": cp.author or "", "subject": cp.subject or "",
            "keywords": cp.keywords or "", "last_modified_by": cp.last_modified_by or "",
            "created": cp.created.isoformat() if cp.created else "",
            "modified": cp.modified.isoformat() if cp.modified else "",
            "revision": str(cp.revision) if cp.revision else ""}


def _ppt_metadata(prs) -> dict:
    dp = prs.DocumentProperty
    return {"title": dp.Title or "", "author": dp.Author or "", "subject": dp.Subject or "",
            "keywords": dp.Keywords or "", "last_modified_by": dp.LastSavedBy or "",
            "created": _spire_dt(dp.CreatedTime), "modified": _spire_dt(dp.LastSavedTime),
            "revision": str(dp.RevisionNumber) if dp.RevisionNumber else ""}


def doc_name(data_type, index, file_path) -> str:
    """Generated document id for the filename attr (NOT the real name): '<type>_<index>_<hash>.txt'.
    The real name is kept in metadata as <source_file>."""
    digest = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()[:24]
    return f"{data_type.lower()}_{index}_{digest}.txt"


def log_parse(kind, slides, registry, skipped_vector=0, skipped_small=0):
    placements = sum(k == "image" for s in slides for k, _ in s.blocks)
    logger.info("%s: %d slides, %d images, %d placements, %d vector + %d small skipped",
                kind, len(slides), len(registry.images), placements, skipped_vector, skipped_small)


# --- .pptx parsing (python-pptx, exact) ------------------------------------- #
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


def parse_pptx(path, registry) -> tuple:
    from pptx import Presentation
    prs = Presentation(str(path))
    slides = [Slide(n, list(iter_pptx_blocks(slide.shapes, registry)))
              for n, slide in enumerate(prs.slides, start=1)]
    log_parse("pptx", slides, registry)
    return slides, _pptx_metadata(prs)


# --- .ppt parsing (Spire ONLY: text + images + tables) ---------------------- #
def _spire_sort_key(shape) -> tuple[float, float]:
    """Reading order: top-to-bottom, then left-to-right (guard missing coords)."""
    try: top = float(shape.Top)
    except Exception: top = 0.0
    try: left = float(shape.Left)
    except Exception: left = 0.0
    return top, left


def _spire_image(shape):
    """Return (blob, content_type, width, height) for a Spire picture shape, else None."""
    from spire.presentation import FillFormatType
    is_pic = type(shape).__name__ == "SlidePicture"
    if not is_pic:
        try:
            is_pic = shape.Fill.FillType == FillFormatType.Picture
        except Exception:
            return None
    if not is_pic:
        return None
    picture_fill = getattr(shape, "PictureFill", None)
    if picture_fill is None:
        try: picture_fill = shape.Fill.PictureFill
        except Exception: return None
    try:
        image_data = picture_fill.Picture.EmbedImage
        return (bytes(image_data.Image.ToArray()), image_data.ContentType,
                image_data.Width, image_data.Height)
    except Exception:
        return None


def _spire_text(shape) -> str:
    """Text of an autoshape's text frame, or '' if none."""
    try:
        return (shape.TextFrame.Text or "").strip()
    except Exception:
        return ""


def _spire_table_rows(table) -> list:
    """Flatten a Spire table to 'a | b | c' rows (best effort; untested — no tables in sample)."""
    rows = []
    try:
        for r in range(table.TableRows.Count):
            row = table.TableRows[r]
            cells = []
            for c in range(row.Count):
                try: cells.append((row[c].TextFrame.Text or "").strip())
                except Exception: cells.append("")
            if any(cells):
                rows.append(" | ".join(cells))
    except Exception:
        pass
    return rows


def _spire_blocks(shapes, registry, stats):
    ordered = sorted((shapes[j] for j in range(shapes.Count)), key=_spire_sort_key)
    for shape in ordered:
        name = type(shape).__name__
        if name == "GroupShape":
            yield from _spire_blocks(shape.Shapes, registry, stats)
            continue

        info = _spire_image(shape)
        if info is not None:                                 # image
            blob, content_type, w, h = info
            ext = ext_from_mime(content_type)
            if ext is None:
                stats["vector"] += 1
            elif MIN_IMAGE_DIM and w and h and min(w, h) < MIN_IMAGE_DIM:
                stats["small"] += 1
            else:
                yield "image", registry.register(blob, ext)
            continue

        if name == "ITable":                                 # table
            rows = _spire_table_rows(shape)
            if rows:
                yield "text", "\n".join(rows)
            continue

        text = _spire_text(shape)                            # text
        if text:
            yield "text", text


def parse_ppt(path, registry) -> tuple:
    from spire.presentation import Presentation
    prs = Presentation()
    prs.LoadFromFile(str(path))
    stats = {"vector": 0, "small": 0}
    slides = [Slide(i + 1, list(_spire_blocks(prs.Slides[i].Shapes, registry, stats)))
              for i in range(prs.Slides.Count)]
    metadata = _ppt_metadata(prs)
    prs.Dispose()
    log_parse("ppt", slides, registry, stats["vector"], stats["small"])
    return slides, metadata


# --- rendering (semantic XML: <text> = native, <figure> = image-derived) ---- #
# Layout mirrors pdf_extractor so an LLM can tell native text from image content:
#   <document filename="..." type="PPT">
#     <metadata><title>...</title>...</metadata>
#     <slide number="1">
#       <text>...</text>
#       <figure id="1">description of the image</figure>
#     </slide>
#   </document>
def render_xml(slides, by_id, filename, data_type, metadata=None, index=1) -> str:
    lines = [f'<document index="{index}" filename="{xml_attr(filename)}"'
             f' data-type="{xml_attr(data_type)}">']
    if metadata:
        lines.append("  <metadata>")
        for key, value in metadata.items():
            if value:
                lines.append(f"    <{key}>{xml_text(value)}</{key}>")
        lines.append("  </metadata>")

    for slide in slides:
        lines.append(f'  <slide number="{slide.number}">')
        text_buf = []

        def flush_text():
            if text_buf:
                lines.append(f"    <text>{xml_text(chr(10).join(text_buf))}</text>")
                text_buf.clear()

        for kind, value in slide.blocks:
            if kind == "text":
                text_buf.append(value)
            else:                                            # image -> its own <figure> tag
                flush_text()
                ref = by_id[value]
                desc = xml_text(ref.description or "(no description)")
                lines.append(f'    <figure id="{ref.image_id}">{desc}</figure>')
        flush_text()
        lines.append("  </slide>")

    lines.append("</document>")
    return "\n".join(lines) + "\n"


# --- entry point ------------------------------------------------------------ #
def pptx_converter(file_path, output_dir=None, *, model=DEFAULT_MODEL,
                   max_workers=DEFAULT_MAX_WORKERS, prompt=IMAGE_PROMPT,
                   data_type=None, client=None, describe=True) -> str:
    path, kind = validate_file(file_path)
    registry = ImageRegistry()
    slides, file_meta = parse_pptx(path, registry) if kind == "pptx" else parse_ppt(path, registry)

    images = registry.images
    if images and describe:
        client = client or llm.get_azure_openai_client()
        llm.describe_images(images, model=model, max_workers=max_workers, prompt=prompt, client=client)

    by_id = {image.image_id: image for image in images}
    dtype = data_type or kind.upper()
    metadata = {"source_file": path.name, "slides": str(len(slides)),
                "images": str(len(images)), **file_meta}    # real name kept as source_file
    xml = render_xml(slides, by_id, doc_name(dtype, 1, path), dtype, metadata=metadata, index=1)
    if output_dir is not None:
        out_path = Path(output_dir) / f"{path.stem}.xml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml, encoding="utf-8")
        logger.info("written to %s", out_path)
    return xml


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert .ppt/.pptx to placeholder XML (Spire-only .ppt).")
    parser.add_argument("file", type=Path, help=".ppt or .pptx file")
    parser.add_argument("-o", "--out", type=Path, default="output", help="output directory")
    parser.add_argument("--provider", choices=["azure", "openai"], default="azure",
                        help="azure (real device, default) or openai (dev box)")
    parser.add_argument("-m", "--model", default=None, help="override model / deployment name")
    parser.add_argument("--data-type", default=None)
    parser.add_argument("--no-describe", action="store_true", help="skip vision calls (parse/placement only)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.provider == "openai":
        from openai import OpenAI
        client = OpenAI()
        model = args.model or "gpt-4.1"
    else:
        client = None
        model = args.model or DEFAULT_MODEL

    try:
        pptx_converter(args.file, args.out, model=model, client=client,
                       data_type=args.data_type, describe=not args.no_describe)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
