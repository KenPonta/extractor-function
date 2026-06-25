import argparse
import base64
import hashlib
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

logger = logging.getLogger(__name__)

_MSO_FILL_PICTURE = 6
_RASTER_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
_IMAGE_DETAIL = "high"

_IMAGE_PROMPT = (
    "This image was taken from a presentation slide. If it is a chart, graph, table, "
    "diagram, or figure, describe its content as plain text: title, axis labels and "
    "ranges, legend/series, and the data, trends, or relationships it conveys. If it is "
    "a logo, icon, or purely decorative background with no information, reply with exactly: "
    "(decorative, no data). Do not invent anything not visible, and do not wrap your reply "
    "in a code fence."
)


class ExtractorConfig:
    model = "gpt-4.1"
    max_workers = 8
    prompt = _IMAGE_PROMPT

    def __init__(self, model=model, max_workers=max_workers, prompt=prompt):
        self.model = model
        self.max_workers = max_workers
        self.prompt = prompt

class ImageRef:
    def __init__(self, image_id: int, blob: bytes, ext: str, description: str = ""):
        self.image_id = image_id
        self.blob = blob
        self.ext = ext
        self.description = description


class Slide:
    def __init__(self, number: int, blocks: list | None = None):
        self.number = number
        self.blocks = blocks if blocks is not None else []


def _validate_pptx(path) -> Path:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if path.suffix.lower() != ".pptx":
        raise ValueError(f"file type mismatch: {path.name}")
    return path


def _image_from_shape(shape) -> tuple[bytes, str] | None:
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        try:
            image = shape.image
            return image.blob, image.ext.lower()
        except Exception:
            return None
    try:
        if int(shape.fill.type) == _MSO_FILL_PICTURE:  # image used as a shape fill (often charts)
            blip = shape._element.find(".//" + qn("a:blip"))
            if blip is not None:
                rid = blip.get(qn("r:embed"))
                part = shape.part.related_part(rid)
                return part.blob, part.partname.split(".")[-1].lower()
    except Exception:
        return None
    return None


def _sort_key(shape) -> tuple[int, int]:
    top = shape.top if isinstance(shape.top, int) else 0
    left = shape.left if isinstance(shape.left, int) else 0
    return top, left


def _iter_blocks(shapes, register):
    for shape in sorted(shapes, key=_sort_key):
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_blocks(shape.shapes, register)
            continue

        image = _image_from_shape(shape)
        if image is not None:
            yield "image", register(*image)
            continue

        if getattr(shape, "has_text_frame", False):
            text = shape.text_frame.text.strip()
            if text:
                yield "text", text

        if getattr(shape, "has_table", False):
            rows = [" | ".join(cell.text.strip() for cell in row.cells)
                    for row in shape.table.rows
                    if any(cell.text.strip() for cell in row.cells)]
            if rows:
                yield "text", "\n".join(rows)


def _svg_to_png(svg_bytes: bytes) -> bytes:
    import fitz
    return fitz.open(stream=svg_bytes, filetype="svg")[0].get_pixmap().tobytes("png")


def _data_url(blob: bytes, ext: str) -> str:
    if ext == "svg":
        blob, ext = _svg_to_png(blob), "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext if ext in _RASTER_EXT else "png")
    return f"data:image/{mime};base64,{base64.b64encode(blob).decode('ascii')}"


def _xml_attr(value) -> str:
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


class PlaceholderExtractor:
    def __init__(self, config: ExtractorConfig | None = None):
        self.config = config or ExtractorConfig()

    def extract_xml(self, pptx_path: Path, data_type: str = "PPTX") -> str:
        slides, by_id = self._run(pptx_path)
        return self._render_xml(slides, by_id, Path(pptx_path).name, data_type=data_type)

    def _run(self, pptx_path: Path):
        pptx_path = _validate_pptx(pptx_path)
        slides, images = self._parse(pptx_path)
        if images:
            self._describe_all(images)
        return slides, {img.image_id: img for img in images}

    def _parse(self, pptx_path: Path):
        registry = {}

        def register(blob, ext):
            digest = hashlib.sha1(blob).hexdigest()
            ref = registry.get(digest)
            if ref is None:
                ref = ImageRef(len(registry) + 1, blob, ext)
                registry[digest] = ref
            return ref.image_id

        presentation = Presentation(str(pptx_path))
        slides = [Slide(number, list(_iter_blocks(slide.shapes, register)))
                  for number, slide in enumerate(presentation.slides, start=1)]
        images = list(registry.values())
        placements = sum(kind == "image" for s in slides for kind, _ in s.blocks)
        logger.info("%d slides, %d unique images (%d placements)",
                    len(slides), len(images), placements)
        return slides, images

    def _describe_all(self, images: list[ImageRef]):
        from openai import AzureOpenAI
        from openai import OpenAI
        client = OpenAI()
        # client = AzureOpenAI(
        #     api_version = api_verison,
        #     azure_endpoint= azure_endpoint,
        #     api_key = azure_api_key
        # )
        workers = min(self.config.max_workers, len(images))
        logger.info("describing %d images via %s (%d concurrent)",
                    len(images), self.config.model, workers)

        def describe(image):
            try:
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": self.config.prompt},
                        {"type": "image_url",
                         "image_url": _data_url(image.blob, image.ext),
                         "detail": _IMAGE_DETAIL}]}],

                )
                image.description = (response.choices[0].message.content or "").strip()
            except Exception as exc:
                logger.warning("image %d failed: %s", image.image_id, exc)
                image.description = f"[image description failed: {exc}]"

        with ThreadPoolExecutor(max_workers=workers) as pool:
            pool.map(describe, images)

    def _render_xml(self, slides, by_id, filename, index=1, data_type="PPTX") -> str:
        slide_texts = []
        for slide in slides:
            parts = [f"Slide {slide.number}"]
            for kind, value in slide.blocks:
                if kind == "text":
                    parts.append(value)
                else:
                    description = by_id[value].description or "(no description)"
                    parts.append(f"[Image {value}]\n{description}")
            slide_texts.append("\n\n".join(parts))
        body = "\n\n".join(slide_texts)
        return (
            "<documents>\n"
            f'  <document index="{index}" filename="{_xml_attr(filename)}"'
            f' data-type="{_xml_attr(data_type)}">\n'
            f"{body}\n"
            "  </document>\n"
            "</documents>\n"
        )


def pptx_to_xml(file_path, output_dir, config: ExtractorConfig | None = None,
                data_type: str = "PPTX") -> Path:
    src = Path(file_path)
    xml = PlaceholderExtractor(config).extract_xml(src, data_type=data_type)
    out_path = Path(output_dir) / f"{src.stem}.xml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(xml, encoding="utf-8")
    return out_path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx", type=Path)
    parser.add_argument("-o", "--out", type=Path, default="output", help="output directory")
    parser.add_argument("-m", "--model", default=ExtractorConfig.model)
    parser.add_argument("--data-type", default="PPTX")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        out = pptx_to_xml(args.pptx, args.out, ExtractorConfig(model=args.model), args.data_type)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    logger.info("written to %s", out)


if __name__ == "__main__":
    main()
