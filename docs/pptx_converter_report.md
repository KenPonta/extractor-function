# `pptx_converter.py` + `llm.py` — How It Works (line by line)

A complete walkthrough of the two-file converter: what the pipeline does, the two input
paths (`.pptx` vs legacy `.ppt`), and every line of code. Open
[`pptx_converter.html`](./pptx_converter.html) for the visual version.

---

## 1. What the two files do

Together they convert a PowerPoint deck (`.ppt` **or** `.pptx`) into an XML `<documents>`
bundle where each slide's text is inline and every image is replaced by an LLM-written
description.

- **`pptx_converter.py`** — the orchestrator: validates the file, parses slides + images,
  dedups images, renders the XML, and runs the CLI. It knows about PowerPoint structure.
- **`llm.py`** — all the model I/O: builds the OpenAI/Azure client, describes images with a
  vision model, and (for `.ppt`) asks the model which slide each figure belongs to. It knows
  about the API but nothing about PowerPoint.

The split is deliberate: `llm.py` takes **plain data** (numbers, strings, bytes) and has no
project imports, so the model logic is isolated and swappable.

---

## 2. The pipeline

```
                      ┌─────────────── pptx_converter.py ───────────────┐
 file ─▶ validate ─▶  parse  ─▶  dedup images  ─▶  describe  ─▶  place  ─▶  render ─▶ XML
         (.ppt|.pptx) │            (registry)        │            │         │
                      │                              │            │         │
              .pptx ──┤ exact placement              │      .ppt only       │
              .ppt  ──┘ (images deferred)            │   (infer slide)       │
                                                     ▼            ▼          ▼
                                              ┌──────────── llm.py ───────────┐
                                              │ describe_images   match_slides │
                                              └────────────────────────────────┘
```

Stages, in order (`pptx_converter()` is the conductor):

| stage | function | what happens |
|-------|----------|--------------|
| 1. validate | `validate_file` | confirm it's `.ppt` or `.pptx`, return the kind |
| 2. parse | `parse_pptx` / `parse_ppt` | read slides → blocks; register images (deduped) |
| 3. describe | `llm.describe_images` | vision model writes each unique image's description |
| 4. place (`.ppt` only) | `place_legacy_images` | infer which slide each figure belongs to |
| 5. render | `render_xml` | stitch text + descriptions into the XML template |

`.pptx` skips stage 4 because it already knows each image's exact slide.

---

## 3. The two input paths

The whole design hinges on one difference between the formats:

| | `.pptx` (modern) | `.ppt` (legacy) |
|---|---|---|
| image → slide link | **known** (each picture is a shape on a slide) | **lost** (no readable link) |
| parser | `python-pptx` | `sharepoint2text` |
| placement | exact, during parse | inferred *after* describing (LLM match, else proportional spread) |
| XML marker | `[Image N]` | `[Image N (approximate slide)]` |

So `.pptx` is straightforward; the clever part is `.ppt`, where images are parsed in **deck
order**, described, then matched to slides by the model — with the order constraint that a
later figure can't land on an earlier slide.

---

## 4. `pptx_converter.py` — line by line

### Imports & constants (lines 1–21)
```python
import argparse, hashlib, logging, sys
from dataclasses import dataclass, field
from pathlib import Path
import llm
from llm import DEFAULT_MAX_WORKERS, DEFAULT_MODEL, IMAGE_PROMPT
```
Standard library + the `llm` module. It imports the model defaults from `llm` so the CLI and
function signatures can use them as defaults without redefining them.

```python
MSO_FILL_PICTURE = 6
```
The enum value meaning "this shape's fill is a picture" — used to catch charts pasted as a
shape fill (not a normal picture).

```python
RASTER_MIME_EXT = {"image/png": "png", "image/jpeg": "jpg", ...}
```
Maps a **MIME content-type → file extension**. The `.ppt` parser gives images by content-type
(not extension), so this converts e.g. `image/png` → `png`. Anything not in this map (WMF/EMF
vector formats) is treated as "can't rasterize" and skipped.

```python
MIN_IMAGE_DIM = 150
```
Skip images whose smallest side is under 150 px. The comment explains why: saving to `.ppt`
turns vector icons into tiny PNGs that the `.pptx` path never exposes; this filters those
out so only real charts get described. `0` disables it.

### `content_digest` (lines 25–35)
```python
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
```
Hashes an image **by its decoded pixels**, not its raw bytes. It opens the image, normalizes
it to RGB, re-encodes it as PNG, and hashes that. Why: `.ppt` re-encodes the same picture
slightly differently on each slide, so raw-bytes hashing would see them as different images.
Hashing the pixels makes identical pictures collapse to one digest (so they're described
once). If PIL can't open it (e.g. a weird format), it falls back to hashing raw bytes.

### Data model (lines 38–66)
```python
@dataclass
class ImageRef:
    image_id: int; blob: bytes; ext: str; description: str = ""
```
One unique image: an id, its bytes, its extension, and the description (filled in later).

```python
@dataclass
class Slide:
    number: int
    blocks: list = field(default_factory=list)   # ("text", str) | ("image", image_id)
```
A slide is its number plus an ordered list of blocks. Each block is a tuple: `("text", str)`
for native text, `("image", id)` for an image placeholder. `field(default_factory=list)`
gives each slide its own fresh list.

```python
@dataclass
class ImageRegistry:
    by_digest: dict = field(default_factory=dict)

    def register(self, blob, ext) -> int:
        digest = content_digest(blob)
        ref = self.by_digest.get(digest)
        if ref is None:
            ref = self.by_digest[digest] = ImageRef(len(self.by_digest) + 1, blob, ext)
        return ref.image_id

    @property
    def images(self) -> list:
        return list(self.by_digest.values())
```
The dedup engine. `register` hashes the image; if that digest is new it creates an `ImageRef`
with the next id; either way it returns the id. So N copies of one picture share one id and
one description. `.images` returns the unique set.

### Helpers (lines 70–97)
```python
def validate_file(file_path) -> tuple[Path, str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    kind = {".ppt": "ppt", ".pptx": "pptx"}.get(path.suffix.lower())
    if kind is None:
        raise ValueError(f"unsupported file type: {path.name} (expected .ppt or .pptx)")
    return path, kind
```
Checks the file exists and is `.ppt` or `.pptx`, returning the kind string that decides which
parser runs. Anything else raises.

```python
def ext_from_mime(content_type) -> str | None:
    return RASTER_MIME_EXT.get((content_type or "").strip().lower())
```
Looks up an extension from a MIME type (for `.ppt` images). Returns `None` for unsupported
types — which the parser uses as the "skip this image" signal.

```python
def xml_attr(value) -> str:
    return str(value).replace("&","&amp;").replace('"',"&quot;").replace("<","&lt;").replace(">","&gt;")
```
Escapes a value for use inside an XML attribute (filename, data-type).

```python
def slide_text(slide) -> str:
    return " ".join(value for kind, value in slide.blocks if kind == "text")
```
Joins all of a slide's text blocks into one string — used to give the placement model the
slide's text.

```python
def log_parse(kind, slides, registry, skipped_vector=0, skipped_small=0):
    placements = sum(k == "image" for s in slides for k, _ in s.blocks)
    logger.info("%s: %d slides, %d images, %d placements, %d vector + %d small skipped", ...)
```
Logs a one-line parse summary (slides, unique images, total image placements, and how many
images were skipped as vector or too-small).

### `.pptx` parsing (lines 101–147)
```python
def shape_sort_key(shape) -> tuple[int, int]:
    top = shape.top if isinstance(shape.top, int) else 0
    left = shape.left if isinstance(shape.left, int) else 0
    return top, left
```
Sort key for reading order (top-to-bottom, then left-to-right), guarding `None` positions.

```python
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
```
Extracts an image from a shape, handling **two cases**: a real `PICTURE` shape (use
`shape.image`), or a picture used as a shape **fill** (charts) — found by reading the
`<a:blip r:embed>` relationship out of the shape XML and resolving it to the stored image
part. Returns `(bytes, ext)` or `None`. (Imports are local so `python-pptx` loads only when
parsing a `.pptx`.)

```python
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
```
The generator that turns one slide's shapes into ordered blocks. It walks shapes in reading
order, recurses into groups, registers images (dedup → yields `("image", id)`), emits text,
and flattens tables to `a | b | c` rows. This is where `.pptx` images get placed on their
exact slide — inline, in order.

```python
def parse_pptx(path, registry) -> list:
    from pptx import Presentation
    slides = [Slide(n, list(iter_pptx_blocks(slide.shapes, registry)))
              for n, slide in enumerate(Presentation(str(path)).slides, start=1)]
    log_parse("pptx", slides, registry)
    return slides
```
Opens the deck and builds a `Slide` per slide (numbered from 1), each carrying its ordered
blocks. Logs the summary and returns the list.

### `.ppt` parsing (lines 151–181)
```python
def parse_ppt(path, registry) -> list:
    import sharepoint2text
    content = next(sharepoint2text.read_file(str(path)))   # one PptContent per file
    slides, pending = [], []                               # pending: (image_index, blob, ext)
    skipped_vector = skipped_small = 0
    for unit in content.iterate_units():                   # one PptUnit per slide, deck order
        blocks = []
        if unit.title:
            blocks.append(("text", unit.title.strip()))
        if (unit.text or "").strip():
            blocks.append(("text", unit.text.strip()))
        for image in unit.get_images():
            ext = ext_from_mime(image.get_content_type())
            w, h = image.width or 0, image.height or 0
            if ext is None:
                skipped_vector += 1
            elif MIN_IMAGE_DIM and w and h and min(w, h) < MIN_IMAGE_DIM:
                skipped_small += 1
            elif (blob := image.get_bytes().read()):
                pending.append((getattr(image, "image_index", 0), blob, ext))
        slides.append(Slide(unit.slide_number, blocks))
    for _, blob, ext in sorted(pending, key=lambda t: t[0]):
        registry.register(blob, ext)
    log_parse("ppt", slides, registry, skipped_vector, skipped_small)
    return slides
```
Parses a legacy `.ppt` via `sharepoint2text`. Key points:
- Each `unit` is a slide; its title and text become text blocks.
- Images are **not placed on slides here** — they're collected into `pending` with their
  `image_index` (true deck order). Images with no rasterizable type are counted as
  `skipped_vector`; images smaller than `MIN_IMAGE_DIM` are `skipped_small`; `:=` reads the
  bytes and only keeps non-empty ones.
- After all slides, `pending` is sorted by `image_index` and registered **in deck order** (so
  image ids follow the order figures appear in the deck — critical for the later matching).
- Placement is deferred because it needs the descriptions, which don't exist yet.

### `.ppt` image placement (lines 188–208)
```python
def proportional_mapping(slides, images) -> dict:
    n = len(slides)
    return {img.image_id: slides[min(n - 1, int((i + 0.5) * n / len(images)))].number
            for i, img in enumerate(images)}
```
The fallback when the LLM isn't used/available: spread the deck-ordered images **evenly**
across slides. Figure `i` of `M` lands on roughly slide `i/M` of the deck. `min(n-1, …)`
guards the last index.

```python
def place_legacy_images(slides, images, model, client, infer_placement=True) -> None:
    if not (slides and images):
        return
    mapping = None
    if infer_placement:
        mapping = llm.match_slides([(s.number, slide_text(s)) for s in slides],
                                   [(im.image_id, im.description) for im in images],
                                   model=model, client=client)
    if mapping is None:
        mapping = proportional_mapping(slides, images)
    by_number = {s.number: s for s in slides}
    for image in images:
        by_number[mapping[image.image_id]].blocks.append(("image", image.image_id))
```
Places `.ppt` images. If `infer_placement`, it asks the model (`llm.match_slides`) for a
`{image_id: slide}` map using each slide's text and each figure's description. If that returns
`None` (any failure), it falls back to `proportional_mapping`. Either way it ends with a full
map and appends each image to its slide's blocks. The all-or-nothing design means a failed
inference never half-places images.

### Rendering (lines 212–226)
```python
def render_xml(slides, by_id, filename, data_type, index=1, approx_images=False) -> str:
    suffix = " (approximate slide)" if approx_images else ""
    slide_texts = []
    for slide in slides:
        parts = [f"Slide {slide.number}"]
        for kind, value in slide.blocks:
            if kind == "text":
                parts.append(value)
            else:
                desc = by_id[value].description or "(no description)"
                parts.append(f"[Image {value}{suffix}]\n{desc}")
        slide_texts.append("\n\n".join(parts))
    body = "\n\n".join(slide_texts)
    return (f'<documents>\n  <document index="{index}" filename="{xml_attr(filename)}"'
            f' data-type="{xml_attr(data_type)}">\n{body}\n  </document>\n</documents>\n')
```
Builds the final XML. Walks each slide's blocks in order — text written as-is, each image
replaced by `[Image N]` + its description. For `.ppt`, `approx_images=True` adds
`(approximate slide)` to the marker so readers know placement was inferred. Everything is
wrapped in the `<documents>/<document>` template with escaped attributes.

### Entry point (lines 230–280)
```python
def pptx_converter(file_path, output_dir=None, *, model=DEFAULT_MODEL,
                   max_workers=DEFAULT_MAX_WORKERS, prompt=IMAGE_PROMPT,
                   data_type=None, client=None, infer_placement=True) -> str:
    path, kind = validate_file(file_path)
    registry = ImageRegistry()
    slides = parse_pptx(path, registry) if kind == "pptx" else parse_ppt(path, registry)

    images = registry.images
    if images:
        client = llm.get_client(client)        # resolve once so describe + placement share it
        llm.describe_images(images, model=model, max_workers=max_workers, prompt=prompt, client=client)
        if kind == "ppt":
            place_legacy_images(slides, images, model, client, infer_placement)

    by_id = {image.image_id: image for image in images}
    xml = render_xml(slides, by_id, path.name, data_type or kind.upper(), approx_images=(kind == "ppt"))
    if output_dir is not None:
        out_path = Path(output_dir) / f"{path.stem}.xml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml, encoding="utf-8")
        logger.info("written to %s", out_path)
    return xml
```
The public entry point and the whole pipeline in one place: validate → parse (by kind) →
(if any images) build the client once, describe all images, and for `.ppt` place them →
render → optionally write to disk → return the XML. The `*` makes everything after
`output_dir` keyword-only. Resolving the client once means describing and placement share the
same connection.

```python
def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert .ppt/.pptx to placeholder XML.")
    parser.add_argument("file", type=Path, help=".ppt or .pptx file")
    parser.add_argument("-o", "--out", type=Path, default="output", help="output directory")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL)
    parser.add_argument("--data-type", default=None)
    parser.add_argument("--no-infer-placement", action="store_true", help="...")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        pptx_converter(args.file, args.out, model=args.model, data_type=args.data_type,
                       infer_placement=not args.no_infer_placement)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
```
The CLI: parse args, set up logging (mute httpx noise), run the converter, and turn the
validation errors into clean `error: …` messages. `--no-infer-placement` flips the `.ppt`
placement to the proportional spread (skips the LLM match).

---

## 5. `llm.py` — line by line

### Module docstring & imports (lines 1–12)
The docstring states the design rule: this module holds **all model config and API I/O**, and
its functions take **plain data** (no `Slide`/`ImageRef` types) so it has no project imports —
keeping the model layer decoupled. Imports: `base64`, `json`, `re`, `ThreadPoolExecutor`.

### Config (lines 15–38)
```python
DEFAULT_MODEL = "gpt-4.1"           # vision model (for Azure, the deployment name)
DEFAULT_MAX_WORKERS = 8             # concurrent description requests
IMAGE_DETAIL = "high"               # vision detail level
PLACEMENT_SLIDE_TEXT_CAP = 600      # chars of slide text sent to the placement model
RASTER_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
```
Tunables. `PLACEMENT_SLIDE_TEXT_CAP` limits how much slide text is sent to the matching model
(to keep that prompt small). The comment flags that on Azure `DEFAULT_MODEL` must be the
**deployment name**.

```python
IMAGE_PROMPT = ("This image was taken from a presentation slide. ...")
```
The vision instruction: extract chart/table data as plain text; for logos/decoration reply
exactly `(decorative, no data)`; don't invent; no code fence.

```python
PLACEMENT_PROMPT = ("You are placing figures back into a slide deck saved from legacy .ppt ...")
```
The matching instruction. The crucial line: because figures are given **in deck order**, the
assigned slide numbers **must be non-decreasing** (figure N's slide ≥ figure N-1's slide).
It asks for **only** a JSON object `{figure_id: slide}`. This constraint is what keeps the
model from scrambling the deck.

### Client (lines 42–64)
```python
def get_client(client=None):
    if client is not None:
        return client
    import os
    if os.environ.get("AZURE_OPENAI_ENDPOINT"):
        from openai import AzureOpenAI
        return AzureOpenAI(api_version=os.environ.get("OPENAI_API_VERSION", "2024-10-21"))
    from openai import OpenAI
    return OpenAI()
```
Resolves which client to use: a caller-supplied one wins; else if `AZURE_OPENAI_ENDPOINT` is
set, build an `AzureOpenAI` (reading endpoint/key/api-version from env); else plain `OpenAI`.
Lazy imports so neither SDK is required unless used.

```python
def _data_url(blob, ext) -> str:
    if ext == "svg":
        import fitz
        blob = fitz.open(stream=blob, filetype="svg")[0].get_pixmap().tobytes("png")
        ext = "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext if ext in RASTER_EXT else "png")
    return f"data:image/{mime};base64,{base64.b64encode(blob).decode('ascii')}"
```
Turns image bytes into a `data:` URL for the vision API. SVGs are rasterized to PNG first
(via PyMuPDF). The MIME is `jpeg` for jpg/jpeg, the ext itself if it's a known raster type,
else `png`.

### Vision description (lines 68–92)
```python
def describe_images(images, *, model=DEFAULT_MODEL, max_workers=DEFAULT_MAX_WORKERS,
                    prompt=IMAGE_PROMPT, client=None):
    client = get_client(client)
    workers = min(max_workers, len(images))
    logger.info("describing %d images via %s (%d concurrent)", len(images), model, workers)

    def describe(image):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": _data_url(image.blob, image.ext), "detail": IMAGE_DETAIL}}]}])
            image.description = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("image %d failed: %s", image.image_id, exc)
            image.description = f"[image description failed: {exc}]"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        pool.map(describe, images)
```
Describes every image **concurrently**, writing each `image.description` in place. Note this
uses the **Chat Completions** API: `messages=` with content parts `text` + `image_url`
(nested `{"url": ...}`), and reads `response.choices[0].message.content`. Per-image
`try/except` isolates failures into an inline note.

### Figure-to-slide matching (lines 96–130)
```python
def match_slides(slides, figures, *, model=DEFAULT_MODEL, client=None) -> dict | None:
    client = get_client(client)
    slide_lines = [f"Slide {n}: {(text or '')[:PLACEMENT_SLIDE_TEXT_CAP]}" for n, text in slides]
    figure_lines = [f"Figure {i}: {desc or '(no description)'}" for i, desc in figures]
    user = "Slides:\n" + "\n".join(slide_lines) + "\n\nFigures (in deck order):\n" + "\n".join(figure_lines)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": PLACEMENT_PROMPT},
                      {"role": "user", "content": user}])
        raw = (response.choices[0].message.content or "").strip()
        replies = json.loads(re.sub(r"^```(?:json)?|```$", "", raw).strip())
    except Exception as exc:
        logger.warning("LLM placement failed (%s); falling back", exc)
        return None

    valid = sorted(n for n, _ in slides)
    mapping, prev = {}, valid[0]
    for fid, _ in figures:
        try:
            target = int(replies[str(fid)])
        except (KeyError, ValueError, TypeError):
            logger.warning("placement model omitted figure %s; falling back", fid)
            return None
        target = min(max(target, prev), valid[-1])      # clamp into [prev, last]
        target = next(n for n in valid if n >= target)  # snap forward to a real slide
        mapping[fid] = prev = target
    logger.info("placed %d figures via %s", len(figures), model)
    return mapping
```
Asks the model which slide each figure belongs to. Step by step:
1. Build a text prompt listing the slides (number + capped text) and the figures (id +
   description), explicitly **in deck order**.
2. Call the model; strip any stray code fence; `json.loads` the `{figure_id: slide}` object.
   Any error → log and return `None` (caller falls back).
3. Then **enforce the constraints in code** — never trusting the model blindly:
   - `prev` tracks the last assigned slide.
   - `clamp into [prev, last]`: a figure can't go before the previous figure's slide and
     can't exceed the last real slide → this is what enforces **non-decreasing** order.
   - `snap forward to a real slide`: if the model picks a number that isn't an actual slide,
     move up to the next real one.
   - If the model omits a figure entirely → return `None` (fall back).
4. Return `{figure_id: slide}`.

The takeaway: the prompt *asks* for order, but the code *guarantees* it — the model can only
choose **within** the allowed region, never reorder the deck.

---

## 6. Key concepts (the three clever bits)

1. **Dedup by pixels, not bytes** (`content_digest`). `.ppt` re-encodes the same image per
   slide; hashing decoded pixels collapses those into one description.
2. **Deferred, inferred placement for `.ppt`** (`parse_ppt` → `describe_images` →
   `place_legacy_images` → `match_slides`). `.ppt` loses image-to-slide links, so images are
   registered in deck order, described, then matched to slides by the model — with a
   proportional-spread fallback so it always produces *some* placement.
3. **Trust-but-verify ordering** (`match_slides`). The model suggests a slide per figure, but
   the code clamps assignments to be non-decreasing and snaps them to real slides — so a bad
   model reply can degrade quality but can't corrupt the structure.

---

## 7. Function cheat-sheet

**`pptx_converter.py`**
- `content_digest` — pixel-hash an image for dedup
- `ImageRef` / `Slide` / `ImageRegistry` — data model + dedup
- `validate_file` — `.ppt`/`.pptx` gate
- `ext_from_mime`, `xml_attr`, `slide_text`, `log_parse` — small helpers
- `shape_sort_key`, `image_from_shape`, `iter_pptx_blocks`, `parse_pptx` — `.pptx` parsing
- `parse_ppt` — legacy parsing (deck-order images)
- `proportional_mapping`, `place_legacy_images` — `.ppt` placement
- `render_xml` — XML output
- `pptx_converter`, `main` — entry point + CLI

**`llm.py`**
- `get_client` — resolve OpenAI / AzureOpenAI
- `_data_url` — image bytes → data URL (SVG→PNG)
- `describe_images` — concurrent vision descriptions
- `match_slides` — figure→slide inference with order constraints
