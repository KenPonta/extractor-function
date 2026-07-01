# PDF Extractor (`pdf/pdf_extractor.py`)

Converts a `.pdf` into placeholder XML: local text/image extraction with **PyMuPDF**, image
description/transcription with an **Azure OpenAI** vision model. No `opendataloader`, no Java —
the only thing that leaves the machine is the image sent to your Azure describer.

---

## Pipeline at a glance

```
PDF ──PyMuPDF──> per-page { text blocks, image blocks, page class }
                       │
                       ├─ normal page   → text + embedded figures (reading order)
                       ├─ scanned/empty → render whole page to PNG → transcribe
                       └─ split figure  → stitch the two halves into one image
                       │
             de-dup images by SHA-256
                       │
        Azure vision:  figures → short description
                       pages   → full transcription
                       │
                    <documents> XML  (text + <image> items)
```

## Setup

The Azure client is built from environment variables (auto-loaded from a gitignored `.env`):

```
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT=<your vision-capable deployment name>
AZURE_OPENAI_API_VERSION=2024-10-21     # optional; defaults to 2024-10-21
```

Run it:
```bash
python pdf/pdf_extractor.py file.pdf -o output
python pdf/pdf_extractor.py file.pdf --no-fallback   # don't render empty/vector-only pages
```

---

## The three cases it handles

### 1. Normal page — text + embedded figures
`page.get_text("dict")` returns **blocks** in reading order; text blocks and image blocks each
carry a bounding box (`bbox`). Text becomes `("text", …)` blocks; each embedded image (which the
dict conveniently includes as raw bytes) becomes an `("image", …)` block. They're sorted by
`(top, left)` so text and figures interleave the way a reader would scan the page.

### 2. Scanned / vector-only / blank page — whole-page transcription
Some pages have **no selectable text** — a scanned document is just a big raster; a vector chart
is drawn with path operators. A page is treated as "whole" when either:
- **scanned**: `text_len ≤ SCANNED_TEXT_MAX_CHARS` **and** image area ≥ `SCANNED_IMAGE_COVER` of the page, or
- **empty**: no text and no images at all (vector-only or blank) — handled when `fallback=True`.

Such a page is rendered to a PNG (`render_page_png`) and sent to the **page transcription** prompt
(`PAGE_PROMPT`), which does OCR-style text recovery plus short notes for any chart. Scanned pages
are always transcribed; empty/vector pages only when `fallback` is on.

### 3. Figure split across a page break — stitched back together
A tall figure can be printed as a **top half at the bottom of page N** and a **bottom half at the
top of page N+1**. `detect_split_pairs` finds these by two heuristics:
- **Edge**: the page-N image hugs the bottom margin and the page-N+1 image hugs the top margin
  (within `EDGE_TOL_FRAC` of the page height).
- **Alignment**: their left/right x-coordinates line up (within `X_ALIGN_TOL_FRAC` of page width).

Matches are `stitch_vertical`-ed into one PNG (top piece over bottom piece), described once, and
placed on page N. The page-N+1 half is marked *consumed* so it isn't emitted again.

---

## Function reference

### Azure OpenAI layer (mirrors `pptx/llm_ref.py`)
| Function | What it does |
|---|---|
| `_load_dotenv()` | On import, copies `KEY=value` lines from the nearest `.env` into `os.environ` (`setdefault`, so a real exported var wins). |
| `LLMError` | Exception for a missing setting or a failed Azure call. |
| `get_required_env(name)` | Returns the env var or raises `LLMError` naming it. |
| `get_azure_openai_client()` | Builds and **caches** (`lru_cache`) the `AzureOpenAI` client from `AZURE_OPENAI_*`. |
| `encode_image_to_data_url(blob, ext)` | Raw image bytes → `data:image/…;base64,…` for vision input. |
| `_describe(blob, ext, prompt)` | One vision call: sends the image + prompt, returns the text reply. |
| `describe_figure(blob, ext)` | `_describe` with `FIGURE_PROMPT` — a concise figure description. |
| `transcribe_page(blob, ext)` | `_describe` with `PAGE_PROMPT` — full-page OCR-style transcription. |

### Data model
| Type | Role |
|---|---|
| `ImageRef` | One unique image: id, bytes, ext, sha256, size, `kind` (`"figure"` \| `"page"`), description. |
| `Page` | A page number + ordered `blocks` (`("text", str)` \| `("image", image_id)`). |
| `ImageRegistry` | De-duplicates images by SHA-256 and assigns sequential ids; `register()` returns the id, `.images` lists the uniques. |

### PyMuPDF extraction
| Function | What it does |
|---|---|
| `_block_text(block)` | Joins a text block's spans/lines into a string. |
| `_extract_page(page)` | Pulls a page's text blocks and image blocks (with bytes + bbox) and classifies it as scanned/empty; returns those plus the page size. |
| `render_page_png(page, dpi)` | Rasterizes a whole page to PNG bytes (for whole-page transcription). |
| `stitch_vertical(top, bottom)` | Stacks two image halves into one PNG (normalizing to the wider half). |
| `detect_split_pairs(page_images, page_sizes)` | Finds bottom-of-N / top-of-N+1 image pairs that line up → split figures. |
| `build_pages(doc, registry, fallback)` | Orchestrates all of the above: extract → classify → stitch splits → assemble `Page`s in reading order, registering every image. |

### Describe + render
| Function | What it does |
|---|---|
| `describe_images(registry, figure_describer, page_describer, max_workers)` | Fills every unique image's `.description` concurrently, routing `page` vs `figure` to the right describer; one failure doesn't abort the batch. |
| `xml_attr(value)` | Escapes `& " < >` for XML attributes. |
| `render_image_item(ref)` | Emits one figure's `<image id sha256 size_bytes>description</image>`. |
| `render_xml(pages, by_id, filename, data_type)` | Builds the final `<documents>` XML; a `page` transcription becomes the page body, a `figure` becomes an `<image>` item. |

### Entry points
| Function | What it does |
|---|---|
| `pdf_converter(file_path, output_dir=None, …)` | Public API: open PDF → `build_pages` → `describe_images` → `render_xml`; writes `<stem>.xml` if `output_dir` is given and returns the XML. The `figure_describer` / `page_describer` params default to the Azure describers but can be swapped (e.g. stubs for tests). |
| `main(argv)` | CLI wrapper (`file`, `-o/--out`, `--data-type`, `--no-fallback`). |

---

## Config knobs (top of the file)
| Constant | Meaning |
|---|---|
| `DEFAULT_MAX_WORKERS = 8` | Concurrent Azure requests. |
| `IMAGE_DETAIL = "high"` | Vision detail level (drives token cost). |
| `PAGE_RENDER_DPI = 200` | Resolution when rendering a whole page. |
| `MIN_FIGURE_DIM = 64` | Drop embedded images smaller than this (icons, rules). |
| `SCANNED_TEXT_MAX_CHARS = 20` | ≤ this much text ⇒ page may be a scan. |
| `SCANNED_IMAGE_COVER = 0.60` | Image area ≥ 60% of page ⇒ page may be a scan. |
| `EDGE_TOL_FRAC = 0.06` | How close to a margin counts as "touching" it (split detection). |
| `X_ALIGN_TOL_FRAC = 0.05` | Horizontal alignment tolerance for split halves. |

---

## Limitations (be honest about the heuristics)
- **Reading order is `(top, left)`** — great for single-column pages; multi-column layouts can
  interleave across columns (same trade-off as the PPTX path).
- **Split detection is heuristic.** It matches by page-edge proximity + x-alignment. A figure that
  spans *three* pages, or two unrelated images that happen to align at a page break, are edge cases;
  tune `EDGE_TOL_FRAC` / `X_ALIGN_TOL_FRAC` if needed.
- **Scanned classification is heuristic.** A near-full-page vector chart with little text can be
  transcribed as a whole page rather than described as a figure — acceptable (the page prompt still
  describes charts), but worth knowing.
- **Exotic embedded image formats** (CMYK JPEG, JPEG2000/JPX, JBIG2) may be rejected by the vision
  API. Most PDFs use PNG/JPEG and work; if you hit failures, normalize figure bytes to PNG via
  Pillow before sending.
- **Whole pages are re-rendered** at `PAGE_RENDER_DPI` rather than reusing the embedded scan, which
  guarantees clean RGB and captures vector overlays, at the cost of a rasterization step.

## Testing without Azure
`pdf_converter` accepts `figure_describer` / `page_describer` callables `(blob, ext) -> str`, so you
can exercise the entire extraction pipeline (text, scanned pages, split stitching) with stubs and no
API calls — which is exactly how this module was validated.
