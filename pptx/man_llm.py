import os
import base64
import hashlib
import mimetypes
from pathlib import Path
from openai import AzureOpenAI
from document_utils.image_resizing import resize_image

SUPPORTED_LLM_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}

#Custom exception for document extraction errors
class DocumentExtractionError(RuntimeError):
    """Raised when a document cannot be converted or extracted."""

# Functionality: Read a required environment variable and validate that it exists.
# Return: The environment variable value as a string.
# Used by: get_azure_openai_client() and describe_image_with_llm().
def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise DocumentExtractionError(f"Missing required environment variable: {name}")
    return value

# Functionality: Create an authenticated Azure OpenAI client from environment settings.
# Return: A configured AzureOpenAI client.
# Used by: describe_image_with_llm().
def get_azure_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_version=get_required_env("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=get_required_env("AZURE_OPENAI_ENDPOINT"),
        api_key=get_required_env("AZURE_OPENAI_API_KEY"),
        timeout=30,
        max_retries=2
    )

# Functionality: Encode a supported image as a base64 data URL for vision input.
# Return: A data URL containing the image MIME type and base64 content.
# Used by: describe_image_with_llm() and unit tests.
def encode_image_to_data_url(image_path: str | Path) -> str:
    """Convert image file to base64 data URL for OpenAI vision input."""
    image_path = Path(image_path)
    if not image_path.exists():
        raise DocumentExtractionError(f"Image file not found: {image_path}")
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type not in SUPPORTED_LLM_IMAGE_MIME_TYPES:
        raise DocumentExtractionError(
            f"Unsupported image MIME type for LLM: {mime_type or 'unknown'}"
        )
    with image_path.open("rb") as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:{mime_type};base64,{image_base64}"

# Functionality: Calculate stable size and SHA-256 metadata for an image file.
# Return: A dictionary containing size_bytes and sha256.
# Used by: DOC and DOCX extractors when creating image XML items.
def get_image_file_metadata(image_path: str | Path) -> dict[str, str]:
    """Return stable metadata that proves which image was analyzed."""
    image_path = Path(image_path)
    if not image_path.exists():
        raise DocumentExtractionError(f"Image file not found: {image_path}")
    image_bytes = image_path.read_bytes()
    return {
        "size_bytes": str(len(image_bytes)),
        "sha256": hashlib.sha256(image_bytes).hexdigest(),
    }

# Functionality: Resize, encode, and send an image to Azure OpenAI for description.
# Return: The generated image description as a stripped string.
# Used by: safe_describe_image_with_llm().
def describe_image_with_llm(image_path: str | Path) -> str:
    # DOC and DOCX extractors both call this function. Resize only the image
    # sent to the LLM while keeping the original extracted image unchanged.
    llm_image_path = resize_image(image_path)
    image_data_url = encode_image_to_data_url(llm_image_path)
    prompt = """
            You are analyzing an image extracted from a document.

            Describe the meaning of the image, not only the visible objects.

            Focus on:
            - What information this image adds to the document
            - Main message or purpose
            - Important text, labels, numbers, or relationships
            - Chart, diagram, table, screenshot, or workflow meaning if applicable

            Return only one concise XML-safe description.
            Do not use markdown.
            """
    try:
        client = get_azure_openai_client()
        response = client.responses.create(
            model=get_required_env("AZURE_OPENAI_DEPLOYMENT"),
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        },
                        {
                            "type": "input_image",
                            "image_url": image_data_url,
                            "detail": "auto",
                        },
                    ],
                }
            ],
            max_output_tokens=500,
            temperature=0.2,
        )
        return response.output_text.strip()
    except Exception as exc:
        raise DocumentExtractionError(str(exc)) from exc 
    
# Functionality: Describe an image without stopping extraction when an error occurs.
# Return: The image description, or an empty string when description fails.
# Used by: DOC and DOCX extractors as their default image describer.
def safe_describe_image_with_llm(image_path: str | Path) -> str:
    """Describe an image, but never stop document extraction."""
    try:
        return describe_image_with_llm(image_path)
    except Exception as exc:
        print(f"[WARN] Could not describe image {image_path}: {exc}")
        return ""