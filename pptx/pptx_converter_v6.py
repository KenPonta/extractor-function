"""pptx_converter_v6.py — .pptx -> semantic XML, parsed ENTIRELY with python-pptx.

v6 is v5 with the .ppt path removed: no Spire, no sharepoint2text — just python-pptx, the
same single-library approach as pptx_converter_v4's .pptx branch. It walks the shape tree in
reading order (recursing into groups; pulling text frames, picture shapes, picture-fill
autoshapes, and tables). Each image becomes a <figure> placeholder replaced by its LLM
description at render time.

Output mirrors pptx_converter_v5:
    <slide number="1"><text>…</text><figure id="1">description</figure></slide>

Vision client via --provider: 'openai' (dev box, gpt-4.1) or 'azure' (real device, deployment
name); default azure so a production pull runs unchanged. All Azure/LLM config lives in llm_ref.py.
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

MSO_FILL_PICTURE = 6                # python-pptx fill type id for a picture fill
RASTER_EXT = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}   # anything else is treated as vector
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
def validate_file(file_path) -> Path:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if path.suffix.lower() != ".pptx":
        raise ValueError(f"unsupported file type: {path.name} (expected .pptx)")
    return path


def xml_attr(value) -> str:
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def xml_text(value) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def doc_name(data_type, index, file_path) -> str:
    """Generated filename attr (NOT the real name): '<type>_<index>_<hash>.txt'."""
    digest = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()[:24]
    return f"{data_type.lower()}_{index}_{digest}.txt"


def _pptx_metadata(prs) -> dict:
    cp = prs.core_properties
    return {"title": cp.title or "", "author": cp.author or "", "subject": cp.subject or "",
            "keywords": cp.keywords or "", "last_modified_by": cp.last_modified_by or "",
            "created": cp.created.isoformat() if cp.created else "",
            "modified": cp.modified.isoformat() if cp.modified else "",
            "revision": str(cp.revision) if cp.revision else ""}


def log_parse(slides, registry, skipped_vector=0, skipped_small=0):
    placements = sum(k == "image" for s in slides for k, _ in s.blocks)
    logger.info("pptx: %d slides, %d images, %d placements, %d vector + %d small skipped",
                len(slides), len(registry.images), placements, skipped_vector, skipped_small)


# --- python-pptx parsing ---------------------------------------------------- #
def _sort_key(shape) -> tuple[int, int]:
    """Reading order: top-to-bottom, then left-to-right (guard missing coords)."""
    top = shape.top if isinstance(shape.top, int) else 0
    left = shape.left if isinstance(shape.left, int) else 0
    return top, left


def _embed_image(shape):
    """(blob, ext, width, height) for a picture shape, else None.

    Covers both python-pptx picture forms: a real PICTURE shape, and an autoshape whose fill is
    a picture (charts pasted as a fill) — the blip is dug out of the shape XML.
    """
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from pptx.oxml.ns import qn
    try:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            image = shape.image
            w, h = image.size
            return image.blob, image.ext.lower(), w, h
        if int(shape.fill.type) == MSO_FILL_PICTURE:
            blip = shape._element.find(".//" + qn("a:blip"))
            if blip is not None:
                part = shape.part.related_part(blip.get(qn("r:embed")))
                blob = part.blob
                ext = part.partname.ext.lower() if hasattr(part.partname, "ext") \
                    else str(part.partname).rsplit(".", 1)[-1].lower()
                return blob, ext, *_dims(blob)
    except Exception:
        return None
    return None


def _dims(blob: bytes) -> tuple[int, int]:
    """Pixel size of an image blob; (0, 0) when it can't be decoded (skips the size filter)."""
    try:
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(blob)) as im:
            return im.size
    except Exception:
        return 0, 0


def _table_rows(table) -> list:
    """Flatten a python-pptx table to 'a | b | c' rows."""
    return [" | ".join(c.text.strip() for c in row.cells)
            for row in table.rows if any(c.text.strip() for c in row.cells)]


def _blocks(shapes, registry, stats):
    """Walk shapes in reading order, recursing groups; yield ('text', str) / ('image', id)."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    for shape in sorted(shapes, key=_sort_key):
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _blocks(shape.shapes, registry, stats)
            continue

        info = _embed_image(shape)
        if info is not None:                                 # image
            blob, ext, w, h = info
            if ext not in RASTER_EXT:
                stats["vector"] += 1
            elif MIN_IMAGE_DIM and w and h and min(w, h) < MIN_IMAGE_DIM:
                stats["small"] += 1
            else:
                yield "image", registry.register(blob, ext)
            continue

        if getattr(shape, "has_table", False):               # table
            rows = _table_rows(shape.table)
            if rows:
                yield "text", "\n".join(rows)
            continue

        if getattr(shape, "has_text_frame", False):          # text
            text = shape.text_frame.text.strip()
            if text:
                yield "text", text


def parse(path, registry) -> tuple:
    """Parse a .pptx into Slides via python-pptx only. Return (list[Slide], metadata)."""
    from pptx import Presentation
    prs = Presentation(str(path))
    stats = {"vector": 0, "small": 0}
    slides = [Slide(n, list(_blocks(slide.shapes, registry, stats)))
              for n, slide in enumerate(prs.slides, start=1)]
    log_parse(slides, registry, stats["vector"], stats["small"])
    return slides, _pptx_metadata(prs)


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
    path = validate_file(file_path)
    registry = ImageRegistry()
    slides, file_meta = parse(path, registry)                # python-pptx only

    images = registry.images
    if images and describe:
        client = client or llm.get_azure_openai_client()
        llm.describe_images(images, model=model, max_workers=max_workers, prompt=prompt, client=client)

    by_id = {image.image_id: image for image in images}

    return render_xml(slides, by_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert .pptx to placeholder XML (python-pptx only).")
    parser.add_argument("file", type=Path, help=".pptx file")
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
