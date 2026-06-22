# `placeholder_extractor.py` — Line-by-Line Study Guide

Read this next to the source. Every line is explained in order. Where a line uses a
Python feature you might get asked about, there's a **▸ concept** note so you can name it.
At the end there's a cheat-sheet of all the language features in one place.

---

## A. Header & imports (lines 1–44)

```python
#!/usr/bin/env python3
```
The **shebang**. Lets you run the file directly (`./placeholder_extractor.py`) by telling
the OS to execute it with `python3`. Harmless when you run it as `python …` instead.

```python
"""Extract a PowerPoint deck to Markdown using native text + image placeholders. ..."""
```
The **module docstring** — documentation for the whole file. Two practical roles: it shows
up in `help()`, and `main()` reuses it as the CLI help text (`description=__doc__`). The
Strategy/Dependencies/Environment sections explain the approach, what to `pip install`, and
that the API key is only needed when there are images.

```python
from __future__ import annotations
```
Makes all type hints **lazy** (stored as strings, not evaluated at runtime). Two benefits:
you can write modern hints like `tuple[bytes, str] | None` on older Pythons, and there's no
runtime cost for annotations. **▸ concept: postponed evaluation of annotations (PEP 563).**

```python
import argparse        # parse command-line arguments
import base64          # encode image bytes for the data: URL
import hashlib         # SHA-1 fingerprint of images (for dedup)
import logging         # progress messages to stderr
import os              # read the OPENAI_API_KEY environment variable
import sys             # stderr stream for logging config
from concurrent.futures import ThreadPoolExecutor   # run image calls in parallel
from dataclasses import dataclass, field            # typed record classes
from pathlib import Path                             # filesystem paths
```
Standard-library imports, each pulled in for exactly one job (comment shows which). Importing
only what you use is part of "clean."

```python
from pptx import Presentation              # open a .pptx and access its slides/shapes
from pptx.enum.shapes import MSO_SHAPE_TYPE # enum to identify shape kinds (PICTURE, GROUP…)
from pptx.oxml.ns import qn                # build namespaced XML tag names for lookups
```
The three things we need from **python-pptx**. `qn` ("qualified name") is the namespace
helper used later to find the `<a:blip>` element correctly.

---

## B. Module-level setup (lines 46–61)

```python
__all__ = ["PlaceholderExtractor", "ExtractorConfig"]
```
Declares the **public API**: the two names exported by `from placeholder_extractor import *`.
Signals "these are the supported entry points; everything else is internal." **▸ concept: `__all__`.**

```python
logger = logging.getLogger(__name__)
```
Creates a logger named after the module. Using a module logger (instead of `print`) lets the
host app control verbosity. **▸ concept: module-level logger.**

```python
_MSO_FILL_PICTURE = 6                       # MSO_FILL.PICTURE: a shape filled with an image
```
A named constant for the magic number `6` (the enum value meaning "this shape's fill is a
picture"). Naming it makes the detection code self-explaining. The leading `_` marks it private.

```python
_RASTER_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
```
The image formats the vision API accepts directly. A **set** because we only do fast
membership tests (`ext in _RASTER_EXT`). Anything not in here (e.g. `svg`) needs conversion.

```python
_IMAGE_PROMPT = ( "This image was taken from a presentation slide. ..." )
```
The instruction sent with **every** image. Worth knowing each clause, because you can be asked
"why does it output what it does":
- *"extract its content as clean Markdown: title, axis labels…"* → tells it to extract **data**, not just caption.
- *"if it is a logo/icon/decorative… reply exactly (decorative — no data)"* → suppresses noise from backgrounds.
- *"Do not invent anything not visible"* → reduces hallucination.
- *"Output raw Markdown only; do not wrap in a code fence"* → fixes the ```` ```markdown ```` wrapping quirk.

**▸ concept:** the parentheses with adjacent strings is **implicit string concatenation** —
Python joins the pieces into one string at compile time.

---

## C. Configuration dataclass (lines 67–74)

```python
@dataclass(frozen=True)
class ExtractorConfig:
    """Tunable settings for an extraction run."""
    model: str = "gpt-4.1"
    image_detail: str = "high"
    max_workers: int = 8
    prompt: str = _IMAGE_PROMPT
```
- `@dataclass` auto-generates `__init__`, `__repr__`, `__eq__` from the field list — you write
  the fields, Python writes the boilerplate. **▸ concept: dataclass.**
- `frozen=True` makes instances **immutable** (you can't reassign `config.model` after creation).
  Good for settings: they can't change mid-run. **▸ concept: frozen dataclass.**
- Each `name: type = default` is a field with a default, so `ExtractorConfig()` works with no
  arguments, and `ExtractorConfig(model="gpt-4o")` overrides just one.

---

## D. The data model (lines 80–109)

```python
@dataclass(frozen=True)
class TextBlock:
    text: str
```
A run of native text. Frozen because once read, it never changes.

```python
@dataclass(frozen=True)
class ImageBlock:
    image_id: int
```
A **placeholder**: it holds only an id, not image bytes. This is the pointer that lets many
copies of one image share a single description.

```python
@dataclass
class ImageRef:
    image_id: int
    blob: bytes
    ext: str
    description: str = ""
```
One **unique** image. Note it's **not** frozen — `description` starts empty and gets filled in
after the model runs (`image.description = …`), so the object must be mutable.

```python
@dataclass
class Slide:
    number: int
    blocks: list[TextBlock | ImageBlock] = field(default_factory=list)
```
One slide = its number + an **ordered list** of blocks (the list order *is* the reading order).
- `field(default_factory=list)` means "default to a **new empty list** each time." You can't
  write `blocks: list = []` because that single list would be **shared** by every instance — a
  classic Python bug. `default_factory` makes a fresh one per object. **▸ concept: mutable default / `default_factory`.**

---

## E. `_image_from_shape` — the detector (lines 115–137)

```python
def _image_from_shape(shape) -> tuple[bytes, str] | None:
```
Takes one shape, returns `(bytes, extension)` if it's an image, otherwise `None`. The
`| None` return type tells callers "this may find nothing."

```python
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        try:
            image = shape.image
            return image.blob, image.ext.lower()
        except Exception:
            return None
```
**Case 1 — a real picture shape.** `shape.image` is python-pptx's built-in accessor; `.blob`
is the raw bytes, `.ext` the format. `.lower()` normalizes `"PNG"`→`"png"`. The `try/except`
guards against linked/broken images that have no retrievable bytes — return `None` rather than crash.

```python
    try:
        if int(shape.fill.type) == _MSO_FILL_PICTURE:
            blip = shape._element.find(".//" + qn("a:blip"))
            if blip is not None:
                rid = blip.get(qn("r:embed"))
                part = shape.part.related_part(rid)
                return part.blob, part.partname.split(".")[-1].lower()
    except Exception:
        return None
    return None
```
**Case 2 — a picture used as a *fill*** (the trick that finds chart PNGs others miss):
- `int(shape.fill.type) == _MSO_FILL_PICTURE` → this shape is filled with an image.
- `shape._element.find(".//" + qn("a:blip"))` → search the shape's raw XML for the `<a:blip>`
  element (the "blip" holds the image reference). `.//` means "anywhere inside"; `qn("a:blip")`
  produces the namespaced tag name so the search actually matches. **▸ concept: namespaced XML lookup.**
- `blip.get(qn("r:embed"))` → read the relationship id (e.g. `"rId3"`) off the blip.
- `shape.part.related_part(rid)` → resolve that id to the stored image part inside the zip.
- `part.blob` is the bytes; `part.partname.split(".")[-1].lower()` takes the extension from the
  filename (`/ppt/media/image5.png` → `png`).
- Final `return None` = "this shape carries no image."

---

## F. `_sort_key` — reading order (lines 140–144)

```python
def _sort_key(shape) -> tuple[int, int]:
    top = shape.top if isinstance(shape.top, int) else 0
    left = shape.left if isinstance(shape.left, int) else 0
    return top, left
```
Returns `(top, left)` so a list of shapes can be `sorted()` top-to-bottom then left-to-right
(PowerPoint stores shapes in z-order, not visual order). The `isinstance(... , int) else 0`
guards against `None` positions (some shapes have no explicit position). **▸ concept: a sort key
function returning a tuple → sorts by first element, then second.**

---

## G. `_iter_blocks` — the walker (lines 147–172)

```python
def _iter_blocks(shapes, register):
```
A **generator** that walks shapes and **yields** blocks one at a time. `register` is a callback
that dedups an image and returns its id. **▸ concept: generator function (uses `yield`).**

```python
    for shape in sorted(shapes, key=_sort_key):
```
Visit shapes in reading order, using the key from section F.

```python
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_blocks(shape.shapes, register)
            continue
```
A group contains nested shapes, so **recurse** into it. `yield from` re-emits every block the
recursive call produces. `continue` skips to the next shape. **▸ concept: recursion + `yield from`.**

```python
        image = _image_from_shape(shape)
        if image is not None:
            yield ImageBlock(register(*image))
            continue
```
Ask the detector if this shape is an image. If so, `register(*image)` dedups it (the `*` unpacks
the `(blob, ext)` tuple into `register(blob, ext)`) and returns the id, which we wrap in an
`ImageBlock` and yield. **▸ concept: argument unpacking with `*`.**

```python
        if getattr(shape, "has_text_frame", False):
            text = shape.text_frame.text.strip()
            if text:
                yield TextBlock(text)
```
If the shape holds text, pull and trim it; yield a `TextBlock` only if non-empty. `getattr(...,
False)` is a safe check — not every shape has `has_text_frame`, so we default to `False` instead
of risking an `AttributeError`. **▸ concept: `getattr` with a default.**

```python
        if getattr(shape, "has_table", False):
            rows = [" | ".join(c.text.strip() for c in row.cells)
                    for row in shape.table.rows
                    if any(c.text.strip() for c in row.cells)]
            if rows:
                yield TextBlock("\n".join(rows))
```
If it's a table, build one `"a | b | c"` string per row, skipping fully-empty rows, then yield
them joined by newlines. **▸ concept: list comprehension with a filter (`if any(...)`).**

---

## H. Image → data URL (lines 178–187)

```python
def _svg_to_png(svg_bytes: bytes) -> bytes:
    import fitz
    return fitz.open(stream=svg_bytes, filetype="svg")[0].get_pixmap().tobytes("png")
```
Rasterizes an SVG to PNG (the vision API can't read SVG). `import fitz` is **inside** the
function — a **lazy import** so decks without SVGs never load PyMuPDF. Reads the SVG as a one-page
document, takes page `[0]`, renders it to a pixmap, returns PNG bytes. **▸ concept: lazy import.**

```python
def _data_url(blob: bytes, ext: str) -> str:
    if ext == "svg":
        blob, ext = _svg_to_png(blob), "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext if ext in _RASTER_EXT else "png")
    return f"data:image/{mime};base64,{base64.b64encode(blob).decode('ascii')}"
```
Turns bytes into the `data:` URL the API wants. Converts SVG first, picks a valid MIME type
(`jpg`→`jpeg`, anything unknown→`png`), base64-encodes the bytes, and formats the URL.
**▸ concepts: ternary expression `A if cond else B`, f-string.**

---

## I. The extractor class (lines 193–274)

```python
class PlaceholderExtractor:
    def __init__(self, config: ExtractorConfig | None = None):
        self.config = config or ExtractorConfig()
```
Holds the config. `config or ExtractorConfig()` means "use the passed config, or a default one
if `None`." **▸ concept: `or` as a default-value idiom.**

```python
    def extract(self, pptx_path: Path) -> str:
        slides, images = self._parse(pptx_path)
        if images:
            self._describe_all(images)
        return self._render(slides, {img.image_id: img for img in images})
```
The public method = the whole pipeline. The last line builds a `{id: ImageRef}` lookup with a
**dict comprehension** and hands it to `_render`. **▸ concept: dict comprehension.**

```python
    def _parse(self, pptx_path: Path) -> tuple[list[Slide], list[ImageRef]]:
        registry: dict[str, ImageRef] = {}

        def register(blob: bytes, ext: str) -> int:
            digest = hashlib.sha1(blob).hexdigest()
            ref = registry.get(digest)
            if ref is None:
                ref = ImageRef(len(registry) + 1, blob, ext)
                registry[digest] = ref
            return ref.image_id
```
`registry` maps an image **fingerprint** → `ImageRef`. `register` is a **closure** — a function
defined inside `_parse` that "remembers" `registry`. It hashes the bytes; if that hash is new,
it creates an `ImageRef` with the next id (`len(registry)+1`) and stores it; either way it
returns the id. This is the **dedup engine**. **▸ concepts: closure, `hashlib.sha1().hexdigest()`.**

```python
        presentation = Presentation(str(pptx_path))
        slides = [
            Slide(number, list(_iter_blocks(slide.shapes, register)))
            for number, slide in enumerate(presentation.slides, start=1)
        ]
```
Open the deck, then build a `Slide` for each one. `enumerate(..., start=1)` gives 1-based slide
numbers. `list(_iter_blocks(...))` drains the generator into the slide's block list, passing
`register` so images dedup as they're found. **▸ concepts: `enumerate(start=1)`, draining a generator with `list()`.**

```python
        images = list(registry.values())
        placements = sum(isinstance(b, ImageBlock) for s in slides for b in s.blocks)
        logger.info("%d slides, %d unique images (%d placements)",
                    len(slides), len(images), placements)
        return slides, images
```
`images` = the unique set. `placements` counts every image *occurrence* (incl. duplicates) by
summing booleans — `True` counts as 1. The log line is where you saw `16 slides, 19 unique images
(25 placements)`. **▸ concept: `sum()` over booleans; lazy `%s` logging.**

```python
    def _describe_all(self, images: list[ImageRef]) -> None:
        client = self._client()
        workers = min(self.config.max_workers, len(images))
        logger.info("describing %d images via %s (%d concurrent)",
                    len(images), self.config.model, workers)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pool.map(lambda img: self._describe(client, img), images)
```
Build the client once, cap threads at `min(max_workers, len(images))` (no point spawning more
threads than images), then `pool.map` runs `_describe` on every image **concurrently**. The
`with` block waits for all of them to finish before exiting. **▸ concepts: `ThreadPoolExecutor`,
context manager (`with`), `lambda`.**

```python
    def _describe(self, client, image: ImageRef) -> None:
        try:
            response = client.responses.create(
                model=self.config.model,
                input=[{"role": "user", "content": [
                    {"type": "input_text", "text": self.config.prompt},
                    {"type": "input_image",
                     "image_url": _data_url(image.blob, image.ext),
                     "detail": self.config.image_detail}]}],
            )
            image.description = (response.output_text or "").strip()
        except Exception as exc:
            logger.warning("image %d failed: %s", image.image_id, exc)
            image.description = f"_[image description failed: {exc}]_"
```
One model call. The `input` is a single user message with two content parts: the **text prompt**
and the **image** (as a data URL, at the configured detail). The result is stored **on the image
object** (`image.description = …`) — that mutation is why `ImageRef` isn't frozen. The `(… or
"").strip()` guards against a `None` output. The `try/except` isolates failures so one bad image
becomes an inline note instead of a crash. **▸ concept: in-place mutation as the "return".**

```python
    @staticmethod
    def _render(slides: list[Slide], by_id: dict[int, ImageRef]) -> str:
        sections = []
        for slide in slides:
            parts = []
            for block in slide.blocks:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
                else:
                    desc = by_id[block.image_id].description or "_[no description]_"
                    parts.append(f"**[Image {block.image_id}]**\n\n{desc}")
            body = "\n\n".join(parts) if parts else "_[no content]_"
            sections.append(f"## Slide {slide.number}\n\n{body}")
        return "\n\n---\n\n".join(sections) + "\n"
```
The assembler. For each slide, walk its blocks: a `TextBlock` is emitted verbatim; an
`ImageBlock` is **looked up by id** and replaced with `**[Image n]**` + its description (the
splice-back). Slides become `## Slide N`, joined by `---` rules. It's a `@staticmethod` because
it needs no instance state — pure inputs → output. **▸ concepts: `@staticmethod`, `isinstance`
dispatch, `or` fallback.**

```python
    @staticmethod
    def _client():
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set, but the deck has images to describe.")
        from openai import OpenAI
        return OpenAI()
```
Builds the OpenAI client. Checks the key first and fails with a clear message if missing. The
`from openai import OpenAI` is **lazy** — a text-only deck never reaches here, so it needs neither
the key nor the package. `OpenAI()` reads the key from the environment automatically.

---

## J. CLI (lines 280–304)

```python
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
```
The command-line entry. `argv=None` makes it **testable** (you can call `main(["deck.pptx"])`
in a test; if `None`, argparse reads real `sys.argv`). `description=__doc__` reuses the module
docstring as help; `RawDescriptionHelpFormatter` keeps its formatting intact.

```python
    parser.add_argument("pptx", type=Path, help="path to the .pptx file")
    parser.add_argument("-o", "--out", type=Path, help="output .md path (default: output/<name>.md)")
    parser.add_argument("-m", "--model", default=ExtractorConfig.model, help="OpenAI model")
    parser.add_argument("--detail", default=ExtractorConfig.image_detail,
                        choices=["low", "high", "auto"], help="image detail level")
    args = parser.parse_args(argv)
```
Defines the arguments: a required `pptx` path, optional `--out`, `--model` (defaulting to the
config's default), and `--detail` restricted to three `choices`. `parse_args(argv)` reads them.

```python
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not args.pptx.exists():
        parser.error(f"file not found: {args.pptx}")
```
Turn on INFO logging to stderr (plain messages, no prefixes), silence the noisy per-request
`httpx` logs, and fail early with a clean error if the file is missing.

```python
    out_path = args.out or Path("output") / f"{args.pptx.stem}.md"
    config = ExtractorConfig(model=args.model, image_detail=args.detail)
    markdown = PlaceholderExtractor(config).extract(args.pptx)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    logger.info("written to %s", out_path)
```
Pick the output path (default `output/<name>.md`; `args.pptx.stem` is the filename without
extension; `/` joins paths via `pathlib`). Build the config from the args, run the extractor,
make sure the output folder exists (`mkdir(parents=True, exist_ok=True)`), write the file, log
where it went. **▸ concept: `pathlib` `/` path joining, `.stem`.**

```python
if __name__ == "__main__":
    main()
```
The standard guard: run `main()` only when the file is executed directly, **not** when it's
imported as a library. **▸ concept: `if __name__ == "__main__"`.**

---

## K. Cheat-sheet — Python features in this file

If someone asks "what language feature is that," here's the full list, each tied to where it appears:

| feature | where | one-line explanation |
|---|---|---|
| postponed annotations | `from __future__ import annotations` | type hints stored as strings, no runtime cost |
| module docstring as CLI help | `description=__doc__` | reuse the top docstring for `--help` |
| `__all__` | line 46 | declares the public API |
| module logger | `logging.getLogger(__name__)` | log instead of print, host controls level |
| named constant for a magic number | `_MSO_FILL_PICTURE = 6` | `6` means "picture fill" |
| set for membership tests | `_RASTER_EXT` | fast `ext in …` checks |
| implicit string concatenation | `_IMAGE_PROMPT` | adjacent strings join into one |
| dataclass / frozen / default_factory | config + data model | auto-generated, immutable, safe mutable defaults |
| `| None` return + `try/except` | `_image_from_shape` | "may find nothing"; never crash |
| namespaced XML lookup | `qn("a:blip")`, `.find(".//…")` | correctly locate OOXML elements |
| tuple sort key | `_sort_key` | sort by top, then left |
| generator / `yield` / `yield from` | `_iter_blocks` | stream blocks; recurse into groups |
| `getattr(obj, name, default)` | text/table checks | safe attribute access |
| argument unpacking `*image` | `register(*image)` | spread a tuple into args |
| list / dict comprehension | `_parse`, `extract` | build collections concisely |
| closure | `register` inside `_parse` | inner function remembers `registry` |
| `enumerate(start=1)` | `_parse` | 1-based numbering |
| `sum()` over booleans | `placements` | count Trues |
| `ThreadPoolExecutor` + `with` + `lambda` | `_describe_all` | parallel calls, auto-joined |
| lazy import | `import fitz`, `from openai import OpenAI` | load heavy deps only when needed |
| in-place mutation as result | `image.description = …` | worker writes onto the object |
| `@staticmethod` | `_render`, `_client` | method that needs no `self` |
| `isinstance` dispatch | `_render` | branch on block type |
| `or` fallback idiom | `config or …`, `desc or …` | default when falsy |
| ternary expression | `_data_url` mime | `A if cond else B` |
| f-strings | throughout | inline string formatting |
| `pathlib` `/` and `.stem` | `main` | path building |
| `if __name__ == "__main__"` | bottom | run-as-script guard |

---

## L. How to rehearse

1. Read this once end-to-end with the source open beside it.
2. Cover the explanations and try to narrate each line from the code alone.
3. For any line you stumble on, check the **▸ concept** note — that's usually the gap.
4. Final test: explain the file out loud in three passes — *pipeline* (3 stages), *data*
   (the 5 records), *line-by-line* (this guide). If you can do all three, you know it cold.
```
