"""Placeholder extractor for legacy binary PowerPoint (.ppt) files.

python-pptx cannot open the legacy OLE/binary .ppt format, so this module uses
`sharepoint-to-text` (import name: ``sharepoint2text``) to parse the deck, then
reuses the *format-independent* core of ``placeholder_extractor`` — the vision
image-description pipeline and the XML renderer — so .ppt and .pptx produce the
same <documents> output.

Install the parser:  pip install sharepoint-to-text

Note on fidelity: a legacy .ppt has no shape geometry, so there is no
layout-based reading order (slides come in deck order, text before images), no
group recursion, and no native tables (the .ppt format stores table text as
plain text runs). Vector images (WMF/EMF) cannot be rasterized here and are
skipped. For modern .pptx keep using placeholder_extractor — it is richer.
"""

import argparse
import hashlib
import logging
import sys
from pathlib import Path

import placeholder_extractor as px

logger = logging.getLogger(__name__)

# content_type on a PptImage is a MIME type ("image/png"); _data_url wants an ext.
_RASTER_MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
}


def _validate_ppt(path) -> Path:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if path.suffix.lower() != ".ppt":
        raise ValueError(f"file type mismatch: {path.name}")
    return path


def _ext_from_mime(content_type: str) -> str | None:
    """Map a PptImage MIME type to a raster extension, or None if unsupported."""
    return _RASTER_MIME_EXT.get((content_type or "").strip().lower())


class PptExtractor(px.PlaceholderExtractor):
    """Legacy-.ppt counterpart of PlaceholderExtractor.

    Reuses the parent's _describe_all (vision) and _render_xml (output); only the
    parse step (python-pptx -> sharepoint2text) and validation differ.
    """

    def extract_xml(self, ppt_path: Path, data_type: str = "PPT") -> str:
        slides, by_id = self._run(ppt_path)
        return self._render_xml(slides, by_id, Path(ppt_path).name, data_type=data_type)

    def _run(self, ppt_path: Path):
        ppt_path = _validate_ppt(ppt_path)
        slides, images = self._parse(ppt_path)
        if images:
            self._describe_all(images)
        return slides, {img.image_id: img for img in images}

    def _parse(self, ppt_path: Path):
        import sharepoint2text

        registry: dict[str, px.ImageRef] = {}

        def register(blob: bytes, ext: str) -> int:
            digest = hashlib.sha1(blob).hexdigest()
            ref = registry.get(digest)
            if ref is None:
                ref = px.ImageRef(len(registry) + 1, blob, ext)
                registry[digest] = ref
            return ref.image_id

        # read_file yields one ExtractionInterface per file; a single .ppt -> one PptContent.
        content = next(sharepoint2text.read_file(str(ppt_path)))

        slides = []
        skipped_vector = 0
        for unit in content.iterate_units():           # PptUnit per slide, in deck order
            blocks = []
            if unit.title:
                blocks.append(("text", unit.title.strip()))
            text = (unit.text or "").strip()            # body + other text, title excluded
            if text:
                blocks.append(("text", text))
            for img in unit.get_images():               # PptImage
                ext = _ext_from_mime(img.get_content_type())
                if ext is None:
                    skipped_vector += 1                 # WMF/EMF/etc. — can't rasterize
                    continue
                blob = img.get_bytes().read()
                if blob:
                    blocks.append(("image", register(blob, ext)))
            slides.append(px.Slide(unit.slide_number, blocks))

        images = list(registry.values())
        placements = sum(kind == "image" for s in slides for kind, _ in s.blocks)
        logger.info("%d slides, %d unique images (%d placements), %d vector images skipped",
                    len(slides), len(images), placements, skipped_vector)
        return slides, images


def ppt_to_xml(file_path, output_dir, config: px.ExtractorConfig | None = None,
               data_type: str = "PPT") -> Path:
    src = Path(file_path)
    xml = PptExtractor(config).extract_xml(src, data_type=data_type)
    out_path = Path(output_dir) / f"{src.stem}.xml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(xml, encoding="utf-8")
    return out_path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("ppt", type=Path)
    parser.add_argument("-o", "--out", type=Path, default="output", help="output directory")
    parser.add_argument("-m", "--model", default=px.ExtractorConfig.model)
    parser.add_argument("--data-type", default="PPT")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        out = ppt_to_xml(args.ppt, args.out, px.ExtractorConfig(model=args.model), args.data_type)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    logger.info("written to %s", out)


if __name__ == "__main__":
    main()
