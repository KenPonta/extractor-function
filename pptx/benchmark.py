#!/usr/bin/env python3
"""
benchmark.py — compare two PPTX-understanding pipelines on cost (credits) and runtime.

  A) whole_pdf : render the whole deck to one PDF, feed it to the model in a single call
  B) routed    : weight each slide; extract text cheaply, send ONLY visual slides to vision
                 (reuses the helpers in pptx_extract.py)

"Credits" == tokens. OpenAI returns token usage on every response (`response.usage`), so
this harness sums input/output tokens for each pipeline, converts to USD with a price
table, and times each run. Run several trials to average out network/model latency.

    pip install python-pptx pymupdf openai
    export OPENAI_API_KEY=sk-...
    python benchmark.py deck.pptx -m gpt-5.5 --trials 3
    python benchmark.py deck.pptx --save-outputs   # also writes routed.md / whole_pdf.md to diff
"""
from __future__ import annotations

import argparse
import base64
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

from pptx import Presentation

import pptx_extract as px


# USD per 1M tokens — OpenAI list prices, June 2026. VERIFY at https://openai.com/api/pricing
# (Batch/Flex ~50% off; cached input is cheaper; requests above ~272K tokens use higher
#  long-context rates. Output values marked "approx" should be confirmed for your model.)
PRICES = {
    "gpt-5.5":      {"input": 5.00, "output": 30.00},
    "gpt-5.4":      {"input": 2.50, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "output": 6.00},    # output approx; verify
    "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
    "gpt-4.1":      {"input": 2.00, "output": 8.00},     # output approx; verify
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4o":       {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":  {"input": 0.15, "output": 0.60},
}

WHOLE_PDF_PROMPT = (
    "This is a full slide presentation exported as PDF. Transcribe every slide as clean "
    "Markdown, one '## Slide N' section per slide in order. Include all text, and describe "
    "any chart, diagram, table, or image and the data it conveys. Do not invent content."
)


def usage_of(resp) -> tuple[int, int]:
    """(input_tokens, output_tokens) from a Responses or Chat Completions usage object."""
    u = getattr(resp, "usage", None)
    if u is None:
        return 0, 0
    inp = getattr(u, "input_tokens", None)
    out = getattr(u, "output_tokens", None)
    if inp is None:                                  # Chat Completions naming
        inp = getattr(u, "prompt_tokens", 0)
    if out is None:
        out = getattr(u, "completion_tokens", 0)
    return int(inp or 0), int(out or 0)


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _blank(approach: str, n_slides: int) -> dict:
    return dict(approach=approach, n_slides=n_slides, n_calls=0,
                input_tokens=0, output_tokens=0, render_s=0.0, api_s=0.0, wall_s=0.0)


# --------------------------------------------------------------------------- #
# Pipeline B: per-slide routed
# --------------------------------------------------------------------------- #
def run_routed(client, pptx_path: Path, model: str, dpi: int):
    t0 = time.perf_counter()
    prs = Presentation(str(pptx_path))
    area = (prs.slide_width or 1) * (prs.slide_height or 1)
    slides = list(prs.slides)
    routed = [(i, px.route_slide(s, area)) for i, s in enumerate(slides, 1)]
    st = _blank("routed", len(routed))

    text_for = {i: px.extract_text(s)
                for (i, kind), s in zip(routed, slides) if kind == "text"}
    vision_pages = [i for i, k in routed if k == "vision"]
    st["n_calls"] = len(vision_pages)

    vis_text: dict[int, str] = {}
    if vision_pages:
        with tempfile.TemporaryDirectory() as tmp:
            wd = Path(tmp)
            tr = time.perf_counter()
            pdf = px.render_pptx_to_pdf(pptx_path, wd)
            slide_pdfs = px.split_pages_to_pdfs(pdf, vision_pages, wd)
            st["render_s"] = time.perf_counter() - tr
            for n in vision_pages:
                if n not in slide_pdfs:
                    vis_text[n] = "[render failed]"
                    continue
                ta = time.perf_counter()
                resp = client.responses.create(
                    model=model,
                    input=[{"role": "user", "content": [
                        {"type": "input_text", "text": px.VISION_PROMPT},
                        {"type": "input_file",
                         "filename": slide_pdfs[n].name,
                         "file_data": f"data:application/pdf;base64,{b64(slide_pdfs[n])}"}]}],
                )
                st["api_s"] += time.perf_counter() - ta
                a, b = usage_of(resp)
                st["input_tokens"] += a
                st["output_tokens"] += b
                vis_text[n] = (resp.output_text or "").strip()

    parts = []
    for i, kind in routed:
        body = text_for.get(i, "") if kind == "text" else vis_text.get(i, "")
        parts.append(f"## Slide {i} ({kind})\n\n{body}".rstrip())
    st["wall_s"] = time.perf_counter() - t0
    return "\n\n---\n\n".join(parts) + "\n", st


# --------------------------------------------------------------------------- #
# Pipeline A: whole deck -> one PDF -> one call
# --------------------------------------------------------------------------- #
def run_whole_pdf(client, pptx_path: Path, model: str, dpi: int):
    t0 = time.perf_counter()
    prs = Presentation(str(pptx_path))
    n_slides = len(prs.slides._sldIdLst)
    st = _blank("whole_pdf", n_slides)
    with tempfile.TemporaryDirectory() as tmp:
        wd = Path(tmp)
        tr = time.perf_counter()
        pdf = px.render_pptx_to_pdf(pptx_path, wd)
        st["render_s"] = time.perf_counter() - tr
        ta = time.perf_counter()
        resp = client.responses.create(
            model=model,
            input=[{"role": "user", "content": [
                {"type": "input_file", "filename": pdf.name,
                 "file_data": f"data:application/pdf;base64,{b64(pdf)}"},
                {"type": "input_text", "text": WHOLE_PDF_PROMPT}]}],
        )
        st["api_s"] = time.perf_counter() - ta
        st["n_calls"] = 1
        a, b = usage_of(resp)
        st["input_tokens"], st["output_tokens"] = a, b
        text = (resp.output_text or "").strip()
    st["wall_s"] = time.perf_counter() - t0
    return text + "\n", st


# --------------------------------------------------------------------------- #
# Cost + reporting
# --------------------------------------------------------------------------- #
def cost_usd(st: dict, model: str):
    p = PRICES.get(model)
    if not p:
        return None
    return st["input_tokens"] / 1e6 * p["input"] + st["output_tokens"] / 1e6 * p["output"]


def mean_stats(runs: list[dict]) -> dict:
    m = dict(approach=runs[0]["approach"], n_slides=runs[0]["n_slides"])
    for k in ("n_calls", "input_tokens", "output_tokens", "render_s", "api_s", "wall_s"):
        m[k] = statistics.mean(r[k] for r in runs)
    return m


def row(st: dict, model: str) -> str:
    c = cost_usd(st, model)
    cstr = f"${c:.4f}" if c is not None else "add price"
    return (f'{st["approach"]:9} | calls {st["n_calls"]:5.1f} | '
            f'in {st["input_tokens"]:>9.0f} | out {st["output_tokens"]:>7.0f} | '
            f'{cstr:>10} | render {st["render_s"]:5.1f}s | '
            f'api {st["api_s"]:6.1f}s | wall {st["wall_s"]:6.1f}s')


def _compare_with_client(client, pptx_path: Path, model: str,
                         trials: int, dpi: int, save_outputs: bool):
    runs = {"whole_pdf": [], "routed": []}
    last_text: dict[str, str] = {}
    for t in range(trials):
        wt, ws = run_whole_pdf(client, pptx_path, model, dpi)
        rt, rs = run_routed(client, pptx_path, model, dpi)
        runs["whole_pdf"].append(ws)
        runs["routed"].append(rs)
        last_text["whole_pdf"], last_text["routed"] = wt, rt
        print(f"trial {t + 1}/{trials} done", file=sys.stderr)

    mw, mr = mean_stats(runs["whole_pdf"]), mean_stats(runs["routed"])
    print(f"\nDeck: {pptx_path.name}   model: {model}   trials: {trials}   dpi: {dpi}")
    print(f"({mr['n_slides']:.0f} slides; routed sent {mr['n_calls']:.1f} to vision, "
          f"the rest extracted as text)\n")
    print(row(mw, model))
    print(row(mr, model))

    cw, cr = cost_usd(mw, model), cost_usd(mr, model)
    if cw and cr:
        print(f"\ncredits: routed = {cr / cw * 100:.0f}% of whole_pdf "
              f"(~{(1 - cr / cw) * 100:.0f}% cheaper)   |   "
              f"input tokens = {mr['input_tokens'] / max(mw['input_tokens'], 1) * 100:.0f}%   |   "
              f"wall time = {mr['wall_s'] / max(mw['wall_s'], 1e-9) * 100:.0f}% of whole_pdf")
    if save_outputs:
        for name, txt in last_text.items():
            Path(f"{name}.md").write_text(txt, encoding="utf-8")
        print("\nwrote routed.md and whole_pdf.md — diff them to confirm routed didn't drop content.")
    return mw, mr


def compare(pptx_path: Path, model: str, trials: int, dpi: int, save_outputs: bool):
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set.")
    from openai import OpenAI
    return _compare_with_client(OpenAI(), pptx_path, model, trials, dpi, save_outputs)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compare whole-PDF vs per-slide-routed PPTX extraction on cost and runtime."
    )
    ap.add_argument("pptx")
    ap.add_argument("-m", "--model", default=px.MODEL)
    ap.add_argument("--trials", type=int, default=1, help="repeat and average (smooths latency)")
    ap.add_argument("--dpi", type=int, default=px.RENDER_DPI)
    ap.add_argument("--save-outputs", action="store_true", help="write routed.md / whole_pdf.md")
    args = ap.parse_args()

    p = Path(args.pptx)
    if not p.exists():
        sys.exit(f"File not found: {p}")
    compare(p, args.model, args.trials, args.dpi, args.save_outputs)


if __name__ == "__main__":
    main()
