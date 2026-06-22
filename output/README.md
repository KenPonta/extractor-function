# Extraction outputs — `Panel TFP Project Slide.pptx`

Markdown produced by `pptx/pptx_to_markdown.py` (clean, production module), on **gpt-4.1**.

| file | `--method` | how the model is used |
|------|-----------|------------------------|
| `placeholder.md` | `placeholder` | native text extracted free; each **image** (incl. picture-*fill* charts) described once and spliced into its slot. Cheapest when visuals are real embedded images. |
| `routed.md` | `routed` | each slide routed by heuristic; text slides extracted natively, visual slides rendered to a 1-page PDF and read by the model (concurrent). Best on text-heavy decks. |
| `whole.md` | `whole` | the whole deck rendered to one PDF, transcribed in a single call. Simplest; best on visual-heavy decks. |

## Run

    export OPENAI_API_KEY=sk-...
    python pptx/pptx_to_markdown.py "Panel TFP Project Slide.pptx" --method placeholder
    python pptx/pptx_to_markdown.py "Panel TFP Project Slide.pptx" --method routed -o output/routed.md
    python pptx/pptx_to_markdown.py "Panel TFP Project Slide.pptx" --method whole

Default output path is `output/<deck name>.md`. `routed` and `whole` require LibreOffice
(`soffice`) installed; `placeholder` only needs LibreOffice if the deck contains SVG images
that need rasterizing (PyMuPDF handles that).
