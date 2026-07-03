"""
Extract text and images from a legacy PowerPoint (.ppt) file using Spire.Presentation.

Install:  pip install Spire.Presentation.Free      # free edition (10-slide cap)
     or:  pip install spire.presentation           # commercial (evaluation watermark w/o license)

Usage:    python extract_ppt.py  input.ppt  output_folder
"""

import os
import sys
import json
from spire.presentation import Presentation, SlidePicture, PictureShape, IAutoShape, FillFormatType


def extract(ppt_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    img_dir = os.path.join(out_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    ppt = Presentation()
    ppt.LoadFromFile(ppt_path)          # works for .ppt and .pptx alike

    manifest = []       # structured record of everything we pull out
    img_count = 0

    def embed_of(shape):
        """Embedded image (IImageData) for a picture, picture-shape, OR picture-fill; else None."""
        if isinstance(shape, SlidePicture):
            return shape.PictureFill.Picture.EmbedImage
        if isinstance(shape, PictureShape):
            return shape.EmbedImage
        try:
            if shape.Fill.FillType == FillFormatType.Picture:       # chart pasted as a shape fill
                return shape.Fill.PictureFill.Picture.EmbedImage
        except Exception:
            pass
        return None

    def walk(shapes, slide_index, record):
        nonlocal img_count
        for shape in shapes:
            if type(shape).__name__ == "GroupShape":                # recurse into groups
                walk(shape.Shapes, slide_index, record)
                continue

            try:
                frame = shape.Frame
                box = {"x": round(frame.Left, 1), "y": round(frame.Top, 1),
                       "width": round(frame.Width, 1), "height": round(frame.Height, 1)}
            except Exception:
                box = {}

            if isinstance(shape, IAutoShape):                       # --- TEXT ---
                try:
                    text = (shape.TextFrame.Text or "").strip()
                except Exception:
                    text = ""
                if text:
                    record["texts"].append({"text": text, "box": box})

            embed = embed_of(shape)                                 # --- IMAGE (3 kinds) ---
            if embed is not None:
                filename = f"slide{slide_index + 1}_img{img_count}.png"
                embed.Image.Save(os.path.join(img_dir, filename))
                record["images"].append({"file": os.path.join("images", filename), "box": box})
                img_count += 1

    # Walk slides -> shapes (recursing groups) so we keep positional context
    for slide_index, slide in enumerate(ppt.Slides):
        slide_record = {"slide": slide_index + 1, "texts": [], "images": []}
        walk(slide.Shapes, slide_index, slide_record)
        manifest.append(slide_record)

    ppt.Dispose()

    # Write a JSON manifest describing what came from where
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Write a plain-text dump of all text
    with open(os.path.join(out_dir, "text.txt"), "w", encoding="utf-8") as f:
        for rec in manifest:
            f.write(f"===== Slide {rec['slide']} =====\n")
            for t in rec["texts"]:
                f.write(t["text"] + "\n")
            f.write("\n")

    print(f"Done. {len(manifest)} slides, {img_count} images extracted to '{out_dir}'.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_ppt.py  input.ppt  output_folder")
        sys.exit(1)
    extract(sys.argv[1], sys.argv[2])