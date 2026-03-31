#!/usr/bin/env python3
"""
Run 4 baselines on the constrained 500-word pitch task with Sonnet 4.6,
then 7-judge blind panel comparing autoreason vs baselines.
"""

import asyncio
import json
import os
import random
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

MODEL = "anthropic/claude-sonnet-4-6"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096

AUTHOR_SYSTEM = "You are a senior consultant producing professional deliverables. Be specific, concrete, and practical."
COT_JUDGE_SYSTEM = "You are an independent evaluator. You have no authorship stake. Think carefully before deciding."

TASK_PROMPT = """You are pitching a developer notification infrastructure startup to YC partners. You have 2 minutes (approximately 500 words).

Base facts (use ALL of these, add nothing that isn't derivable from them):
- Product: API-first notification service handling push, email, SMS, in-app for apps with 1M-50M MAU
- Current traction: 47 paying customers, $38K MRR, 180M notifications/month delivered
- Team: 3 engineers (ex-Twilio, ex-AWS SNS), founded 8 months ago
- Key metric: 99.97% delivery rate vs industry avg 94%
- Pricing: usage-based, $0.001/notification after 100K free tier
- Problem: engineering teams spend 3-6 months building notification infrastructure that isn't their core product
- Competition: AWS SNS (low-level), OneSignal (marketing-focused), custom builds
- Ask: $2M seed for hiring 2 more engineers and SOC2 certification

Constraints:
- Maximum 500 words
- Must be a compelling narrative, not a feature list
- Every sentence must earn its place

Write the pitch."""

BASELINE_PROMPTS = {
    "improve_this": "Improve this pitch. Make it stronger, more compelling, and tighter. Stay within 500 words.\n\n---\n{current}\n---\n\nProduce the complete improved pitch.",
    "critique_and_revise": "Review this pitch critically. Find real problems. Then revise to fix every problem. Stay within 500 words.\n\n---\n{current}\n---\n\nProduce the complete revised pitch.",
    "conservative": "Make changes only if genuinely wrong or weak. If already good, leave as is. Stay within 500 words.\n\n---\n{current}\n---\n\nProduce the complete pitch.",
    "harsh_critic": "Find every flaw in this pitch. Rewrite from scratch to address all of them. Stay within 500 words.\n\n---\n{current}\n---\n\nProduce the complete revised pitch.",
}

COT_JUDGE_5WAY = """ORIGINAL TASK:
---
{task_prompt}
---

INITIAL OUTPUT (starting point for all methods):
---
{initial_output}
---

Five teams independently improved the initial output using different methods:

{proposals}

For each version, think step by step:
1. How compelling is this as a 2-minute YC pitch?
2. Does it use all the base facts without adding unsupported claims?
3. Is it a narrative or a feature list?
4. Does every sentence earn its place, or is there filler?
5. Would a YC partner want to hear more after this?

After reasoning, rank all five from best to worst:

RANKING: [best], [second], [third], [fourth], [worst]"""


async def call_llm(system, user, model, temperature, max_tokens, max_retries=8):
    for attempt in range(max_retries):
        try:
            response = await litellm.acompletion(
                model=model, messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ], temperature=temperature, max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err or "overloaded" in err or "529" in err:
                wait = min((2 ** attempt) * 5, 120)
                await asyncio.sleep(wait)
            else:
                if attempt < max_retries - 1:
                    await asyncio.sleep(10)
                else:
                    raise
    raise RuntimeError(f"Failed after {max_retries} retries")


def parse_ranking(text, valid_chars="ABCDE"):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw.upper() if c in valid_chars]
            if len(items) >= 3:
                return items
    return None


async def main():
    root = Path(__file__).parent
    out_dir = root / "results_46_constrained_eval"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load autoreason output
    ar_output = (root / "results_46_v3_constrained" / "autoreason" / "final_output.md").read_text()
    initial_a = (root / "results_46_v3_constrained" / "autoreason" / "initial_a.md").read_text()

    print(f"Constrained Task Evaluation: Autoreason vs Baselines")
    print(f"Model: {MODEL}")
    print(f"Autoreason output: {len(ar_output.split())} words (converged pass 10)")
    print(f"Initial A: {len(initial_a.split())} words")
    print(f"{'='*60}\n")

    # Run baselines (15 passes each)
    baseline_outputs = {}
    for bname, bprompt in BASELINE_PROMPTS.items():
        bf = out_dir / f"baseline_{bname}.md"
        if bf.exists():
            baseline_outputs[bname] = bf.read_text()
            print(f"  {bname}: {len(baseline_outputs[bname].split())}w (cached)")
        else:
            print(f"  {bname}: running 15 passes...", end="", flush=True)
            current = initial_a
            for p in range(15):
                current = await call_llm(AUTHOR_SYSTEM, bprompt.format(current=current), MODEL, AUTHOR_TEMP, MAX_TOKENS)
            bf.write_text(current)
            baseline_outputs[bname] = current
            print(f" {len(current.split())}w")

    # 7-judge blind panel
    print(f"\n  Running 7-judge CoT panel...")
    all_outputs = {"autoreason_constrained": ar_output}
    all_outputs.update(baseline_outputs)
    method_names = list(all_outputs.keys())
    labels = list("ABCDE")

    judge_tasks = []
    judge_orders = []
    for _ in range(7):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(5)}
        judge_orders.append(order)
        parts = [f"VERSION {labels[i]}:\n---\n{all_outputs[order[labels[i]]]}\n---" for i in range(5)]
        judge_tasks.append(call_llm(COT_JUDGE_SYSTEM, COT_JUDGE_5WAY.format(
            task_prompt=TASK_PROMPT, initial_output=initial_a, proposals="\n\n".join(parts)
        ), MODEL, JUDGE_TEMP, MAX_TOKENS))

    responses = await asyncio.gather(*judge_tasks, return_exceptions=True)

    borda = {n: 0 for n in method_names}
    first_place = {n: 0 for n in method_names}
    points = [5, 4, 3, 2, 1]
    valid = 0

    for j, (resp, order) in enumerate(zip(responses, judge_orders)):
        if isinstance(resp, Exception):
            print(f"  Judge {j+1}: ERROR")
            continue
        ranking = parse_ranking(resp)
        if not ranking:
            print(f"  Judge {j+1}: PARSE FAILED")
            (out_dir / f"judge_{j+1}_raw.txt").write_text(resp)
            continue
        valid += 1
        mapped = [order.get(l, l) for l in ranking[:5]]
        for pos, method in enumerate(mapped):
            if method in borda and pos < len(points):
                borda[method] += points[pos]
        if mapped[0] in first_place:
            first_place[mapped[0]] += 1
        print(f"  Judge {j+1}: {', '.join(mapped[:3])}")

    sorted_methods = sorted(borda.items(), key=lambda x: -x[1])
    max_borda = valid * 5

    print(f"\n{'='*60}")
    print(f"Results ({valid} judges, max Borda = {max_borda}):\n")
    for name, score in sorted_methods:
        marker = " <-- autoreason" if "autoreason" in name else ""
        print(f"  {name:30s} Borda={score:3d}  1st={first_place.get(name,0)}{marker}")

    results = {
        "borda": borda,
        "first_place": first_place,
        "valid_judges": valid,
        "max_borda": max_borda,
        "word_counts": {k: len(v.split()) for k, v in all_outputs.items()},
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {out_dir / 'results.json'}")


if __name__ == "__main__":
    asyncio.run(main())
