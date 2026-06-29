"""Entry point: convert a .ppt/.pptx into placeholder XML via pptx/pptx_converter.py.

Usage:
    python run.py                # converts FILE below
    python run.py deck.pptx      # converts the file you pass as the first argument

Azure credentials are read from .env (see pptx/llm_ref.py). Set MODEL to your Azure
deployment name, or pass -m on pptx_converter's own CLI instead.
"""
import logging
import sys
from pathlib import Path

# pptx_converter.py and its sibling llm_ref.py live in ./pptx, so put that on the import path.
sys.path.insert(0, str(Path(__file__).parent / "pptx"))
from pptx_converter import pptx_converter

FILE = "Panel-2.ppt"        # input .ppt or .pptx (overridden by the first CLI arg if given)
OUTPUT_DIR = "output"       # writes <stem>.xml here
MODEL = None                # None -> use the module default; or set your Azure deployment name


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    file = sys.argv[1] if len(sys.argv) > 1 else FILE
    kwargs = {"model": MODEL} if MODEL else {}      # only override the model if one is set
    xml = pptx_converter(file, OUTPUT_DIR, **kwargs)
    print(xml)                                      # XML on stdout; logs go to stderr


if __name__ == "__main__":
    main()
