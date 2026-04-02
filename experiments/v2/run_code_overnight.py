#!/usr/bin/env python3
"""
Overnight code experiments on full 150-problem set.

Three experiments, parallelized by problem range:
  1. Haiku code (all 4 strategies): haiku_single, haiku_critique, haiku_autoreason, sonnet_single
  2. Sonnet 4.6 code (3 strategies): s46_single, s46_critique, s46_autoreason
  3. Best-of-N on code: haiku_best_of_6 vs haiku_autoreason vs sonnet_single

Usage:
    python run_code_overnight.py --experiment haiku --start 0 --end 50
    python run_code_overnight.py --experiment s46 --start 0 --end 50
    python run_code_overnight.py --experiment best_of_n --start 0 --end 50
    python run_code_overnight.py --experiment haiku --start 0 --end 150  # all at once
    python run_code_overnight.py --summarize  # just print results from saved files
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
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

HAIKU = "openrouter/anthropic/claude-3.5-haiku"
SONNET = "anthropic/claude-sonnet-4-20250514"
SONNET46 = "anthropic/claude-sonnet-4-6"
MAX_TOKENS = 4096
BUDGET = 6

SYSTEM = """You are an expert competitive programmer. You solve problems in Python.
Your solutions must read from stdin and write to stdout.
Always output complete, runnable Python code in a ```python block.
Do not use any external libraries beyond Python's standard library."""

ANALYSIS = """You solved a competitive programming problem but your solution failed some tests.

PROBLEM:
{desc}

YOUR SOLUTION:
```python
{code}
```

TEST RESULTS:
{feedback}

Before writing a new solution, analyze:
1. What is the core algorithmic problem?
2. Why did your approach fail?
3. What edge cases did you miss?
4. What alternative approaches could work?

Then write a complete corrected solution in a ```python block."""

CRITIQUE = """You solved a competitive programming problem but your solution failed some tests.

PROBLEM:
{desc}

YOUR SOLUTION:
```python
{code}
```

TEST RESULTS:
{feedback}

Fix the solution. Write a complete corrected solution in a ```python block."""


async def call_llm(system, user, model, temperature=0.7, max_retries=8):
    for attempt in range(max_retries):
        try:
            response = await litellm.acompletion(
                model=model, messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ], temperature=temperature, max_tokens=MAX_TOKENS
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


def extract_code(text):
    if "```python" in text:
        return text.split("```python")[1].split("```")[0].strip()
    if "```" in text:
        code = text.split("```")[1]
        return code.lstrip("\n").split("```")[0].strip()
    return text.strip()


def run_test(code, input_str, expected, timeout=10):
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            result = subprocess.run(
                [sys.executable, f.name],
                input=input_str, capture_output=True, text=True, timeout=timeout
            )
            os.unlink(f.name)
            actual = result.stdout.strip()
            passed = actual == expected.strip()
            return {"passed": passed, "stdout": actual, "expected": expected.strip(),
                    "stderr": result.stderr[:500] if result.stderr else "",
                    "status": "pass" if passed else "wrong_answer"}
    except subprocess.TimeoutExpired:
        try: os.unlink(f.name)
        except: pass
        return {"passed": False, "status": "timeout", "stdout": "", "expected": expected.strip(), "stderr": ""}
    except Exception as e:
        return {"passed": False, "status": "runtime_error", "stdout": "", "expected": expected.strip(), "stderr": str(e)[:500]}


def evaluate(code, problem, use_private=False):
    tests = problem["public_tests"]
    pub = [run_test(code, i, o) for i, o in zip(tests["input"], tests["output"])]
    priv = []
    if use_private and "private_tests" in problem:
        pt = problem["private_tests"]
        priv = [run_test(code, i, o) for i, o in zip(pt["input"], pt["output"])]
    return {
        "pass_public": all(r["passed"] for r in pub),
        "pass_private": all(r["passed"] for r in priv) if priv else None,
        "public_results": pub, "private_results": priv,
    }


def fmt_feedback(ev):
    lines = []
    for i, r in enumerate(ev["public_results"]):
        s = "PASS" if r["passed"] else "FAIL"
        lines.append(f"Test {i+1}: {s}")
        if not r["passed"]:
            if r["status"] == "timeout": lines.append("  TLE")
            elif r["status"] == "runtime_error": lines.append(f"  RE: {r['stderr'][:200]}")
            else:
                lines.append(f"  Expected: {r['expected'][:150]}")
                lines.append(f"  Got:      {r['stdout'][:150]}")
    return "\n".join(lines)


def make_prompt(problem):
    desc = problem["description"]
    pub = problem["public_tests"]
    ex = "".join(f"\n--- Example {i+1} ---\nInput:\n{inp.strip()}\nOutput:\n{out.strip()}\n"
                 for i, (inp, out) in enumerate(zip(pub["input"], pub["output"])))
    return f"Solve this competitive programming problem in Python.\n\n{desc}\n{ex}\nComplete Python solution reading stdin, writing stdout."


async def strat_single(problem, model, budget=BUDGET):
    prompt = make_prompt(problem)
    best_code, best_score = None, -1
    for _ in range(budget):
        resp = await call_llm(SYSTEM, prompt, model, 0.7)
        code = extract_code(resp)
        ev = evaluate(code, problem)
        score = sum(1 for r in ev["public_results"] if r["passed"])
        if score > best_score:
            best_score = score
            best_code = code
        if ev["pass_public"]: break
    return best_code


async def strat_critique(problem, model, budget=BUDGET):
    prompt = make_prompt(problem)
    resp = await call_llm(SYSTEM, prompt, model, 0.7)
    code = extract_code(resp)
    for _ in range(budget - 1):
        ev = evaluate(code, problem)
        if ev["pass_public"]: break
        resp = await call_llm(SYSTEM, CRITIQUE.format(
            desc=problem["description"], code=code, feedback=fmt_feedback(ev)), model, 0.7)
        code = extract_code(resp)
    return code


async def strat_autoreason(problem, author_model, budget=BUDGET):
    prompt = make_prompt(problem)
    resp = await call_llm(SYSTEM, prompt, author_model, 0.7)
    best_code = extract_code(resp)
    best_ev = evaluate(best_code, problem)
    if best_ev["pass_public"]: return best_code

    for _ in range(budget - 1):
        fb = fmt_feedback(best_ev)
        resp = await call_llm(SYSTEM, ANALYSIS.format(
            desc=problem["description"], code=best_code, feedback=fb), author_model, 0.7)
        new_code = extract_code(resp)
        new_ev = evaluate(new_code, problem)
        if new_ev["pass_public"]: return new_code
        new_s = sum(1 for r in new_ev["public_results"] if r["passed"])
        old_s = sum(1 for r in best_ev["public_results"] if r["passed"])
        if new_s >= old_s:
            best_code, best_ev = new_code, new_ev
    return best_code


async def strat_best_of_n(problem, model, n=BUDGET):
    """Generate N, return best by public test score."""
    prompt = make_prompt(problem)
    tasks = [call_llm(SYSTEM, prompt, model, 0.7) for _ in range(n)]
    resps = await asyncio.gather(*tasks, return_exceptions=True)
    best_code, best_score = None, -1
    for resp in resps:
        if isinstance(resp, Exception): continue
        code = extract_code(resp)
        ev = evaluate(code, problem)
        score = sum(1 for r in ev["public_results"] if r["passed"])
        if score > best_score:
            best_score = score
            best_code = code
    return best_code


EXPERIMENTS = {
    "haiku": {
        "haiku_single": lambda p: strat_single(p, HAIKU),
        "haiku_critique": lambda p: strat_critique(p, HAIKU),
        "haiku_autoreason": lambda p: strat_autoreason(p, HAIKU),
        "sonnet_single": lambda p: strat_single(p, SONNET),
    },
    "s46": {
        "s46_single": lambda p: strat_single(p, SONNET46),
        "s46_critique": lambda p: strat_critique(p, SONNET46),
        "s46_autoreason": lambda p: strat_autoreason(p, SONNET46),
    },
    "best_of_n": {
        "haiku_best6": lambda p: strat_best_of_n(p, HAIKU),
        "haiku_autoreason": lambda p: strat_autoreason(p, HAIKU),
        "sonnet_single": lambda p: strat_single(p, SONNET),
    },
}


async def run_experiment(exp_name, problems, start, end, out_dir):
    strats = EXPERIMENTS[exp_name]
    out_dir.mkdir(parents=True, exist_ok=True)
    subset = problems[start:end]

    print(f"Experiment: {exp_name} | Problems {start}-{end} ({len(subset)})")
    print(f"Strategies: {list(strats.keys())}\n")

    for idx, problem in enumerate(subset):
        global_idx = start + idx
        pid = problem.get("id", f"p{global_idx}")
        tier = problem.get("tier", "?")
        print(f"[{global_idx+1}/{len(problems)}] {pid} ({tier})")

        for sname, sfn in strats.items():
            rf = out_dir / f"{pid}_{sname}.json"
            if rf.exists():
                r = json.loads(rf.read_text())
                pub = "PASS" if r.get("pass_public") else "FAIL"
                priv = "PASS" if r.get("pass_private") else "FAIL"
                print(f"  {sname:<25} pub={pub} priv={priv} (cached)")
                continue

            try:
                code = await sfn(problem)
                ev = evaluate(code, problem, use_private=True)
                r = {
                    "problem_id": pid, "tier": tier, "strategy": sname,
                    "pass_public": ev["pass_public"],
                    "pass_private": ev.get("pass_private"),
                    "public_passed": sum(1 for x in ev["public_results"] if x["passed"]),
                    "public_total": len(ev["public_results"]),
                    "private_passed": sum(1 for x in ev["private_results"] if x["passed"]) if ev["private_results"] else 0,
                    "private_total": len(ev["private_results"]) if ev["private_results"] else 0,
                }
                rf.write_text(json.dumps(r, indent=2))
                pub = "PASS" if r["pass_public"] else "FAIL"
                priv = "PASS" if r.get("pass_private") else "FAIL"
                print(f"  {sname:<25} pub={pub} priv={priv}")
            except Exception as e:
                print(f"  {sname:<25} ERROR: {e}")
                rf.write_text(json.dumps({"problem_id": pid, "tier": tier, "strategy": sname, "error": str(e)}, indent=2))


def summarize(out_dir, exp_name):
    results = []
    for f in sorted(out_dir.glob("*.json")):
        if f.name == "summary.json": continue
        results.append(json.loads(f.read_text()))

    strats = list(EXPERIMENTS.get(exp_name, {}).keys())
    if not strats:
        strats = list(set(r.get("strategy") for r in results if r.get("strategy")))

    print(f"\n{'='*60}")
    print(f"SUMMARY: {exp_name} ({out_dir.name})")
    print(f"{'='*60}")

    for sname in strats:
        sr = [r for r in results if r.get("strategy") == sname and "error" not in r]
        if not sr: continue
        pub = sum(1 for r in sr if r.get("pass_public"))
        priv = sum(1 for r in sr if r.get("pass_private"))
        n = len(sr)
        print(f"\n  {sname}:")
        print(f"    Public:  {pub}/{n} ({pub/n*100:.0f}%)")
        print(f"    Private: {priv}/{n} ({priv/n*100:.0f}%)")
        for tier in ["easy", "medium", "hard"]:
            tr = [r for r in sr if r.get("tier") == tier]
            if tr:
                tp = sum(1 for r in tr if r.get("pass_public"))
                tpr = sum(1 for r in tr if r.get("pass_private"))
                print(f"      {tier}: pub={tp}/{len(tr)} priv={tpr}/{len(tr)}")

    # Save summary
    summary = {}
    for sname in strats:
        sr = [r for r in results if r.get("strategy") == sname and "error" not in r]
        if not sr: continue
        summary[sname] = {
            "n": len(sr),
            "public_pass": sum(1 for r in sr if r.get("pass_public")),
            "private_pass": sum(1 for r in sr if r.get("pass_private")),
            "by_tier": {}
        }
        for tier in ["easy", "medium", "hard"]:
            tr = [r for r in sr if r.get("tier") == tier]
            if tr:
                summary[sname]["by_tier"][tier] = {
                    "n": len(tr),
                    "public": sum(1 for r in tr if r.get("pass_public")),
                    "private": sum(1 for r in tr if r.get("pass_private")),
                }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", choices=list(EXPERIMENTS.keys()) + ["all"])
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=150)
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args()

    problems = json.loads(Path("/workspace/autoreason-code/problems_150.json").read_text())
    root = Path(__file__).parent

    if args.summarize:
        for exp in EXPERIMENTS:
            d = root / f"results_code_{exp}"
            if d.exists():
                summarize(d, exp)
        return

    exps = list(EXPERIMENTS.keys()) if args.experiment == "all" else [args.experiment]
    for exp in exps:
        out_dir = root / f"results_code_{exp}"
        await run_experiment(exp, problems, args.start, args.end, out_dir)
        summarize(out_dir, exp)


if __name__ == "__main__":
    asyncio.run(main())
