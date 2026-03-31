#!/usr/bin/env python3
"""
Run 3 diverse judge models on the autoreason paper.
Each judge gives verbose feedback on strengths, weaknesses, and specific suggestions.
"""

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

JUDGES = [
    {"model": "anthropic/claude-sonnet-4-6", "name": "Sonnet 4.6"},
    {"model": "anthropic/claude-opus-4-6", "name": "Opus 4.6"},
    {"model": "openrouter/google/gemini-2.5-pro", "name": "Gemini 2.5 Pro"},
]


async def call_llm(model, system, user, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                max_tokens=8192,
            )
            return response.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err or "overloaded" in err:
                wait = min((2 ** attempt) * 10, 120)
                print(f"  Rate limited on {model}, waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                if attempt < max_retries - 1:
                    print(f"  Error on {model}: {e}, retrying...")
                    await asyncio.sleep(10)
                else:
                    return f"ERROR: {e}"
    return "ERROR: max retries exceeded"


async def main():
    out_dir = Path("/root/autoreason-experiment/paper/reviews")
    out_dir.mkdir(exist_ok=True)

    print(f"Running {len(JUDGES)} judges on the paper...")
    print(f"Paper length: {len(PAPER_TEXT)} chars, ~{len(PAPER_TEXT.split())} words\n")

    tasks = []
    for judge in JUDGES:
        print(f"  Launching {judge['name']} ({judge['model']})...")
        tasks.append(call_llm(
            judge["model"],
            "You are a senior ML researcher and experienced peer reviewer.",
            JUDGE_PROMPT + PAPER_TEXT,
        ))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for judge, result in zip(JUDGES, results):
        if isinstance(result, Exception):
            print(f"\n{'='*70}")
            print(f"JUDGE: {judge['name']} — ERROR: {result}")
            continue

        print(f"\n{'='*70}")
        print(f"JUDGE: {judge['name']} ({judge['model']})")
        print(f"{'='*70}\n")
        print(result)

        # Save to file
        review_file = out_dir / f"review_{judge['name'].lower().replace(' ', '_').replace('.', '')}.md"
        review_file.write_text(f"# Review: {judge['name']}\n\n{result}\n")
        print(f"\n  Saved to {review_file}")


if __name__ == "__main__":
    asyncio.run(main())
