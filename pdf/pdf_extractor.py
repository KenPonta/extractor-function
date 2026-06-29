"""PDF -> placeholder-XML extractor, built on opendataloader-pdf.

Pipeline (no data leaves the machine except through your sanctioned Azure describer):

    opendataloader (local Java engine)        your code (unchanged)
    ----------------------------------        ---------------------
    PDF --> structured JSON + image files --> describe images via
            (text, tables, headings,          safe_describe_image_with_llm
             image refs + bounding boxes)      (Azure, your one egress)
                                          --> <documents> XML

opendataloader runs in local mode: layout analysis, reading order, table structure, and
image extraction with zero network egress (bundled JAR, no telemetry). It does NOT
describe images here -- that stays on your Azure channel so the PDF corpus matches your
DOC/DOCX output (same prompt, same provenance, same quality).

Three behaviours are driven by what opendataloader actually emits:
  * Tables arrive as nested rows/cells and are rendered as ' | '-joined rows.
  * The same picture on N pages is written as N files; images are de-duplicated by
    SHA-256 (the same hash you already use for provenance), so each is described once.
  * Vector-only pages (charts drawn with path operators, no text, no raster) come back
    empty from local mode; an optional PyMuPDF page-render fallback rasterizes them so no
    page is silently dropped. Genuinely scanned pages already arrive as a full-page image
    and are transcribed via the page describer.

INTEGRATION POINTS (search for "INTEGRATION"):
  1. _DESCRIBER_MODULE -- import path of the module you pasted
     (safe_describe_image_with_llm, get_azure_openai_client, get_image_file_metadata, ...).
  2. render_image_item() -- the one place that emits an image's XML; align its tag and
     attributes with however your DOC/DOCX extractors write their image items.
  3. Page transcription prompt/limits live here (PAGE_PROMPT, PAGE_MAX_TOKENS) rather than
     in your shared describer, so DOC/DOCX behaviour is untouched. Move them into the
     shared module instead if you'd rather have one describer for everything.
"""

import argparse
import hashlib
import json
import logging
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path

logger = logging.getLogger(__name__)

# INTEGRATION 1: where your pasted helpers live (safe_describe_image_with_llm,
# get_azure_openai_client, encode_image_to_data_url, get_image_file_metadata,
# get_required_env, DocumentExtractionError). Adjust to your project's layout.
_DESCRIBER_MODULE = "document_utils.image_description"

DEFAULT_DATA_TYPE = "PDF"
DEFAULT_MAX_WORKERS = 8
DEFAULT_IMAGE_FORMAT = "png"   # png keeps lossless detail and passes your MIME gate
FALLBACK_DPI = 200             # DPI for the PyMuPDF render of empty/vector-only pages

# Transcription prompt for a whole page (a scan or a fallback-rendered page). Distinct
# from your figure prompt: a page needs full OCR + structure, not a one-line summary.
PAGE_PROMPT = (
    "You are transcribing a full page rendered from a PDF. Output the page's text exactly "
    "as it appears, preserving reading order and structure: keep headings, paragraphs, and "
    "lists, and render any table as rows of cells separated by ' | '. For any chart or "
    "figure, add a short plain-text note of what it shows (title, axes, series, trend). If "
    "the page is blank, reply with exactly: (blank page). Return XML-safe text only, with "
    "no markdown and no code fences."
)
PAGE_MAX_TOKENS = 4000


# --- describers ------------------------------------------------------------- #
def _figure_describer(image_path: str) -> str:
    """Your sanctioned figure describer (resize + concise description, on Azure)."""
    return import_module(_DESCRIBER_MODULE).safe_describe_image_with_llm(image_path)


def describe_page_with_llm(image_path) -> str:
    """Transcribe a full page image, reusing your Azure client and encoder.

    Kept here (not in the shared module) so your DOC/DOCX figure path is untouched. It
    reuses get_azure_openai_client / encode_image_to_data_url and only swaps the prompt,
    token budget, and detail level for transcription. The page image is NOT downsized --
    full resolution matters for OCR.
    """
    mod = import_module(_DESCRIBER_MODULE)
    client = mod.get_azure_openai_client()
    image_data_url = mod.encode_image_to_data_url(image_path)  # enforces png/jpeg/webp
    response = client.responses.create(
        model=mod.get_required_env("AZURE_OPENAI_DEPLOYMENT"),
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": PAGE_PROMPT},
            {"type": "input_image", "image_url": image_data_url, "detail": "high"},
        ]}],
        max_output_tokens=PAGE_MAX_TOKENS,
        temperature=0.0,
    )
    return (response.output_text or "").strip()


def _page_describer(image_path: str) -> str:
    """Transcribe a page, but never abort extraction (mirrors your safe_* wrapper)."""
    try:
        return describe_page_with_llm(image_path)
    except Exception as exc:
        logger.warning("page transcription failed for %s: %s", image_path, exc)
        return ""


def _file_metadata(image_path: str):
    """(sha256, size_bytes) for an image. Uses your helper when importable, else stdlib."""
    try:
        meta = import_module(_DESCRIBER_MODULE).get_image_file_metadata(image_path)
        return meta["sha256"], meta["size_bytes"]
    except Exception:
        blob = Path(image_path).read_bytes()
        return hashlib.sha256(blob).hexdigest(), str(len(blob))


# --- data model ------------------------------------------------------------- #
@dataclass
class ImageRef:
    image_id: int
    path: str
    sha256: str
    size_bytes: str
    kind: str             # "figure" (embedded picture) | "page" (full-page scan/render)
    description: str = ""


@dataclass
class Page:
    number: int
    blocks: list = field(default_factory=list)  # ("text", str) | ("image", image_id)


@dataclass
class ImageRegistry:
    """De-duplicates images by SHA-256 so identical pictures are described once."""

    by_sha: dict = field(default_factory=dict)

    def register(self, path: str, kind: str) -> int:
        sha, size = _file_metadata(path)
        ref = self.by_sha.get(sha)
        if ref is None:
            ref = ImageRef(len(self.by_sha) + 1, path, sha, size, kind)
            self.by_sha[sha] = ref
        return ref.image_id

    @property
    def images(self) -> list:
        return list(self.by_sha.values())


# --- opendataloader front-end ----------------------------------------------- #
def run_opendataloader(pdf_path: Path, work_dir: Path, *, sanitize: bool = False,
                       use_struct_tree: bool = False, include_header_footer: bool = False,
                       image_format: str = DEFAULT_IMAGE_FORMAT) -> dict:
    """Run local-mode extraction and return the parsed JSON.

    Content-safety filters (hidden text, off-page, tiny, hidden-OCG) stay ON, which strips
    prompt-injection payloads before any text reaches your model. `sanitize` additionally
    masks emails/phones/IPs/cards/URLs in the extracted text.

    NOTE: header/footer filtering is ON by default (include_header_footer=False) -- running
    headers, footers, and page numbers are dropped, which is usually what you want for RAG.
    The catch: on a sparse page a lone line in the top/bottom margin can be misread as a
    header and removed. Set include_header_footer=True to keep them (they then arrive as
    `header`/`footer` elements, which this parser folds into the page text).
    """
    import opendataloader_pdf

    opendataloader_pdf.convert(
        input_path=[str(pdf_path)],
        output_dir=str(work_dir),
        format="json",
        image_output="external",   # write image files; your describer takes a path
        image_format=image_format,
        sanitize=sanitize,
        use_struct_tree=use_struct_tree,
        include_header_footer=include_header_footer,
        quiet=True,
    )
    json_path = work_dir / f"{pdf_path.stem}.json"
    if not json_path.exists():
        raise RuntimeError(f"opendataloader produced no JSON for {pdf_path.name}")
    return json.loads(json_path.read_text(encoding="utf-8"))


# --- JSON -> blocks --------------------------------------------------------- #
def gather_text(node: dict) -> str:
    """Collect text from a node and its descendants (used for table cells, containers)."""
    parts = []
    content = node.get("content")
    if isinstance(content, str) and content.strip():
        parts.append(content.strip())
    for kid in node.get("kids", []):
        kind = kid.get("type")
        if kind == "image":
            continue
        parts.append(render_table(kid) if kind == "table" else gather_text(kid))
    return " ".join(p for p in parts if p).strip()


def render_table(node: dict) -> str:
    """Render a table element (nested rows/cells) as ' | '-joined rows."""
    lines = []
    for row in node.get("rows", []):
        cells = [gather_text(cell) for cell in row.get("cells", [])]
        if any(c.strip() for c in cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines) if lines else gather_text(node)


def _first_page(node: dict):
    if node.get("page number") is not None:
        return node["page number"]
    for kid in node.get("kids", []):
        page = _first_page(kid)
        if page is not None:
            return page
    return None


def walk_blocks(node: dict):
    """Yield (page_number, kind, value) in reading order.

    kind is "text" (value=str) or "imgpath" (value=source path relative to the JSON dir).
    Tables and images are emitted whole; containers are recursed into.
    """
    node_type = node.get("type")
    if node_type == "image":
        source = node.get("source")
        if source:
            yield node.get("page number"), "imgpath", source
        return
    if node_type == "table":
        text = render_table(node)
        if text:
            yield _first_page(node), "text", text
        return
    content = node.get("content")
    if isinstance(content, str) and content.strip():
        yield node.get("page number"), "text", content.strip()
        return
    for kid in node.get("kids", []):
        yield from walk_blocks(kid)


def build_pages(doc_json: dict, json_dir: Path, registry: ImageRegistry, pdf_path: Path,
                fallback: bool) -> list:
    """Turn opendataloader JSON into Pages, classifying scanned/figure/empty pages.

    A page with images but no text is treated as scanned (images -> "page" transcription).
    A page with text treats its images as figures. A page with no elements at all is
    rendered whole via PyMuPDF (if `fallback`) so vector-only pages aren't lost.
    """
    raw = defaultdict(list)
    for page, kind, value in walk_blocks(doc_json):
        raw[page if page is not None else 1].append((kind, value))

    total = int(doc_json.get("number of pages") or (max(raw) if raw else 0))
    pages = []
    for number in range(1, total + 1):
        items = raw.get(number, [])
        has_text = any(kind == "text" for kind, _ in items)
        blocks = []

        if not items:
            if fallback:
                rendered = render_page_png(pdf_path, number, json_dir)
                if rendered is not None:
                    blocks.append(("image", registry.register(str(rendered), "page")))
        else:
            for kind, value in items:
                if kind == "text":
                    blocks.append(("text", value))
                else:
                    img_kind = "figure" if has_text else "page"
                    path = (json_dir / value).resolve()
                    blocks.append(("image", registry.register(str(path), img_kind)))

        pages.append(Page(number, blocks))
    return pages


def render_page_png(pdf_path: Path, page_number: int, out_dir: Path,
                    dpi: int = FALLBACK_DPI):
    """Rasterize one page to PNG (fallback for vector-only / empty pages)."""
    try:
        import fitz
    except Exception:
        logger.warning("PyMuPDF not available; cannot render empty page %d", page_number)
        return None
    with fitz.open(str(pdf_path)) as doc:
        pix = doc[page_number - 1].get_pixmap(dpi=dpi)
        out = out_dir / f"fallback_page_{page_number}.png"
        pix.save(str(out))
    return out


# --- describe + render ------------------------------------------------------ #
def describe_images(registry: ImageRegistry, figure_describer, page_describer,
                    max_workers: int):
    """Fill each image's description via the right describer (concurrent)."""
    images = registry.images
    if not images:
        return
    workers = min(max_workers, len(images))
    logger.info("describing %d unique images via Azure (%d concurrent)", len(images), workers)

    def run(ref: ImageRef):
        describer = page_describer if ref.kind == "page" else figure_describer
        ref.description = describer(ref.path) or ""

    with ThreadPoolExecutor(max_workers=workers) as pool:
        pool.map(run, images)


def xml_attr(value) -> str:
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def render_image_item(ref: ImageRef) -> str:
    """INTEGRATION 2: emit one image's XML.

    Align this element's tag and attributes with your DOC/DOCX image items so the PDF
    output is byte-compatible with the rest of the corpus. Descriptions are produced
    XML-safe by the prompt, so they're inlined as-is.
    """
    return (f'<image id="{ref.image_id}" sha256="{ref.sha256}" '
            f'size_bytes="{ref.size_bytes}">'
            f'{ref.description or "(no description)"}'
            f'</image>')


def render_xml(pages: list, by_id: dict, filename: str, data_type: str,
               index: int = 1) -> str:
    page_texts = []
    for page in pages:
        parts = [f"Page {page.number}"]
        for kind, value in page.blocks:
            if kind == "text":
                parts.append(value)
            else:
                ref = by_id[value]
                # A scanned/rendered page's transcription IS the page body; a figure is
                # wrapped as an <image> item alongside the surrounding text.
                parts.append(ref.description or "(no description)" if ref.kind == "page"
                             else render_image_item(ref))
        page_texts.append("\n\n".join(parts))
    body = "\n\n".join(page_texts)

    return (
        "<documents>\n"
        f'  <document index="{index}" filename="{xml_attr(filename)}"'
        f' data-type="{xml_attr(data_type)}">\n'
        f"{body}\n"
        "  </document>\n"
        "</documents>\n"
    )


# --- public entry point ----------------------------------------------------- #
def pdf_converter(file_path, output_dir=None, *, data_type: str = DEFAULT_DATA_TYPE,
                  max_workers: int = DEFAULT_MAX_WORKERS, fallback: bool = True,
                  sanitize: bool = False, use_struct_tree: bool = False,
                  include_header_footer: bool = False,
                  figure_describer=_figure_describer, page_describer=_page_describer) -> str:
    """Convert a .pdf to placeholder XML using opendataloader + your Azure describer.

    Args:
        file_path: path to a .pdf.
        output_dir: if given, the XML is also written to ``<output_dir>/<stem>.xml``.
        data_type: value for the document's ``data-type`` attribute.
        max_workers: max concurrent Azure description requests.
        fallback: render empty/vector-only pages with PyMuPDF so none are dropped.
        sanitize: mask emails/phones/IPs/cards/URLs in extracted text (opendataloader).
        use_struct_tree: trust the PDF's tag tree for structure when present.
        include_header_footer: keep running headers/footers (default drops them; see
            run_opendataloader for the sparse-page caveat).
        figure_describer / page_describer: callables(path)->str. Defaults call your
            safe_describe_image_with_llm and the page-transcription wrapper here; swap
            them (e.g. for tests, or a fully-local model) without touching the pipeline.

    Returns:
        The rendered <documents> XML string.
    """
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"file not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"unsupported file type: {pdf_path.name} (expected .pdf)")

    # opendataloader writes the JSON and image files here; cleaned up on exit. Pass a
    # persistent dir instead if you want to keep the extracted images.
    with tempfile.TemporaryDirectory(prefix="odl_") as tmp:
        work_dir = Path(tmp)
        doc_json = run_opendataloader(pdf_path, work_dir, sanitize=sanitize,
                                      use_struct_tree=use_struct_tree,
                                      include_header_footer=include_header_footer)
        registry = ImageRegistry()
        pages = build_pages(doc_json, work_dir, registry, pdf_path, fallback)
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
                                                 "(opendataloader + Azure describer).")
    parser.add_argument("file", type=Path, help=".pdf file")
    parser.add_argument("-o", "--out", type=Path, default="output", help="output directory")
    parser.add_argument("--data-type", default=DEFAULT_DATA_TYPE)
    parser.add_argument("--sanitize", action="store_true", help="mask PII in extracted text")
    parser.add_argument("--struct-tree", action="store_true", help="use PDF tag tree")
    parser.add_argument("--keep-header-footer", action="store_true",
                        help="keep running headers/footers (default: drop them)")
    parser.add_argument("--no-fallback", action="store_true",
                        help="don't render empty/vector-only pages")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        pdf_converter(args.file, args.out, data_type=args.data_type, sanitize=args.sanitize,
                      use_struct_tree=args.struct_tree, fallback=not args.no_fallback,
                      include_header_footer=args.keep_header_footer)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()