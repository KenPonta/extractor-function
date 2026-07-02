# PDF Extractor (`pdf/pdf_extractor.py`)

Converts a `.pdf` into **flat, semantic XML**: local text/image extraction with **PyMuPDF**,
image description/transcription with the shared **Azure OpenAI** layer in `pptx/llm_ref.py`.
No `opendataloader`, no Java — the only thing that leaves the machine is the image sent to Azure.

---

## Pipeline at a glance

```
PDF ──PyMuPDF──> per-page { text blocks, image blocks, page class }
                       │
                       ├─ normal page   → <text> + embedded <figure>s (reading order)
                       ├─ scanned/empty → render whole page to PNG → transcribe → <text>
                       └─ split figure  → stitch the two halves into one image
                       │
             de-dup images by SHA-256
                       │
   Azure (via pptx/llm_ref.py):  figures → short description
                                 pages   → full transcription
                       │
        <document> <page> <text> / <figure> XML
```

## Setup

Azure config is owned by `pptx/llm_ref.py`, which auto-loads a gitignored `.env` on import:

```
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_API_VERSION=2024-10-21     # optional; defaults to 2024-10-21
```

The **model / deployment** is `llm_ref.DEFAULT_MODEL` (currently `"gpt-4.1-deployment"`), shared
with the PPTX path — change it there to point at your vision-capable deployment. (You no longer
need `AZURE_OPENAI_DEPLOYMENT`; that was the old self-contained version.)

Run it:
```bash
python pdf/pdf_extractor.py file.pdf -o output
python pdf/pdf_extractor.py file.pdf --no-fallback   # don't render empty/vector-only pages
```

---

## Output format (LLM-friendly: semantic tags, flat structure)

```xml
<document filename="report.pdf" type="PDF">
  <page number="1">
    <text>Intro paragraph text, with &amp; and &lt; escaped.</text>
    <figure id="1">Bar chart: revenue by region and year, trending up.</figure>
  </page>
  <page number="2">
    <text>Full-page transcription of a scanned page…</text>
  </page>
</document>
```

- **Semantic tags**: `<document>`, `<page number>`, `<text>`, `<figure id>` — no generic blobs.
- **Flat**: three shallow levels (`document > page > text|figure`); no deep nesting.
- **Order preserved**: `<text>` and `<figure>` sit as siblings in reading order; consecutive text
  blocks are merged into one `<text>`.
- **Whole-page transcription** (scanned/vector/blank page) becomes that page's `<text>`.
- **Valid XML**: extracted text and descriptions are escaped (`& < >`), so real PDF text can't
  break the markup.

---

## The three cases it handles

### 1. Normal page — text + embedded figures
`page.get_text("dict")` returns **blocks** in reading order; text and image blocks each carry a
`bbox`, and image blocks include the raw image bytes. Text → `<text>`; each embedded image →
`<figure id>`. They're sorted by `(top, left)` so text and figures interleave naturally.

### 2. Scanned / vector-only / blank page — whole-page transcription
Pages with **no selectable text** (a scan is just a raster; a vector chart is drawn with path
operators) are treated as "whole" when either:
- **scanned**: `text_len ≤ SCANNED_TEXT_MAX_CHARS` **and** image area ≥ `SCANNED_IMAGE_COVER` of the page, or
- **empty**: no text and no images (vector-only/blank) — handled when `fallback=True`.

Such a page is rendered to PNG (`render_page_png`) and sent to `transcribe_page` (`PAGE_PROMPT`,
OCR-style). Scanned pages are always transcribed; empty/vector pages only when `fallback` is on.

### 3. Figure split across a page break — stitched back together
A tall figure printed as **top half at the bottom of page N** + **bottom half at the top of page
N+1** is found by `detect_split_pairs`:
- **Edge**: page-N image hugs the bottom margin and page-N+1 image hugs the top margin (within `EDGE_TOL_FRAC` of page height).
- **Alignment**: their x-coordinates line up (within `X_ALIGN_TOL_FRAC` of page width).

Matches are `stitch_vertical`-ed into one PNG (top over bottom), described once, and placed on page
N; the page-N+1 half is marked consumed so it isn't emitted twice.

---

## Function reference

### LLM calls — delegated to `pptx/llm_ref.py`
The PDF module has **no** Azure code of its own; it imports `llm_ref` (from the sibling `pptx/`
folder) and calls through it, so PDF and PPTX share one client, one encoder, one `.env` loader,
and one deployment constant.

| Function | What it does |
|---|---|
| `_client()` | Cached (`lru_cache`) `llm_ref.get_azure_openai_client()` — one Azure client per run. |
| `_describe(blob, ext, prompt)` | One vision call using `llm_ref`'s client, `encode_image_to_data_url`, `DEFAULT_MODEL`, and `IMAGE_DETAIL`; returns the text reply. |
| `describe_figure(blob, ext)` | `_describe` with `FIGURE_PROMPT` — a concise figure description. |
| `transcribe_page(blob, ext)` | `_describe` with `PAGE_PROMPT` — full-page OCR-style transcription. |

(From `llm_ref` itself: `get_azure_openai_client`, `encode_image_to_data_url`, `get_required_env`,
`_load_dotenv`, `DEFAULT_MODEL`, `IMAGE_DETAIL` — see `pptx/llm_ref.py`.)

### Data model
| Type | Role |
|---|---|
| `ImageRef` | One unique image: id, bytes, ext, sha256, size, `kind` (`"figure"` \| `"page"`), description. |
| `Page` | A page number + ordered `blocks` (`("text", str)` \| `("image", image_id)`). |
| `ImageRegistry` | De-duplicates images by SHA-256, assigns sequential ids; `register()` → id, `.images` → uniques. |

### PyMuPDF extraction
| Function | What it does |
|---|---|
| `_block_text(block)` | Joins a text block's spans/lines into a string. |
| `_extract_page(page)` | Pulls a page's text + image blocks (bytes + bbox) and classifies it scanned/empty; returns those + page size. |
| `render_page_png(page, dpi)` | Rasterizes a whole page to PNG bytes. |
| `stitch_vertical(top, bottom)` | Stacks two image halves into one PNG. |
| `detect_split_pairs(page_images, page_sizes)` | Finds bottom-of-N / top-of-N+1 image pairs that line up. |
| `build_pages(doc, registry, fallback)` | Orchestrates extract → classify → stitch splits → assemble `Page`s in reading order, registering every image. |

### Describe + render
| Function | What it does |
|---|---|
| `describe_images(registry, figure_describer, page_describer, max_workers)` | Fills every unique image's `.description` concurrently, routing `page` vs `figure`; one failure doesn't abort the batch. |
| `xml_attr(value)` | Escapes `& " < >` for an XML **attribute**. |
| `xml_text(value)` | Escapes `& < >` for XML **element text** (extracted text + descriptions). |
| `render_xml(pages, by_id, filename, data_type)` | Emits the flat `<document>/<page>/<text>/<figure>` XML. |

### Entry points
| Function | What it does |
|---|---|
| `pdf_converter(file_path, output_dir=None, …)` | Public API: open PDF → `build_pages` → `describe_images` → `render_xml`; writes `<stem>.xml` if `output_dir` is set and returns the XML. `figure_describer` / `page_describer` default to the Azure describers but can be swapped (e.g. stubs for tests). |
| `main(argv)` | CLI wrapper (`file`, `-o/--out`, `--data-type`, `--no-fallback`). |

---

## Config knobs (top of the file)
| Constant | Meaning |
|---|---|
| `DEFAULT_MAX_WORKERS = 8` | Concurrent Azure requests. |
| `PAGE_RENDER_DPI = 200` | Resolution when rendering a whole page. |
| `MIN_FIGURE_DIM = 64` | Drop embedded images smaller than this (icons, rules). |
| `SCANNED_TEXT_MAX_CHARS = 20` | ≤ this much text ⇒ page may be a scan. |
| `SCANNED_IMAGE_COVER = 0.60` | Image area ≥ 60% of page ⇒ page may be a scan. |
| `EDGE_TOL_FRAC = 0.06` | How close to a margin counts as "touching" it (split detection). |
| `X_ALIGN_TOL_FRAC = 0.05` | Horizontal alignment tolerance for split halves. |

(Model, detail level, and the Azure prompts' *client* live in `pptx/llm_ref.py`; the PDF-specific
`FIGURE_PROMPT` / `PAGE_PROMPT` are at the top of this file.)

---

## Limitations (be honest about the heuristics)
- **Reading order is `(top, left)`** — great for single-column pages; multi-column layouts can
  interleave across columns.
- **Split detection is heuristic** (edge proximity + x-alignment). Three-page spans or two aligned
  unrelated images at a page break are edge cases; tune `EDGE_TOL_FRAC` / `X_ALIGN_TOL_FRAC`.
- **Scanned classification is heuristic** — a near-full-page vector chart with little text may be
  transcribed as a whole page rather than described as a figure.
- **Vector charts on a text page are missed as figures** (only whole vector *pages* are rendered).
- **Exotic image formats** (CMYK JPEG, JPEG2000/JPX, JBIG2) may be rejected by the vision API;
  normalize to PNG via Pillow first if you hit failures.
- **Whole pages are re-rendered** at `PAGE_RENDER_DPI` (clean RGB, captures vector overlays) at the
  cost of a rasterization step.

## Testing without Azure
`pdf_converter` accepts `figure_describer` / `page_describer` callables `(blob, ext) -> str`, so you
can exercise the whole pipeline (text, scanned pages, split stitching, XML rendering) with stubs and
no API calls — which is how this module was validated.
