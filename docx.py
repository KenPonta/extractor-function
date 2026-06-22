from docx2python import docx2python
import subprocess, tempfile
from pathlib import Path


file = '/Users/pontakornkangvanwanich/extaction-function/langchain-memory-overview-2.docx'
docx_content = docx2python(file)
print(docx_content.text)
docx_content.close()

def extract_docx(doc_path):
    file = 'doc_path'
    docx_content = docx2python(file)
    print(docx_content.text)
    docx_content.close()

def _convert_doc_to_docx(doc_path, out_dir):
    subprocess.run([
        "soffice", "--headless",
        "--convert-to", "docx:MS Word 2007 XML",
        "--outdir", str(out_dir), str(doc_path),
    ], check=True, capture_output=True)
    return Path(out_dir) / (Path(doc_path).stem + ".docx")
