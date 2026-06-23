import sys
from pathlib import Path

# placeholder_extractor.py lives in ../pptx, so put that folder on the import path.
sys.path.insert(0, str(Path(__file__).parent.parent / "pptx"))
