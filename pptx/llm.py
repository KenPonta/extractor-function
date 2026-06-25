"""LLM config and calls: vision descriptions + figure-to-slide matching.

Kept separate from parsing/rendering so all model config and API I/O live in one place.
Functions take plain data (no Slide/ImageRef types) so this module has no project imports.
"""
import base64
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# --- config ----------------------------------------------------------------- #
DEFAULT_MODEL = "gpt-4.1"           # vision model (for Azure, the deployment name)
DEFAULT_MAX_WORKERS = 8             # concurrent description requests
IMAGE_DETAIL = "high"               # vision detail level
PLACEMENT_SLIDE_TEXT_CAP = 600      # chars of slide text sent to the placement model
RASTER_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

IMAGE_PROMPT = (
    "This image was taken from a presentation slide. If it is a chart, graph, table, "
    "diagram, or figure, describe its content as plain text: title, axis labels and "
    "ranges, legend/series, and the data, trends, or relationships it conveys. If it is "
    "a logo, icon, or purely decorative background with no information, reply with exactly: "
    "(decorative, no data). Do not invent anything not visible, and do not wrap your reply "
    "in a code fence."
)

PLACEMENT_PROMPT = (
    "You are placing figures back into a slide deck saved from legacy .ppt, which lost the "
    "figure-to-slide links. Below are the slides (number + text) and the figures with "
    "descriptions, IN THE ORDER THEY APPEAR IN THE DECK. Assign each figure to the one slide "
    "whose text it most plausibly belongs to, judging by matching titles/topics. Because the "
    "figures are already in deck order, the slide numbers you assign MUST be non-decreasing "
    "(figure N's slide >= figure N-1's slide). Reply with ONLY a JSON object mapping figure "
    "id to slide number, e.g. {\"1\": 1, \"2\": 5, \"3\": 5}. No prose, no code fence."
)


# --- client ----------------------------------------------------------------- #
def get_client(client=None):
    """The given client, or a default OpenAI() from OPENAI_* env vars."""
    if client is not None:
        return client
    from openai import OpenAI
    return OpenAI()


def _data_url(blob: bytes, ext: str) -> str:
    if ext == "svg":
        import fitz
        blob = fitz.open(stream=blob, filetype="svg")[0].get_pixmap().tobytes("png")
        ext = "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext if ext in RASTER_EXT else "png")
    return f"data:image/{mime};base64,{base64.b64encode(blob).decode('ascii')}"


# --- vision description ------------------------------------------------------ #
def describe_images(images, *, model=DEFAULT_MODEL, max_workers=DEFAULT_MAX_WORKERS,
                    prompt=IMAGE_PROMPT, client=None):
    """Set each image's .description in place via a vision model, concurrently.

    images: objects with .blob, .ext, .image_id; .description is written here.
    """
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


# --- figure-to-slide matching ----------------------------------------------- #
def match_slides(slides, figures, *, model=DEFAULT_MODEL, client=None) -> dict | None:
    """Ask the model which slide each figure belongs to; return {figure_id: slide} or None.

    slides:  [(number, text), ...] in deck order.   figures: [(id, description), ...] in deck order.
    Assignments are clamped non-decreasing, so the model can pick a slide within the right
    region but cannot reorder the deck. Returns None on any failure so the caller can fall back.
    """
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
        replies = json.loads(re.sub(r"^```(?:json)?|```$", "", raw).strip())  # tolerate a code fence
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
        target = min(max(target, prev), valid[-1])          # clamp into [prev, last]
        target = next(n for n in valid if n >= target)      # snap forward to a real slide
        mapping[fid] = prev = target
    logger.info("placed %d figures via %s", len(figures), model)
    return mapping
