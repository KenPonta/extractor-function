import os
import re
import json
import base64
import logging
from concurrent.futures import ThreadPoolExecutor
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

# Model + request configuration (model is the Azure deployment name).
DEFAULT_MODEL = "gpt-4.1-deployment"     # vision model / Azure deployment name
DEFAULT_MAX_WORKERS = 8                  # concurrent description requests
IMAGE_DETAIL = "high"                    # vision detail level
PLACEMENT_SLIDE_TEXT_CAP = 600           # chars of slide text sent to the placement model
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


#Custom exception for LLM call errors
class LLMError(RuntimeError):
    """Raised when an LLM request cannot be completed."""

# Functionality: Read a required environment variable and validate that it exists.
# Return: The environment variable value as a string.
# Used by: get_azure_openai_client().
def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise LLMError(f"Missing required environment variable: {name}")
    return value

# Functionality: Create an authenticated Azure OpenAI client from environment settings.
# Return: A configured AzureOpenAI client.
# Used by: describe_images() and match_slides().
def get_azure_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_version=get_required_env("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=get_required_env("AZURE_OPENAI_ENDPOINT"),
        api_key=get_required_env("AZURE_OPENAI_API_KEY"),
        timeout=30,
        max_retries=2,
    )

# Functionality: Encode an image's bytes as a base64 data URL for vision input.
# Return: A data URL string containing the image MIME type and base64 content.
# Used by: describe_images().
def encode_image_to_data_url(blob: bytes, ext: str) -> str:
    if ext == "svg":  # rasterize vector to PNG; the vision API takes raster only
        import fitz
        blob = fitz.open(stream=blob, filetype="svg")[0].get_pixmap().tobytes("png")
        ext = "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext if ext in RASTER_EXT else "png")
    return f"data:image/{mime};base64,{base64.b64encode(blob).decode('ascii')}"

# Functionality: Describe each image with the vision model, concurrently, in place.
# Return: None (each image's .description attribute is set).
# Used by: pptx_converter().
def describe_images(images, *, model=DEFAULT_MODEL, max_workers=DEFAULT_MAX_WORKERS,
                    prompt=IMAGE_PROMPT, client=None):
    """images: objects with .blob, .ext, .image_id; .description is written here."""
    client = client or get_azure_openai_client()
    workers = min(max_workers, len(images))
    logger.info("describing %d images via %s (%d concurrent)", len(images), model, workers)

    def describe(image):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": encode_image_to_data_url(image.blob, image.ext),
                        "detail": IMAGE_DETAIL}}]}])
            image.description = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("image %d failed: %s", image.image_id, exc)
            image.description = f"[image description failed: {exc}]"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        pool.map(describe, images)

# Functionality: Ask the model which slide each figure belongs to, in deck order.
# Return: A {figure_id: slide_number} dict, with assignments clamped non-decreasing.
# Used by: place_legacy_images() in pptx_converter.
def match_slides(slides, figures, *, model=DEFAULT_MODEL, client=None) -> dict:
    # slides: [(number, text), ...] in deck order.   figures: [(id, description), ...] in deck order.
    # Placement is always LLM-driven (no heuristic fallback), so API/JSON errors propagate;
    # only a single omitted figure is tolerated (kept on the prior slide).
    client = client or get_azure_openai_client()
    slide_lines = [f"Slide {n}: {(text or '')[:PLACEMENT_SLIDE_TEXT_CAP]}" for n, text in slides]
    figure_lines = [f"Figure {i}: {desc or '(no description)'}" for i, desc in figures]
    user = "Slides:\n" + "\n".join(slide_lines) + "\n\nFigures (in deck order):\n" + "\n".join(figure_lines)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": PLACEMENT_PROMPT},
                  {"role": "user", "content": user}])
    raw = (response.choices[0].message.content or "").strip()
    replies = json.loads(re.sub(r"^```(?:json)?|```$", "", raw).strip())  # tolerate a code fence

    valid = sorted(n for n, _ in slides)
    mapping, prev = {}, valid[0]
    for fid, _ in figures:
        try:
            target = int(replies[str(fid)])
        except (KeyError, ValueError, TypeError):
            logger.warning("placement model omitted figure %s; keeping it on slide %s", fid, prev)
            target = prev
        target = min(max(target, prev), valid[-1])          # clamp into [prev, last]
        target = next(n for n in valid if n >= target)      # snap forward to a real slide
        mapping[fid] = prev = target
    logger.info("placed %d figures via %s", len(figures), model)
    return mapping
