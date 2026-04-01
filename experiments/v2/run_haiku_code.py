#!/usr/bin/env python3
"""
Haiku+autoreason on CodeContests with Sonnet judges.
Objective ground truth via test cases — no LLM judge bias.

Compare:
  - Haiku single-pass (pass@6: 6 independent attempts)
  - Haiku critique-and-revise (1 attempt + 5 revisions)
  - Haiku autoreason (1 attempt + structured analysis + 4 revisions, Sonnet judges)
  - Sonnet single-pass (pass@6, the expensive baseline)

Use a subset of 30 problems (10 easy, 10 medium, 10 hard) for cost efficiency.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
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
MAX_TOKENS = 4096
BUDGET = 6  # total LLM calls per problem

SYSTEM_PROMPT = """You are an expert competitive programmer. You solve problems in Python.
Your solutions must read from stdin and write to stdout.
Always output complete, runnable Python code in a ```python block.
Do not use any external libraries beyond Python's standard library."""

ANALYSIS_PROMPT = """You solved a competitive programming problem but your solution failed some tests.

PROBLEM:
{problem_desc}

YOUR SOLUTION:
```python
{code}
```

TEST RESULTS:
{test_feedback}

Before writing a new solution, analyze:
1. What is the core algorithmic problem?
2. Why did your approach fail?
3. What edge cases did you miss?
4. What alternative approaches could work?

Then write a complete corrected solution in a ```python block."""

CRITIQUE_PROMPT = """You solved a competitive programming problem but your solution failed some tests.

PROBLEM:
{problem_desc}

YOUR SOLUTION:
```python
{code}
```

TEST RESULTS:
{test_feedback}

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
    """Extract Python code from markdown code blocks."""
    if "```python" in text:
        parts = text.split("```python")
        if len(parts) > 1:
            code = parts[1].split("```")[0]
            return code.strip()
    if "```" in text:
        parts = text.split("```")
        if len(parts) > 1:
            code = parts[1]
            if code.startswith("\n"):
                code = code[1:]
            return code.split("```")[0].strip()
    return text.strip()


def run_test(code, input_str, expected_output, timeout=10):
    """Run code with input and check output."""
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
            expected = expected_output.strip()
            passed = actual == expected
            return {
                "passed": passed, "stdout": actual, "expected": expected,
                "stderr": result.stderr[:500] if result.stderr else "",
                "status": "pass" if passed else "wrong_answer"
            }
    except subprocess.TimeoutExpired:
        return {"passed": False, "status": "timeout", "stdout": "", "expected": expected_output.strip(), "stderr": ""}
    except Exception as e:
        return {"passed": False, "status": "runtime_error", "stdout": "", "expected": expected_output.strip(), "stderr": str(e)[:500]}


def evaluate(code, problem, use_private=False):
    """Evaluate code against test cases."""
    tests = problem["public_tests"]
    results = []
    for inp, out in zip(tests["input"], tests["output"]):
        results.append(run_test(code, inp, out))

    private_results = []
    if use_private and "private_tests" in problem:
        ptests = problem["private_tests"]
        for inp, out in zip(ptests["input"], ptests["output"]):
            private_results.append(run_test(code, inp, out))

    return {
        "pass_public": all(r["passed"] for r in results),
        "pass_private": all(r["passed"] for r in private_results) if private_results else None,
        "public_results": results,
        "private_results": private_results,
    }


def format_feedback(eval_result):
    lines = []
    for i, r in enumerate(eval_result["public_results"]):
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"Test {i+1}: {status}")
        if not r["passed"]:
            if r["status"] == "timeout":
                lines.append("  Time limit exceeded")
            elif r["status"] == "runtime_error":
                lines.append(f"  Runtime error: {r['stderr'][:300]}")
            else:
                lines.append(f"  Expected: {r['expected'][:200]}")
                lines.append(f"  Got:      {r['stdout'][:200]}")
    return "\n".join(lines)


def make_problem_prompt(problem):
    desc = problem["description"]
    pub = problem["public_tests"]
    examples = ""
    for i, (inp, out) in enumerate(zip(pub["input"], pub["output"])):
        examples += f"\n--- Example {i+1} ---\nInput:\n{inp.strip()}\nOutput:\n{out.strip()}\n"
    return f"Solve this competitive programming problem in Python.\n\n{desc}\n{examples}\nWrite a complete Python solution that reads from stdin and writes to stdout."


async def strategy_single_pass(problem, model, budget=BUDGET):
    """Generate budget independent attempts, return best."""
    prompt = make_problem_prompt(problem)
    best_code, best_score = None, -1

    for i in range(budget):
        resp = await call_llm(SYSTEM_PROMPT, prompt, model, temperature=0.7)
        code = extract_code(resp)
        ev = evaluate(code, problem)
        score = sum(1 for r in ev["public_results"] if r["passed"])
        if score > best_score:
            best_score = score
            best_code = code
        if ev["pass_public"]:
            break

    return best_code


async def strategy_critique_revise(problem, model, budget=BUDGET):
    """Generate once, then critique-and-revise with test feedback."""
    prompt = make_problem_prompt(problem)
    resp = await call_llm(SYSTEM_PROMPT, prompt, model, temperature=0.7)
    code = extract_code(resp)

    for i in range(budget - 1):
        ev = evaluate(code, problem)
        if ev["pass_public"]:
            break
        feedback = format_feedback(ev)
        resp = await call_llm(SYSTEM_PROMPT, CRITIQUE_PROMPT.format(
            problem_desc=problem["description"], code=code, test_feedback=feedback
        ), model, temperature=0.7)
        code = extract_code(resp)

    return code


async def strategy_autoreason(problem, author_model, judge_model=SONNET, budget=BUDGET):
    """Generate, structured analysis, then revisions. Judge selects best."""
    prompt = make_problem_prompt(problem)

    # Call 1: initial generation
    resp = await call_llm(SYSTEM_PROMPT, prompt, author_model, temperature=0.7)
    code_a = extract_code(resp)
    ev_a = evaluate(code_a, problem)

    if ev_a["pass_public"]:
        return code_a

    # Call 2: structured analysis + revision
    feedback = format_feedback(ev_a)
    resp = await call_llm(SYSTEM_PROMPT, ANALYSIS_PROMPT.format(
        problem_desc=problem["description"], code=code_a, test_feedback=feedback
    ), author_model, temperature=0.7)
    code_b = extract_code(resp)

    best_code = code_a
    best_ev = ev_a

    # Check B
    ev_b = evaluate(code_b, problem)
    if ev_b["pass_public"]:
        return code_b
    score_a = sum(1 for r in ev_a["public_results"] if r["passed"])
    score_b = sum(1 for r in ev_b["public_results"] if r["passed"])
    if score_b > score_a:
        best_code = code_b
        best_ev = ev_b

    # Calls 3-6: further revisions with analysis
    for i in range(budget - 2):
        feedback = format_feedback(best_ev)
        resp = await call_llm(SYSTEM_PROMPT, ANALYSIS_PROMPT.format(
            problem_desc=problem["description"], code=best_code, test_feedback=feedback
        ), author_model, temperature=0.7)
        new_code = extract_code(resp)
        new_ev = evaluate(new_code, problem)

        if new_ev["pass_public"]:
            return new_code

        new_score = sum(1 for r in new_ev["public_results"] if r["passed"])
        best_score = sum(1 for r in best_ev["public_results"] if r["passed"])
        if new_score >= best_score:
            best_code = new_code
            best_ev = new_ev

    return best_code


async def main():
    root = Path(__file__).parent
    code_dir = Path("/workspace/autoreason-code")
    base_dir = root / "results_haiku_code"
    base_dir.mkdir(parents=True, exist_ok=True)

    # Load problems
    problems_file = code_dir / "problems_90.json"
    if not problems_file.exists():
        problems_file = code_dir / "problems.json"
    problems = json.loads(problems_file.read_text())

    # Sample 30: 10 per tier
    sampled = []
    for tier in ["easy", "medium", "hard"]:
        tier_problems = [p for p in problems if p.get("tier") == tier]
        sampled.extend(tier_problems[:10])

    if not sampled:
        # Fallback: just take first 30
        sampled = problems[:30]

    print(f"Haiku+Autoreason on Code ({len(sampled)} problems)")
    print(f"Author: {HAIKU}, Judge/Analysis: {SONNET}")
    print(f"Budget: {BUDGET} calls per problem\n")

    strategies = {
        "haiku_single": lambda p: strategy_single_pass(p, HAIKU),
        "haiku_critique": lambda p: strategy_critique_revise(p, HAIKU),
        "haiku_autoreason": lambda p: strategy_autoreason(p, HAIKU, SONNET),
        "sonnet_single": lambda p: strategy_single_pass(p, SONNET),
    }

    all_results = []
    for idx, problem in enumerate(sampled):
        pid = problem.get("id", problem.get("name", f"problem_{idx}"))
        tier = problem.get("tier", "unknown")
        print(f"\n[{idx+1}/{len(sampled)}] {pid} ({tier})")

        for strat_name, strat_fn in strategies.items():
            result_file = base_dir / f"{pid}_{strat_name}.json"
            if result_file.exists():
                r = json.loads(result_file.read_text())
                pub = "PASS" if r.get("pass_public") else "FAIL"
                priv = "PASS" if r.get("pass_private") else "FAIL"
                print(f"  {strat_name:<25} pub={pub} priv={priv} (cached)")
                all_results.append(r)
                continue

            try:
                code = await strat_fn(problem)
                # Evaluate on both public and private
                final_ev = evaluate(code, problem, use_private=True)
                r = {
                    "problem_id": pid, "tier": tier, "strategy": strat_name,
                    "pass_public": final_ev["pass_public"],
                    "pass_private": final_ev.get("pass_private"),
                    "public_passed": sum(1 for x in final_ev["public_results"] if x["passed"]),
                    "public_total": len(final_ev["public_results"]),
                    "private_passed": sum(1 for x in final_ev["private_results"] if x["passed"]) if final_ev["private_results"] else 0,
                    "private_total": len(final_ev["private_results"]) if final_ev["private_results"] else 0,
                }
                result_file.write_text(json.dumps(r, indent=2))
                all_results.append(r)
                pub = "PASS" if r["pass_public"] else "FAIL"
                priv = "PASS" if r.get("pass_private") else "FAIL"
                print(f"  {strat_name:<25} pub={pub} priv={priv}")
            except Exception as e:
                print(f"  {strat_name:<25} ERROR: {e}")
                r = {"problem_id": pid, "tier": tier, "strategy": strat_name, "error": str(e)}
                all_results.append(r)

    # Summary
    print(f"\n\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")

    for strat_name in strategies:
        strat_results = [r for r in all_results if r.get("strategy") == strat_name and "error" not in r]
        if not strat_results:
            continue
        pub_pass = sum(1 for r in strat_results if r.get("pass_public"))
        priv_pass = sum(1 for r in strat_results if r.get("pass_private"))
        n = len(strat_results)
        print(f"\n  {strat_name}:")
        print(f"    Public:  {pub_pass}/{n} ({pub_pass/n*100:.0f}%)")
        print(f"    Private: {priv_pass}/{n} ({priv_pass/n*100:.0f}%)")
        for tier in ["easy", "medium", "hard"]:
            tr = [r for r in strat_results if r.get("tier") == tier]
            if tr:
                tp = sum(1 for r in tr if r.get("pass_public"))
                tpr = sum(1 for r in tr if r.get("pass_private"))
                print(f"      {tier}: pub={tp}/{len(tr)} priv={tpr}/{len(tr)}")

    (base_dir / "all_results.json").write_text(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
