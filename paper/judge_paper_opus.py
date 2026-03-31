#!/usr/bin/env python3
"""Run just Opus 4.6 on the paper."""

import asyncio
import os
from pathlib import Path

def load_dotenv(path):
    if not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())

load_dotenv(os.path.expanduser("~/.hermes/.env"))

import litellm
litellm.suppress_debug_info = True

PAPER_TEXT = Path("/root/autoreason-experiment/paper/autoreason.tex").read_text()

JUDGE_PROMPT = """You are a senior ML researcher reviewing a paper for a top venue (NeurIPS/ICML). 
Give a thorough, honest review. Be specific. Cite section numbers and table/figure numbers when referencing content.

Structure your review as:

## Summary
One paragraph summarizing what the paper does and claims.

## Strengths (be specific, cite sections)
Number each strength. Explain WHY it's a strength, not just that it exists.

## Weaknesses (be specific, cite sections)
Number each weakness. For each, explain the impact on the paper's claims and suggest a concrete fix if possible.

## Questions for Authors
Specific questions that, if answered well, would change your assessment.

## Minor Issues
Typos, formatting, unclear sentences, missing references, etc.

## Overall Assessment
Would you accept, weak accept, borderline, weak reject, or reject? Why? What is the single most important thing the authors should address?

---

Here is the paper (LaTeX source):

"""

async def main():
    print("Running Opus 4.6 review...")
    response = await litellm.acompletion(
        model="anthropic/claude-opus-4-6",
        messages=[
            {"role": "system", "content": "You are a senior ML researcher and experienced peer reviewer."},
            {"role": "user", "content": JUDGE_PROMPT + PAPER_TEXT},
        ],
        temperature=0.3,
        max_tokens=8192,
    )
    result = response.choices[0].message.content
    print(f"\n{'='*70}")
    print(f"JUDGE: Opus 4.6")
    print(f"{'='*70}\n")
    print(result)

    out = Path("/root/autoreason-experiment/paper/reviews/review_opus_46.md")
    out.write_text(f"# Review: Opus 4.6\n\n{result}\n")
    print(f"\nSaved to {out}")

if __name__ == "__main__":
    asyncio.run(main())
