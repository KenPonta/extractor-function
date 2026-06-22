#!/usr/bin/env python3
"""
measure.py — one-off harness: run the 3 methods in pptx_to_markdown.py, capture
runtime + token usage, and score each output against a reference Markdown file.

Does NOT modify the clean module: it wraps OpenAI's responses.create to tally usage.

    python measure.py "deck.pptx" reference.md
"""
from __future__ import annotations

import re
import sys
import threading
import time
from pathlib import Path

import pptx_to_markdown as M

PRICE = {"input": 2.00, "output": 8.00}  # gpt-4.1 USD / 1M tokens


class Tracker:
    def __init__(self):
        self.calls = self.inp = self.out = 0
        self._lock = threading.Lock()

    def add(self, resp):
        u = getattr(resp, "usage", None)
        with self._lock:
            self.calls += 1
            if u:
                self.inp += getattr(u, "input_tokens", 0) or 0
                self.out += getattr(u, "output_tokens", 0) or 0


def wrapped_client(tracker: Tracker):
    from openai import OpenAI
    client = OpenAI()
    orig = client.responses.create

    def create(*a, **k):
        resp = orig(*a, **k)
        tracker.add(resp)
        return resp

    client.responses.create = create
    return client


_WORD = re.compile(r"[a-zA-Z]{3,}")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_STOP = set("the and for that with this from are was its has have not but you all can".split())


def words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)} - _STOP


def numbers(text: str) -> set[str]:
    return set(_NUM.findall(text))


def recall(ref_set: set[str], out_set: set[str]) -> float:
    return 100.0 * len(ref_set & out_set) / len(ref_set) if ref_set else 0.0


def main() -> None:
    pptx_path = Path(sys.argv[1])
    ref_path = Path(sys.argv[2])
    ref = ref_path.read_text(encoding="utf-8")
    ref_w, ref_n = words(ref), numbers(ref)

    rows = []
    outdir = Path("output")
    outdir.mkdir(exist_ok=True)

    for name in ("placeholder", "routed", "whole"):
        tracker = Tracker()
        M._client = lambda t=tracker: wrapped_client(t)  # patch factory for this run
        t0 = time.perf_counter()
        md = M.METHODS[name](pptx_path)
        wall = time.perf_counter() - t0
        (outdir / f"measured-{name}.md").write_text(md, encoding="utf-8")

        cost = tracker.inp / 1e6 * PRICE["input"] + tracker.out / 1e6 * PRICE["output"]
        rows.append({
            "method": name, "calls": tracker.calls, "wall": wall,
            "inp": tracker.inp, "out": tracker.out, "cost": cost,
            "words": len(words(md)), "word_recall": recall(ref_w, words(md)),
            "num_recall": recall(ref_n, numbers(md)),
        })
        print(f"  {name}: done ({wall:.1f}s, {tracker.calls} calls)", file=sys.stderr)

    print(f"\nDeck: {pptx_path.name}   model: {M.MODEL}   "
          f"reference: {ref_path.name} ({len(ref_w)} content words, {len(ref_n)} numbers)\n")
    head = (f"{'method':12} {'calls':>5} {'wall_s':>7} {'in_tok':>8} {'out_tok':>8} "
            f"{'cost$':>8} {'words':>6} {'word%':>6} {'num%':>6}")
    print(head)
    print("-" * len(head))
    for r in rows:
        print(f"{r['method']:12} {r['calls']:>5} {r['wall']:>7.1f} {r['inp']:>8} "
              f"{r['out']:>8} {r['cost']:>8.4f} {r['words']:>6} "
              f"{r['word_recall']:>5.1f}% {r['num_recall']:>5.1f}%")
    print("\nword% / num% = share of the reference's content words / numbers that appear "
          "in each output (higher = more complete vs ground truth).")


if __name__ == "__main__":
    main()
