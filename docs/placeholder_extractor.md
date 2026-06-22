# `placeholder_extractor.py` — Component Reference

A line-by-line guide to every component in `pptx/placeholder_extractor.py`: what it
does, why it exists, and which library it relies on. For a visual map of the same
material, open [`placeholder_extractor.html`](./placeholder_extractor.html) in a browser.

---

## 1. What the module does

Convert a PowerPoint deck (`.pptx`) into Markdown by combining two cheap sources and
using the language model for one thing only — describing images:

1. **Text** is read straight from the file with `python-pptx` (free, exact).
2. **Images** are pulled out of the `.pptx` package and each unique one is described
   once by an OpenAI vision model, then spliced back where it sat on the slide.

The model never re-transcribes text it could already read, so output tokens — the
dominant cost — stay small, and the native text is lossless.

---

## 2. The pipeline (three stages)

```
.pptx ──▶ [1] PARSE ──▶ slides + unique images ──▶ [2] DESCRIBE ──▶ [3] RENDER ──▶ Markdown
           (no network)                              (model calls)     (string assembly)
```

| stage | method | network? | output |
|-------|--------|----------|--------|
| 1. Parse | `PlaceholderExtractor._parse` | no | ordered text/image blocks per slide + a deduped image set |
| 2. Describe | `PlaceholderExtractor._describe_all` | yes (images only) | each image's Markdown description |
| 3. Render | `PlaceholderExtractor._render` | no | the final stitched Markdown |

`extract()` is the public entry point that runs all three.

---

## 3. Libraries used and why

| library | role in this file | where |
|---------|-------------------|-------|
| **python-pptx** | Open the deck, walk shapes/groups, read text and tables, and resolve image relationships inside the OOXML package. | `Presentation`, `MSO_SHAPE_TYPE`, `qn`, every shape access |
| **PyMuPDF (`fitz`)** | Rasterize **SVG** images to PNG (vision APIs don't accept SVG). Imported lazily, so decks without SVGs never need it. | `_svg_to_png` |
| **openai** | Send each image to the vision model via the Responses API. Imported lazily, so text-only decks need no key or package. | `_client`, `_describe` |
| **hashlib** (stdlib) | SHA-1 of each image's bytes to deduplicate identical images (describe once, reuse everywhere). | `_parse.register` |
| **base64** (stdlib) | Encode image bytes into a `data:` URL for the API. | `_data_url` |
| **concurrent.futures** (stdlib) | Describe images in parallel (thread pool) — the calls are I/O-bound. | `_describe_all` |
| **dataclasses** (stdlib) | Small, typed records (`ImageRef`, `Slide`, …) instead of loose tuples/dicts. | data model |
| **logging** (stdlib) | Structured progress to stderr instead of `print`. | throughout |
| **argparse / pathlib / os** (stdlib) | CLI parsing, paths, and reading `OPENAI_API_KEY`. | `main`, `_client` |

---

## 4. Configuration — `ExtractorConfig`

A frozen dataclass holding everything tunable, so call sites stay clean and settings
are immutable per run.

| field | default | purpose |
|-------|---------|---------|
| `model` | `"gpt-4.1"` | any vision-capable OpenAI model |
| `image_detail` | `"high"` | `"high"` reads dense charts better; `"low"`/`"auto"` cost fewer input tokens |
| `max_workers` | `8` | how many images are described concurrently |
| `prompt` | `_IMAGE_PROMPT` | the instruction sent with every image |

---

## 5. Data model (the typed records)

| type | meaning |
|------|---------|
| `TextBlock(text)` | a run of native text from the slide |
| `ImageBlock(image_id)` | a placeholder pointing at a deduplicated image |
| `ImageRef(image_id, blob, ext, description)` | one unique image and the description the model returns for it |
| `Slide(number, blocks)` | one slide as an ordered list of `TextBlock`/`ImageBlock` |

A slide's `blocks` list **is** the reading order; an `ImageBlock` is a pointer so that
N copies of the same logo share one `ImageRef` (and one model call).

---

## 6. Function-by-function

### `_image_from_shape(shape) -> (blob, ext) | None`
The detector. Returns image bytes if the shape carries a picture, else `None`. It
checks **two** places, which is the crux of handling real-world decks:

1. **A true picture shape** (`shape_type == PICTURE`) → `shape.image.blob`.
2. **A picture *fill* on a shape** (`fill.type == PICTURE`) → follow the fill's
   `<a:blip r:embed="rId…">` relationship to the stored image part and read its `.blob`.

Case 2 is what catches charts pasted as a shape fill, which `shape.image` alone misses.
Both read the **original embedded file** — no slide rendering involved.

### `_sort_key(shape) -> (top, left)`
Sort helper to approximate human reading order (top-to-bottom, then left-to-right),
because shapes come back in z-order, not visual order. Guards against `None` positions.

### `_iter_blocks(shapes, register)`
The recursive walker. For each shape (descending into groups), it yields a `TextBlock`
or an `ImageBlock`. `register` is a callback that deduplicates an image and hands back
its stable `image_id`. Also flattens tables into `text | text | text` rows.

### `_svg_to_png(svg_bytes) -> bytes`
Rasterizes a single SVG to PNG with PyMuPDF. Needed because the vision API accepts
raster formats only. Imported lazily so it's a zero-cost dependency unless used.

### `_data_url(blob, ext) -> str`
Turns raw image bytes into a `data:image/…;base64,…` URL for the API, converting SVG to
PNG first and normalizing the MIME type.

### `PlaceholderExtractor.extract(pptx_path) -> str`
Public entry point: `parse → (describe if any images) → render`. The only method most
callers need.

### `PlaceholderExtractor._parse(pptx_path)`
Stage 1. Opens the deck, walks every slide via `_iter_blocks`, and builds the deduped
image registry through a closure (`register`) keyed by SHA-1 of the bytes. Returns the
slides and the unique images. No network.

### `PlaceholderExtractor._describe_all(images)`
Stage 2. Creates the client once and runs `_describe` across all images in a thread
pool (bounded by `max_workers`). Only called when at least one image exists.

### `PlaceholderExtractor._describe(client, image)`
Sends one image (text prompt + `input_image` data URL) to the Responses API and stores
the result on the `ImageRef`. Per-image `try/except` so one failure can't sink the run.

### `PlaceholderExtractor._render(slides, by_id)`
Stage 3. Walks each slide's blocks, emitting native text as-is and replacing each
`ImageBlock` with `**[Image n]**` + its description. Pure string assembly, no network.

### `PlaceholderExtractor._client()`
Lazily constructs the OpenAI client, raising a clear error if `OPENAI_API_KEY` is unset.
Called only when there are images — so a text-only deck needs no key.

### `main(argv)`
CLI: parses args, configures logging (and mutes `httpx` request noise), runs the
extractor, and writes the Markdown (default `output/<name>.md`).

---

## 7. Why it's structured this way (design notes)

- **Network isolated to one stage.** Parse and render are pure and offline; only
  `_describe_all` touches OpenAI. Easy to test, and text-only decks skip the network
  entirely.
- **Dedup before describing.** Identical images (repeated logos, shared chart) are
  described once — fewer calls, lower cost. On the sample deck this turned 25 image
  placements into 19 model calls.
- **Lazy imports.** `fitz` and `openai` load only when actually needed, so a text-only
  run has no heavy dependencies and no key requirement.
- **Typed records over tuples/dicts.** `Slide`, `TextBlock`, `ImageBlock`, `ImageRef`
  make the data flow self-documenting and safe to refactor.
- **Failures are isolated.** A bad image yields an inline note, not a crashed run.

---

## 8. Usage

```bash
export OPENAI_API_KEY=sk-...
python pptx/placeholder_extractor.py "deck.pptx"                 # -> output/deck.md
python pptx/placeholder_extractor.py "deck.pptx" -o out.md --detail auto
```

```python
from pathlib import Path
from placeholder_extractor import PlaceholderExtractor, ExtractorConfig

md = PlaceholderExtractor(ExtractorConfig(image_detail="auto")).extract(Path("deck.pptx"))
```
