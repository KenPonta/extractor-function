"""pptx_converter_v5.py — .ppt/.pptx -> semantic XML, parsed ENTIRELY with Spire.Presentation.

v5 drops both python-pptx and sharepoint2text: one Spire path handles both formats (Spire's
LoadFromFile reads .ppt and .pptx alike). It applies the Spire-present.py shape walk — recurse
into groups; detect SlidePicture, PictureShape, AND picture-fill autoshapes; pull IAutoShape text
and ITable rows — in reading order. Each image becomes an <figure> placeholder that is replaced by
its LLM description at render time (the "manifest placeholder -> described text" idea).

Output mirrors pptx_converter_v4 / pdf_extractor:
    <document index="1" filename="ppt_1_<hash>.txt" data-type="PPT">
      <metadata><source_file>…</source_file>…</metadata>
      <slide number="1"><text>…</text><figure id="1">description</figure></slide>
    </document>

Vision client via --provider: 'openai' (dev box, gpt-4.1) or 'azure' (real device, deployment name);
default azure so a production pull runs unchanged. All Azure/LLM config lives in llm_ref.py.
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

RASTER_MIME_EXT = {                 # MIME -> ext; anything not here is treated as vector (skipped)
    "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg",
    "image/gif": "gif", "image/webp": "webp", "image/bmp": "bmp",
}
MIN_IMAGE_DIM = 150                 # px: drop images whose smaller side is under this (icons/rules)


# --- data model ------------------------------------------------------------- #
def content_digest(blob: bytes) -> str:
    """Content hash normalized to decoded RGB pixels so re-encodings of one picture collide."""
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
    blocks: list = field(default_factory=list)  # ("text", str) | ("image", image_id)


@dataclass
class ImageRegistry:
    """De-duplicates images by content so an identical picture is described only once."""
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


# --- helpers ---------------------------------------------------------------- #
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


def doc_name(data_type, index, file_path) -> str:
    """Generated filename attr (NOT the real name): '<type>_<index>_<hash>.txt'."""
    digest = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()[:24]
    return f"{data_type.lower()}_{index}_{digest}.txt"


def _spire_dt(dt) -> str:
    try:
        return f"{dt.Year:04d}-{dt.Month:02d}-{dt.Day:02d}"
    except Exception:
        return ""


def _spire_metadata(prs) -> dict:
    dp = prs.DocumentProperty
    return {"title": dp.Title or "", "author": dp.Author or "", "subject": dp.Subject or "",
            "keywords": dp.Keywords or "", "last_modified_by": dp.LastSavedBy or "",
            "created": _spire_dt(dp.CreatedTime), "modified": _spire_dt(dp.LastSavedTime),
            "revision": str(dp.RevisionNumber) if dp.RevisionNumber else ""}


def log_parse(kind, slides, registry, skipped_vector=0, skipped_small=0):
    placements = sum(k == "image" for s in slides for k, _ in s.blocks)
    logger.info("%s: %d slides, %d images, %d placements, %d vector + %d small skipped",
                kind, len(slides), len(registry.images), placements, skipped_vector, skipped_small)


# --- Spire parsing (both .ppt and .pptx) ------------------------------------ #
def _sort_key(shape) -> tuple[float, float]:
    """Reading order: top-to-bottom, then left-to-right (guard missing coords)."""
    try: top = float(shape.Top)
    except Exception: top = 0.0
    try: left = float(shape.Left)
    except Exception: left = 0.0
    return top, left


def _embed_image(shape):
    """(blob, content_type, width, height) for a picture shape, else None.

    Covers all three Spire picture forms (from Spire-present.py): a SlidePicture, a PictureShape,
    and an autoshape whose fill is a picture (charts pasted as a fill).
    """
    from spire.presentation import SlidePicture, PictureShape, FillFormatType
    embed = None
    if isinstance(shape, SlidePicture):
        embed = shape.PictureFill.Picture.EmbedImage
    elif isinstance(shape, PictureShape):
        embed = shape.EmbedImage
    else:
        try:
            if shape.Fill.FillType == FillFormatType.Picture:
                embed = shape.Fill.PictureFill.Picture.EmbedImage
        except Exception:
            embed = None
    if embed is None:
        return None
    try:
        return bytes(embed.Image.ToArray()), embed.ContentType, embed.Width, embed.Height
    except Exception:
        return None


def _text(shape) -> str:
    try:
        return (shape.TextFrame.Text or "").strip()
    except Exception:
        return ""


def _table_rows(table) -> list:
    """Flatten a Spire ITable to 'a | b | c' rows (best effort)."""
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


def _blocks(shapes, registry, stats):
    """Walk shapes in reading order, recursing groups; yield ('text', str) / ('image', id)."""
    ordered = sorted((shapes[j] for j in range(shapes.Count)), key=_sort_key)
    for shape in ordered:
        name = type(shape).__name__
        if name == "GroupShape":
            yield from _blocks(shape.Shapes, registry, stats)
            continue

        info = _embed_image(shape)
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
            rows = _table_rows(shape)
            if rows:
                yield "text", "\n".join(rows)
            continue

        text = _text(shape)                                  # text
        if text:
            yield "text", text


def parse(path, kind, registry) -> tuple:
    """Parse a .ppt or .pptx into Slides via Spire only. Return (list[Slide], metadata)."""
    from spire.presentation import Presentation
    prs = Presentation()
    prs.LoadFromFile(str(path))
    stats = {"vector": 0, "small": 0}
    slides = [Slide(i + 1, list(_blocks(prs.Slides[i].Shapes, registry, stats)))
              for i in range(prs.Slides.Count)]
    metadata = _spire_metadata(prs)
    prs.Dispose()
    log_parse(kind, slides, registry, stats["vector"], stats["small"])
    return slides, metadata


def render_xml(slides, by_id) -> str:
    lines = []

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

    return "\n".join(lines) + "\n"


# --- entry point ------------------------------------------------------------ #
def pptx_converter(file_path, output_dir=None, *, model=DEFAULT_MODEL,
                   max_workers=DEFAULT_MAX_WORKERS, prompt=IMAGE_PROMPT,
                   data_type=None, client=None, describe=True) -> str:
    path, kind = validate_file(file_path)
    registry = ImageRegistry()
    slides, file_meta = parse(path, kind, registry)          # Spire for both formats

    images = registry.images
    if images and describe:
        client = client or llm.get_azure_openai_client()
        llm.describe_images(images, model=model, max_workers=max_workers, prompt=prompt, client=client)

    by_id = {image.image_id: image for image in images}

    return render_xml(slides, by_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert .ppt/.pptx to placeholder XML (Spire-only).")
    parser.add_argument("file", type=Path, help=".ppt or .pptx file")
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
        xml = pptx_converter(args.file, model=model, client=client,
                             data_type=args.data_type, describe=not args.no_describe)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(xml)                                       # XML on stdout; logs go to stderr


if __name__ == "__main__":
    main()
