import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "pptx"))
from placeholder_extractor import pptx_to_xml

pptx_to_xml(
    "/Users/pontakornkangvanwanich/extaction-function/Panel TFP Project Slide.pptx",
    "/Users/pontakornkangvanwanich/extaction-function/output",
)
