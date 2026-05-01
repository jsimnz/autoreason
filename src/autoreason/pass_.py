"""One refinement pass: critic → author_b → synthesizer → judge panel.

Emits artifact files into `pass_dir`:
    version_a.md, critic.md, version_b.md, version_ab.md,
    judge_01.md ... judge_NN.md, result.json

`result.json` existence is the resume sentinel — on re-entry we skip the pass
and return the previously decided winner.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from pathlib import Path
from typing import Any

from autoreason.aggregate import aggregate_rankings, parse_ranking, randomize_for_judge
from autoreason.artifacts import (
    PHASE_AUTHOR_B,
    PHASE_CRITIC,
    PHASE_JUDGES,
    PHASE_SYNTH,
    EventSink,
    LoopMonitor,
)
from autoreason.config import Config
from autoreason.llm import BudgetExhaustedHandler, CostTracker, call_llm
from autoreason.prompts import Prompts

PassResult = dict[str, Any]


async def run_pass(
    task_prompt: str,
    current_a: str,
    pass_num: int,
    pass_dir: Path,
    config: Config,
    prompts: Prompts,
    *,
    injection: str = "",
    cost_tracker: CostTracker | None = None,
    monitor: LoopMonitor | None = None,
    events: EventSink | None = None,
    dry_run: bool = False,
    on_budget_exhausted: BudgetExhaustedHandler | None = None,
) -> tuple[str, str, PassResult]:
    """Run one pass. Returns (winner_label, winner_text, result_dict)."""
    pass_dir.mkdir(parents=True, exist_ok=True)
    streams_dir = pass_dir / "streams"
    streams_dir.mkdir(parents=True, exist_ok=True)

    resumed = _try_resume(pass_dir, current_a)
    if resumed is not None:
        if events is not None:
            events.emit(
                "pass_resumed_cached",
                pass_num=pass_num,
                winner=resumed[2].get("winner"),
            )
        return resumed

    if dry_run:
        stub = {
            "pass": pass_num,
            "winner": "DRY",
            "scores": {},
            "num_judges": config.num_judges,
            "dry_run": True,
        }
        return "DRY", current_a, stub

    t0 = time.monotonic()
    cost_before = cost_tracker.total_usd if cost_tracker else 0.0

    if events is not None:
        events.emit("pass_started", pass_num=pass_num, injection=bool(injection))

    (pass_dir / "version_a.md").write_text(current_a)

    # ── Step 1: critic ──
    if monitor is not None:
        monitor.set_phase(pass_num, PHASE_CRITIC)
    phase_t0 = time.monotonic()
    critic_system, critic_user = prompts.render(
        "critic", version_a=current_a, task_prompt=task_prompt, injection=injection
    )
    critic_model = config.model_for_role("critic")
    critic_text = await call_llm(
        critic_system,
        critic_user,
        critic_model,
        config.author_temperature,
        config.max_tokens,
        max_retries=config.max_retries,
        cost_tracker=cost_tracker,
        on_budget_exhausted=on_budget_exhausted,
        stream_path=streams_dir / "critic.md",
    )
    (pass_dir / "critic.md").write_text(critic_text)
    _emit_phase_complete(events, pass_num, PHASE_CRITIC, phase_t0)

    # ── Step 2: author_b (adversarial revision) ──
    if monitor is not None:
        monitor.set_phase(pass_num, PHASE_AUTHOR_B)
    phase_t0 = time.monotonic()
    b_system, b_user = prompts.render(
        "author_b", task_prompt=task_prompt, version_a=current_a, critic=critic_text
    )
    author_b_model = config.model_for_role("author_b")
    version_b = await call_llm(
        b_system,
        b_user,
        author_b_model,
        config.author_temperature,
        config.max_tokens,
        max_retries=config.max_retries,
        cost_tracker=cost_tracker,
        on_budget_exhausted=on_budget_exhausted,
        stream_path=streams_dir / "author_b.md",
    )
    (pass_dir / "version_b.md").write_text(version_b)
    _emit_phase_complete(events, pass_num, PHASE_AUTHOR_B, phase_t0)

    # ── Step 3: synthesizer (with randomized X/Y order) ──
    if monitor is not None:
        monitor.set_phase(pass_num, PHASE_SYNTH)
    phase_t0 = time.monotonic()
    if random.random() < 0.5:
        vx, vy = current_a, version_b
    else:
        vx, vy = version_b, current_a
    s_system, s_user = prompts.render(
        "synthesizer", task_prompt=task_prompt, version_x=vx, version_y=vy
    )
    synthesizer_model = config.model_for_role("synthesizer")
    version_ab = await call_llm(
        s_system,
        s_user,
        synthesizer_model,
        config.author_temperature,
        config.max_tokens,
        max_retries=config.max_retries,
        cost_tracker=cost_tracker,
        on_budget_exhausted=on_budget_exhausted,
        stream_path=streams_dir / "synthesizer.md",
    )
    (pass_dir / "version_ab.md").write_text(version_ab)
    _emit_phase_complete(events, pass_num, PHASE_SYNTH, phase_t0)

    # ── Step 4: judge panel (parallel) ──
    if monitor is not None:
        monitor.set_phase(pass_num, PHASE_JUDGES)
    phase_t0 = time.monotonic()
    judge_orders: list[dict[str, str]] = []
    judge_models_used: list[str] = []
    judge_coros = []
    for i in range(config.num_judges):
        proposals, order_map = randomize_for_judge(current_a, version_b, version_ab)
        judge_orders.append(order_map)
        j_system, j_user = prompts.render(
            "judge", task_prompt=task_prompt, judge_proposals=proposals
        )
        judge_model_i = config.model_for_judge(i)
        judge_models_used.append(judge_model_i)
        judge_coros.append(
            call_llm(
                j_system,
                j_user,
                judge_model_i,
                config.judge_temperature,
                config.max_tokens,
                max_retries=config.max_retries,
                cost_tracker=cost_tracker,
                on_budget_exhausted=on_budget_exhausted,
                stream_path=streams_dir / f"judge_{i + 1:02d}.md",
            )
        )

    judge_responses = await asyncio.gather(*judge_coros, return_exceptions=True)

    rankings: list[list[str] | None] = []
    judge_details: list[dict[str, Any]] = []
    for j, (response, order_map, jmodel) in enumerate(
        zip(judge_responses, judge_orders, judge_models_used), start=1
    ):
        if isinstance(response, BaseException):
            rankings.append(None)
            judge_details.append(
                {"judge": j, "model": jmodel, "error": str(response), "presentation_order": order_map}
            )
            (pass_dir / f"judge_{j:02d}.md").write_text(f"ERROR: {response}")
        else:
            ranking = parse_ranking(response, order_map)
            rankings.append(ranking)
            judge_details.append(
                {"judge": j, "model": jmodel, "ranking": ranking, "presentation_order": order_map}
            )
            (pass_dir / f"judge_{j:02d}.md").write_text(response)
    _emit_phase_complete(events, pass_num, PHASE_JUDGES, phase_t0, num_judges=config.num_judges)

    winner, scores, valid = aggregate_rankings(rankings)
    version_map = {"A": current_a, "B": version_b, "AB": version_ab}
    winner_text = version_map[winner]

    pass_cost = (cost_tracker.total_usd - cost_before) if cost_tracker else 0.0
    elapsed = round(time.monotonic() - t0, 2)

    result: PassResult = {
        "pass": pass_num,
        "winner": winner,
        "scores": scores,
        "num_judges": config.num_judges,
        "num_valid": len(valid),
        "individual_rankings": [r for r in rankings if r is not None],
        "judge_details": judge_details,
        "elapsed_seconds": elapsed,
        "author_model": config.author_model,
        "critic_model": critic_model,
        "author_b_model": author_b_model,
        "synthesizer_model": synthesizer_model,
        "judge_model": config.judge_model or config.author_model,
        "judge_models": judge_models_used,
        "cost_usd": round(pass_cost, 6),
        "winner_words": len(winner_text.split()),
    }
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    if events is not None:
        events.emit(
            "pass_complete",
            pass_num=pass_num,
            winner=winner,
            scores=scores,
            elapsed_seconds=elapsed,
            cost_usd=round(pass_cost, 6),
            winner_words=len(winner_text.split()),
        )

    return winner, winner_text, result


def _emit_phase_complete(
    events: EventSink | None,
    pass_num: int,
    phase: str,
    t0: float,
    **extra: Any,
) -> None:
    if events is None:
        return
    events.emit(
        "phase_complete",
        pass_num=pass_num,
        phase=phase,
        elapsed_seconds=round(time.monotonic() - t0, 2),
        **extra,
    )


def _try_resume(pass_dir: Path, current_a: str) -> tuple[str, str, PassResult] | None:
    """If this pass already has a result.json, reconstruct the return tuple."""
    result_file = pass_dir / "result.json"
    if not result_file.exists():
        return None
    try:
        existing = json.loads(result_file.read_text())
    except json.JSONDecodeError:
        return None
    winner = existing.get("winner")
    if not winner:
        return None
    if winner == "A":
        return winner, current_a, existing
    winner_file = pass_dir / f"version_{winner.lower()}.md"
    if winner_file.exists():
        return winner, winner_file.read_text(), existing
    return None
