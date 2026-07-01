"""PDF -> placeholder-XML extractor built directly on PyMuPDF (no opendataloader).

WHAT IT DOES
    Reads a PDF locally with PyMuPDF (fitz): pulls the text and the embedded images
    per page, in reading order, then sends the images to an Azure OpenAI vision model
    for description/transcription and emits a <documents> XML (text + <image> items).

THREE THINGS IT HANDLES ON PURPOSE
    1. Normal pages         -> text blocks + embedded figures, interleaved in reading order.
    2. Scanned / vector /   -> the whole page is rendered to a PNG and transcribed (OCR-style),
       blank pages             because there is no selectable text to pull.
    3. Figures split across -> a picture whose top half sits at the bottom of page N and whose
       a page break            bottom half sits at the top of page N+1 is detected by edge +
                               horizontal-alignment heuristics, stitched back into one image,
                               and described once.

The only network egress is the Azure describer. Everything else is local.
See PDF_EXTRACTOR.md for the full walkthrough.
"""

import argparse
import base64
import hashlib
import io
import logging
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# --- config ----------------------------------------------------------------- #
DEFAULT_DATA_TYPE = "PDF"
DEFAULT_MAX_WORKERS = 8              # concurrent Azure describe/transcribe requests
IMAGE_DETAIL = "high"               # vision detail level
PAGE_RENDER_DPI = 200               # DPI for rendering whole (scanned/vector) pages

MIN_FIGURE_DIM = 64                 # px: drop embedded images smaller than this (icons/rules)
SCANNED_TEXT_MAX_CHARS = 20         # <= this much selectable text => page is likely a scan
SCANNED_IMAGE_COVER = 0.60          # image area >= 60% of the page => page is likely a scan
EDGE_TOL_FRAC = 0.06                # within 6% of a page edge counts as "touching" that edge
X_ALIGN_TOL_FRAC = 0.05             # split halves must line up horizontally within 5% of width

FIGURE_PROMPT = (
    "This image was taken from a PDF. If it is a chart, graph, table, diagram, or figure, "
    "describe its content as plain text: title, axis labels and ranges, legend/series, and "
    "the data, trends, or relationships it conveys. If it is a logo, icon, or purely "
    "decorative graphic with no information, reply with exactly: (decorative, no data). Do "
    "not invent anything not visible, and return XML-safe text with no markdown or code fence."
)

PAGE_PROMPT = (
    "You are transcribing a full page rendered from a PDF. Output the page's text exactly as "
    "it appears, preserving reading order and structure: keep headings, paragraphs, and lists, "
    "and render any table as rows of cells separated by ' | '. For any chart or figure, add a "
    "short plain-text note of what it shows (title, axes, series, trend). If the page is blank, "
    "reply with exactly: (blank page). Return XML-safe text only, with no markdown or code fence."
)


# --- Azure OpenAI layer (mirrors pptx/llm_ref.py) --------------------------- #
# Functionality: Load KEY=value lines from the nearest .env into os.environ (once, at import).
# Return: None.
# Used by: module import, so get_required_env() finds AZURE_OPENAI_* during local runs.
def _load_dotenv() -> None:
    for directory in (Path.cwd(), *Path(__file__).resolve().parents):
        env_file = directory / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            break

_load_dotenv()


# Custom exception for LLM call errors
class LLMError(RuntimeError):
    """Raised when a required setting is missing or an Azure call cannot be completed."""

# Functionality: Read a required environment variable and validate that it exists.
# Return: The environment variable value as a string.
# Used by: get_azure_openai_client() and the describer functions (for the deployment name).
def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise LLMError(f"Missing required environment variable: {name}")
    return value

# Functionality: Build (and cache) an authenticated Azure OpenAI client from env settings.
# Return: A configured AzureOpenAI client, reused across all images in a run.
# Used by: describe_figure() and transcribe_page().
@lru_cache(maxsize=1)
def get_azure_openai_client():
    from openai import AzureOpenAI
    return AzureOpenAI(
        azure_endpoint=get_required_env("AZURE_OPENAI_ENDPOINT"),
        api_key=get_required_env("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    )

# Functionality: Encode raw image bytes as a base64 data URL for vision input.
# Return: A "data:image/...;base64,..." string.
# Used by: describe_figure() and transcribe_page().
def encode_image_to_data_url(blob: bytes, ext: str) -> str:
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext if ext in ("png", "gif", "webp") else "png")
    return f"data:image/{mime};base64,{base64.b64encode(blob).decode('ascii')}"

# Functionality: Send one image + a prompt to the Azure vision model and return its reply.
# Return: The model's text reply, stripped.
# Used by: describe_figure() and transcribe_page() (they only differ by prompt).
def _describe(blob: bytes, ext: str, prompt: str) -> str:
    response = get_azure_openai_client().chat.completions.create(
        model=get_required_env("AZURE_OPENAI_DEPLOYMENT"),
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": encode_image_to_data_url(blob, ext), "detail": IMAGE_DETAIL}},
        ]}])
    return (response.choices[0].message.content or "").strip()

# Functionality: Concise description of an embedded figure (chart/table/diagram).
# Return: A short plain-text description.
# Used by: describe_images() for images classified as "figure".
def describe_figure(blob: bytes, ext: str) -> str:
    return _describe(blob, ext, FIGURE_PROMPT)

# Functionality: Full-page transcription of a rendered scanned/vector page.
# Return: The page's transcribed text + figure notes.
# Used by: describe_images() for images classified as "page".
def transcribe_page(blob: bytes, ext: str) -> str:
    return _describe(blob, ext, PAGE_PROMPT)


# --- data model ------------------------------------------------------------- #
@dataclass
class ImageRef:
    image_id: int
    blob: bytes
    ext: str
    sha256: str
    size_bytes: str
    kind: str              # "figure" (embedded picture) | "page" (rendered whole page)
    description: str = ""


@dataclass
class Page:
    number: int
    blocks: list = field(default_factory=list)  # ("text", str) | ("image", image_id)


@dataclass
class ImageRegistry:
    """De-duplicates images by SHA-256 so an identical picture is described only once."""
    by_sha: dict = field(default_factory=dict)

    def register(self, blob: bytes, ext: str, kind: str) -> int:
        sha = hashlib.sha256(blob).hexdigest()
        ref = self.by_sha.get(sha)
        if ref is None:
            ref = self.by_sha[sha] = ImageRef(len(self.by_sha) + 1, blob, ext,
                                              sha, str(len(blob)), kind)
        return ref.image_id

    @property
    def images(self) -> list:
        return list(self.by_sha.values())


# --- PyMuPDF extraction ----------------------------------------------------- #
# Functionality: Join the text of a "dict" text block into one string (lines preserved).
# Return: The block's text, or "".
# Used by: _extract_page().
def _block_text(block: dict) -> str:
    lines = []
    for line in block.get("lines", []):
        text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


# Functionality: Pull one page's text blocks and image blocks, and classify the page.
# Return: (text_blocks, image_blocks, is_scanned, is_empty, (page_w, page_h)) where
#         text_blocks = [(y0, x0, text)], image_blocks = [{bbox, blob, ext, w, h}].
# Used by: build_pages().
def _extract_page(page) -> tuple:
    data = page.get_text("dict")
    pw, ph = page.rect.width, page.rect.height
    text_blocks, image_blocks = [], []
    text_len, image_area = 0, 0.0
    for block in data.get("blocks", []):
        x0, y0, x1, y1 = block["bbox"]
        if block["type"] == 0:                                  # text block
            text = _block_text(block)
            if text:
                text_blocks.append((y0, x0, text))
                text_len += len(text)
        elif block["type"] == 1 and block.get("image"):         # image block (bytes inline)
            image_blocks.append({"bbox": (x0, y0, x1, y1), "blob": block["image"],
                                 "ext": block.get("ext", "png"),
                                 "w": block.get("width", 0), "h": block.get("height", 0)})
            image_area += max(0.0, x1 - x0) * max(0.0, y1 - y0)
    page_area = (pw * ph) or 1.0
    is_scanned = text_len <= SCANNED_TEXT_MAX_CHARS and (image_area / page_area) >= SCANNED_IMAGE_COVER
    is_empty = text_len == 0 and not image_blocks
    return text_blocks, image_blocks, is_scanned, is_empty, (pw, ph)


# Functionality: Render a whole page to PNG bytes (for scanned/vector/empty pages).
# Return: PNG bytes.
# Used by: build_pages() when a page is transcribed as a whole.
def render_page_png(page, dpi: int = PAGE_RENDER_DPI) -> bytes:
    return page.get_pixmap(dpi=dpi).tobytes("png")


# Functionality: Stack two image halves vertically into one PNG (top piece over bottom piece).
# Return: PNG bytes of the stitched image.
# Used by: build_pages() when a split figure is detected across a page break.
def stitch_vertical(top_blob: bytes, bottom_blob: bytes) -> bytes:
    from PIL import Image
    top = Image.open(io.BytesIO(top_blob)).convert("RGB")
    bottom = Image.open(io.BytesIO(bottom_blob)).convert("RGB")
    width = max(top.width, bottom.width)                        # normalize to the wider half
    def _scaled(im):
        return im if im.width == width else im.resize((width, round(im.height * width / im.width)))
    top, bottom = _scaled(top), _scaled(bottom)
    canvas = Image.new("RGB", (width, top.height + bottom.height), "white")
    canvas.paste(top, (0, 0))
    canvas.paste(bottom, (0, top.height))
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue()


# Functionality: Find figures split across consecutive page breaks (bottom of N + top of N+1).
# Return: list of (page_n, idx_top_half, page_n+1, idx_bottom_half).
# Used by: build_pages().
def detect_split_pairs(page_images: dict, page_sizes: dict) -> list:
    pairs = []
    for n in sorted(page_images):
        nxt = n + 1
        if nxt not in page_images:
            continue
        (wn, hn), (_, hn1) = page_sizes[n], page_sizes[nxt]
        for i, top in enumerate(page_images[n]):
            ax0, ay0, ax1, ay1 = top["bbox"]
            if (hn - ay1) > EDGE_TOL_FRAC * hn:                 # top half must hug page N's bottom
                continue
            for j, bot in enumerate(page_images[nxt]):
                bx0, by0, bx1, by1 = bot["bbox"]
                if by0 > EDGE_TOL_FRAC * hn1:                   # bottom half must hug N+1's top
                    continue
                if abs(ax0 - bx0) <= X_ALIGN_TOL_FRAC * wn and abs(ax1 - bx1) <= X_ALIGN_TOL_FRAC * wn:
                    pairs.append((n, i, nxt, j))                # aligned horizontally -> same figure
                    break
    return pairs


# Functionality: Turn a PDF into Pages of ("text"/"image") blocks in reading order, applying
#                scanned-page transcription and split-figure stitching. Registers every image.
# Return: list[Page].
# Used by: pdf_converter().
def build_pages(doc, registry: ImageRegistry, *, fallback: bool = True) -> list:
    n_pages = doc.page_count

    # 1) Extract raw content and classify each page.
    per_page = {}
    for i in range(n_pages):
        tb, ib, scanned, empty, size = _extract_page(doc[i])
        per_page[i + 1] = {"text": tb, "images": ib, "scanned": scanned,
                           "empty": empty, "size": size}

    # 2) Detect + stitch figures split across page breaks (only among non-scanned pages).
    page_images = {n: pp["images"] for n, pp in per_page.items() if not pp["scanned"]}
    sizes = {n: pp["size"] for n, pp in per_page.items()}
    consumed, stitched = set(), defaultdict(list)
    for n, i, m, j in detect_split_pairs(page_images, sizes):
        if (n, i) in consumed or (m, j) in consumed:
            continue
        top, bottom = per_page[n]["images"][i], per_page[m]["images"][j]
        stitched[n].append({"bbox": top["bbox"],
                            "blob": stitch_vertical(top["blob"], bottom["blob"]), "ext": "png"})
        consumed.update({(n, i), (m, j)})
        logger.info("stitched a figure split across pages %d-%d", n, m)

    # 3) Assemble pages.
    pages = []
    for n in range(1, n_pages + 1):
        pp = per_page[n]
        blocks = []
        if pp["scanned"] or (pp["empty"] and fallback):         # whole page -> transcribe
            png = render_page_png(doc[n - 1])
            blocks.append(("image", registry.register(png, "png", "page")))
            pages.append(Page(n, blocks))
            continue

        items = [(y0, x0, "text", text) for (y0, x0, text) in pp["text"]]
        for idx, im in enumerate(pp["images"]):                 # embedded figures
            if (n, idx) in consumed:
                continue
            if min(im["w"], im["h"]) < MIN_FIGURE_DIM:          # drop tiny icons/rules
                continue
            items.append((im["bbox"][1], im["bbox"][0], "figure", im))
        for im in stitched.get(n, []):                          # stitched split figures
            items.append((im["bbox"][1], im["bbox"][0], "figure", im))

        items.sort(key=lambda t: (t[0], t[1]))                  # reading order: top->bottom, left->right
        for _, _, kind, payload in items:
            if kind == "text":
                blocks.append(("text", payload))
            else:
                blocks.append(("image", registry.register(payload["blob"], payload["ext"], "figure")))
        pages.append(Page(n, blocks))
    return pages


# --- describe + render ------------------------------------------------------ #
# Functionality: Fill each unique image's .description via the right describer, concurrently.
# Return: None (mutates ImageRef.description).
# Used by: pdf_converter().
def describe_images(registry: ImageRegistry, figure_describer, page_describer, max_workers: int):
    images = registry.images
    if not images:
        return
    workers = min(max_workers, len(images))
    logger.info("describing %d unique images via Azure (%d concurrent)", len(images), workers)

    def run(ref: ImageRef):
        describer = page_describer if ref.kind == "page" else figure_describer
        try:
            ref.description = (describer(ref.blob, ref.ext) or "").strip()
        except Exception as exc:
            logger.warning("describe failed for image %d (%s): %s", ref.image_id, ref.kind, exc)
            ref.description = f"[description failed: {exc}]"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        pool.map(run, images)


def xml_attr(value) -> str:
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


# Functionality: Emit one embedded figure's XML element.
# Return: an <image> element string.
# Used by: render_xml().
def render_image_item(ref: ImageRef) -> str:
    return (f'<image id="{ref.image_id}" sha256="{ref.sha256}" size_bytes="{ref.size_bytes}">'
            f'{ref.description or "(no description)"}</image>')


# Functionality: Render all pages into the final <documents> XML.
# Return: the XML string.
# Used by: pdf_converter().
def render_xml(pages: list, by_id: dict, filename: str, data_type: str, index: int = 1) -> str:
    page_texts = []
    for page in pages:
        parts = [f"Page {page.number}"]
        for kind, value in page.blocks:
            if kind == "text":
                parts.append(value)
            else:
                ref = by_id[value]
                # A whole-page transcription IS the page body; a figure is an <image> item.
                parts.append(ref.description or "(no description)" if ref.kind == "page"
                             else render_image_item(ref))
        page_texts.append("\n\n".join(parts))
    body = "\n\n".join(page_texts)
    return (f'<documents>\n  <document index="{index}" filename="{xml_attr(filename)}"'
            f' data-type="{xml_attr(data_type)}">\n{body}\n  </document>\n</documents>\n')


# --- public entry point ----------------------------------------------------- #
def pdf_converter(file_path, output_dir=None, *, data_type: str = DEFAULT_DATA_TYPE,
                  max_workers: int = DEFAULT_MAX_WORKERS, fallback: bool = True,
                  figure_describer=describe_figure, page_describer=transcribe_page) -> str:
    """Convert a .pdf to placeholder XML using PyMuPDF + an Azure describer.

    Args:
        file_path: path to a .pdf.
        output_dir: if given, also write the XML to ``<output_dir>/<stem>.xml``.
        data_type: value for the document's ``data-type`` attribute.
        max_workers: max concurrent Azure requests.
        fallback: also render+transcribe empty/vector-only pages (scanned pages are always
            transcribed regardless).
        figure_describer / page_describer: callables(blob, ext) -> str. Default to the Azure
            describers above; swap for stubs in tests or a local model.

    Returns:
        The rendered <documents> XML string.
    """
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"file not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"unsupported file type: {pdf_path.name} (expected .pdf)")

    with fitz.open(str(pdf_path)) as doc:
        registry = ImageRegistry()
        pages = build_pages(doc, registry, fallback=fallback)
        describe_images(registry, figure_describer, page_describer, max_workers)
        by_id = {ref.image_id: ref for ref in registry.images}
        xml = render_xml(pages, by_id, pdf_path.name, data_type=data_type)

    if output_dir is not None:
        out_path = Path(output_dir) / f"{pdf_path.stem}.xml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml, encoding="utf-8")
        logger.info("written to %s", out_path)
    return xml


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert a .pdf to placeholder XML "
                                                 "(PyMuPDF + Azure describer).")
    parser.add_argument("file", type=Path, help=".pdf file")
    parser.add_argument("-o", "--out", type=Path, default="output", help="output directory")
    parser.add_argument("--data-type", default=DEFAULT_DATA_TYPE)
    parser.add_argument("--no-fallback", action="store_true",
                        help="don't render empty/vector-only pages (scanned pages still transcribed)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        pdf_converter(args.file, args.out, data_type=args.data_type, fallback=not args.no_fallback)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
