#!/usr/bin/env python3
"""
Cross-model judges: use GPT-4o and Gemini as judges instead of the same Claude model.

Tests whether autoreason's advantage is real or an artifact of same-model preference bias.
If cross-model judges produce similar rankings, the finding is robust.
If they diverge, the paper needs to acknowledge model-family bias.

We compare final outputs from tasks 1 and 4 using:
- Claude Sonnet 4 judges (control, existing)
- GPT-4o judges
- Gemini 2.5 Flash judges
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

JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_JUDGES = 7  # per model

JUDGE_MODELS = {
    "claude_sonnet4": "anthropic/claude-sonnet-4-20250514",
    "gpt4o": "openrouter/openai/gpt-4o",
    "gemini_flash": "openrouter/google/gemini-2.5-flash-preview",
}

COT_JUDGE_SYSTEM = "You are an independent evaluator. You have no authorship stake. Think carefully before deciding."

TASK_PROMPTS = {}
for i in range(1, 6):
    tp = Path(f"/workspace/autoreason/tasks/task_{i:02d}.md")
    if tp.exists():
        TASK_PROMPTS[i] = tp.read_text().strip()

COT_JUDGE_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Five teams independently produced proposals for this task using different improvement methods. Each started from the same initial draft.

{proposals}

For each version, think step by step:
1. How well does it accomplish the original task?
2. Is the content specific and actionable, or generic?
3. Is the level of detail appropriate — enough substance without bloat?
4. Are numbers and claims defensible?

After reasoning, rank all five from best to worst:

RANKING: [best], [second], [third], [fourth], [worst]

Where each slot is A, B, C, D, or E."""


async def call_llm(system, user, model, temperature=0.3, max_tokens=MAX_TOKENS, max_retries=8):
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
                print(f"    [Rate limited ({model}), retrying in {wait}s...]")
                await asyncio.sleep(wait)
            elif "not found" in err or "does not exist" in err or "invalid" in err:
                print(f"    Model {model} not available: {e}")
                return None
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


async def run_judge_panel(task_prompt, methods, model_name, model_id, out_dir):
    """Run a 7-judge panel using a specific model."""
    out_dir.mkdir(parents=True, exist_ok=True)
    
    method_names = list(methods.keys())
    labels = list("ABCDE")[:len(method_names)]
    
    judge_tasks = []
    judge_orders = []
    
    for _ in range(NUM_JUDGES):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(len(method_names))}
        judge_orders.append(order)
        parts = [f"VERSION {labels[i]}:\n---\n{methods[order[labels[i]]]}\n---"
                 for i in range(len(method_names))]
        judge_tasks.append(call_llm(
            COT_JUDGE_SYSTEM,
            COT_JUDGE_PROMPT.format(task_prompt=task_prompt, proposals="\n\n".join(parts)),
            model_id, JUDGE_TEMP, MAX_TOKENS))
    
    responses = await asyncio.gather(*judge_tasks, return_exceptions=True)
    
    borda = {n: 0 for n in method_names}
    first_place = {n: 0 for n in method_names}
    points = [5, 4, 3, 2, 1]
    valid = 0
    
    for j, (resp, order) in enumerate(zip(responses, judge_orders)):
        if isinstance(resp, Exception) or resp is None:
            print(f"    Judge {j+1} ({model_name}): ERROR")
            continue
        ranking = parse_ranking(resp, "".join(labels))
        if not ranking:
            print(f"    Judge {j+1} ({model_name}): PARSE FAILED")
            (out_dir / f"judge_{j+1}_raw.txt").write_text(str(resp))
            continue
        valid += 1
        mapped = [order.get(l, l) for l in ranking[:len(method_names)]]
        for pos, method in enumerate(mapped):
            if method in borda and pos < len(points):
                borda[method] += points[pos]
        if mapped[0] in first_place:
            first_place[mapped[0]] += 1
        print(f"    Judge {j+1} ({model_name}): {' > '.join(mapped[:3])}...")
        (out_dir / f"judge_{j+1}_raw.txt").write_text(resp)
    
    results = {
        "model": model_name, "model_id": model_id, "valid_judges": valid,
        "borda": borda, "first_place": first_place,
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    return results


async def main():
    root = Path(__file__).parent
    out_dir = root / "results_cross_model_judges"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Check which models are available
    available_models = {}
    for name, model_id in JUDGE_MODELS.items():
        try:
            resp = await call_llm("You are a test.", "Say 'ok'.", model_id, 0.0, 10)
            if resp:
                available_models[name] = model_id
                print(f"  ✓ {name} ({model_id})")
            else:
                print(f"  ✗ {name} ({model_id}) - not available")
        except Exception as e:
            print(f"  ✗ {name} ({model_id}) - {e}")
    
    if len(available_models) < 2:
        print("Need at least 2 models. Exiting.")
        return
    
    for task_num in [1, 4]:
        print(f"\n{'='*60}")
        print(f"Task {task_num}: Cross-Model Judge Comparison")
        print(f"{'='*60}")
        
        # Load final outputs (all generated by Claude)
        v1_dir = root / "results_v1_comparison" / f"task_{task_num:02d}"
        
        methods = {}
        for fname, mname in [
            ("v1_output.md", "autoreason"),
            ("baseline_critique_and_revise.md", "critique_revise"),
            ("baseline_harsh_critic.md", "harsh_critic"),
            ("baseline_improve_this.md", "improve_this"),
            ("baseline_conservative.md", "conservative"),
        ]:
            fp = v1_dir / fname
            if fp.exists():
                methods[mname] = fp.read_text()
        
        if len(methods) < 3:
            print(f"  Not enough outputs for task {task_num}, skipping")
            continue
        
        task_prompt = TASK_PROMPTS[task_num]
        
        # Run each judge model
        all_results = {}
        for model_name, model_id in available_models.items():
            print(f"\n  --- {model_name} judges ---")
            r = await run_judge_panel(
                task_prompt, methods, model_name, model_id,
                out_dir / f"task_{task_num:02d}_{model_name}")
            all_results[model_name] = r
        
        # Cross-model comparison table
        print(f"\n  Cross-Model Comparison (Task {task_num}):")
        print(f"  {'Method':<20}", end="")
        for mn in all_results:
            print(f"  {mn:>15}", end="")
        print()
        print(f"  {'-'*20}", end="")
        for mn in all_results:
            print(f"  {'-'*15}", end="")
        print()
        
        for method in methods:
            print(f"  {method:<20}", end="")
            for mn, r in all_results.items():
                b = r["borda"].get(method, 0)
                print(f"  {b:>15}", end="")
            print()
        
        # Save comparison
        (out_dir / f"task_{task_num:02d}_comparison.json").write_text(
            json.dumps(all_results, indent=2))
    
    # Rank correlation analysis
    print(f"\n{'='*60}")
    print("Rank Correlation Summary")
    print(f"{'='*60}")
    print("(Compare Borda rankings across judge models to check for same-model bias)")
    

if __name__ == "__main__":
    asyncio.run(main())
