"""Main AutoReason loop: generate initial A, iterate, converge."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autoreason.artifacts import PHASE_IDLE, PHASE_INITIAL, EventSink, LoopMonitor
from autoreason.config import Config
from autoreason.llm import BudgetExhaustedHandler, CostTracker, call_llm
from autoreason.pass_ import run_pass
from autoreason.prompts import Prompts

# Callback signatures:
#   on_pass_complete(result_dict, incumbent_text) -> bool
#     Return False to request graceful stop after this pass.
#   injections_getter() -> str
#     Return text to append to the next critic prompt, or "" for none.
OnPassComplete = Callable[[dict[str, Any], str], bool]
InjectionsGetter = Callable[[], str]


@dataclass
class RunResult:
    """Final outcome of a loop invocation."""

    status: str  # "converged" | "max_passes_reached" | "stopped" | "dry_run"
    final_text: str
    history: list[dict[str, Any]] = field(default_factory=list)
    num_passes: int = 0
    elapsed_seconds: float = 0.0
    cost_usd: float = 0.0


async def run_autoreason_loop(
    task_prompt: str,
    task_dir: Path,
    config: Config,
    prompts: Prompts | None = None,
    *,
    cost_tracker: CostTracker | None = None,
    dry_run: bool = False,
    on_pass_complete: OnPassComplete | None = None,
    injections_getter: InjectionsGetter | None = None,
    monitor: LoopMonitor | None = None,
    events: EventSink | None = None,
    on_budget_exhausted: BudgetExhaustedHandler | None = None,
) -> RunResult:
    """Run passes until convergence, max_passes, or a requested stop.

    Artifacts written into `task_dir`:
        initial_a.md, pass_NN/ (via run_pass), incumbent_after_NN.md (on change),
        history.json, final_output.md.
    """
    prompts = prompts or Prompts.load_defaults()
    task_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.monotonic()

    if events is not None:
        events.emit("run_started", task_dir=str(task_dir), dry_run=dry_run)

    if monitor is not None:
        monitor.set_phase(0, PHASE_INITIAL)
    current_a = await _generate_or_reuse_initial(
        task_prompt,
        task_dir,
        config,
        prompts,
        cost_tracker=cost_tracker,
        dry_run=dry_run,
        on_budget_exhausted=on_budget_exhausted,
    )
    if events is not None and not dry_run:
        events.emit("initial_a_ready", words=len(current_a.split()))

    history: list[dict[str, Any]] = []
    streak = 0
    status = "max_passes_reached"

    for pass_num in range(1, config.max_passes + 1):
        injection = injections_getter() if injections_getter else ""
        pass_dir = task_dir / f"pass_{pass_num:02d}"

        if monitor is not None:
            monitor.pass_num = pass_num
            monitor.streak = streak

        winner, winner_text, result = await run_pass(
            task_prompt,
            current_a,
            pass_num,
            pass_dir,
            config,
            prompts,
            injection=injection,
            cost_tracker=cost_tracker,
            monitor=monitor,
            events=events,
            dry_run=dry_run,
            on_budget_exhausted=on_budget_exhausted,
        )

        if dry_run:
            history.append({"pass": pass_num, "winner": "DRY"})
            continue

        entry = {
            "pass": pass_num,
            "winner": winner,
            "scores": result.get("scores", {}),
            "words": result.get("winner_words"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "cost_usd": result.get("cost_usd"),
        }
        history.append(entry)
        _write_history(task_dir, history)

        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (task_dir / f"incumbent_after_{pass_num:02d}.md").write_text(current_a)
            if events is not None:
                events.emit(
                    "incumbent_changed",
                    pass_num=pass_num,
                    new_incumbent=winner,
                    words=len(current_a.split()),
                )

        if monitor is not None:
            monitor.streak = streak
            monitor.num_passes = len(history)

        continue_loop = True
        if on_pass_complete is not None:
            try:
                continue_loop = bool(on_pass_complete(result, current_a))
            except Exception:  # noqa: BLE001 — hooks must never take down the loop
                continue_loop = True

        if not continue_loop:
            status = "stopped"
            if events is not None:
                events.emit("stopped", pass_num=pass_num, reason="pass_complete_hook")
            break

        if streak >= config.convergence_threshold:
            status = "converged"
            if events is not None:
                events.emit("converged", pass_num=pass_num, streak=streak)
            break

    if monitor is not None:
        monitor.set_phase(monitor.pass_num, PHASE_IDLE)

    if dry_run:
        status = "dry_run"
        final_text = current_a
    else:
        final_text = current_a
        (task_dir / "final_output.md").write_text(final_text)
        _write_history(task_dir, history)
        if status == "max_passes_reached" and events is not None:
            events.emit("max_passes_reached", num_passes=len(history))

    return RunResult(
        status=status,
        final_text=final_text,
        history=history,
        num_passes=len(history),
        elapsed_seconds=round(time.monotonic() - t_start, 2),
        cost_usd=round(cost_tracker.total_usd, 6) if cost_tracker else 0.0,
    )


async def _generate_or_reuse_initial(
    task_prompt: str,
    task_dir: Path,
    config: Config,
    prompts: Prompts,
    *,
    cost_tracker: CostTracker | None,
    dry_run: bool,
    on_budget_exhausted: BudgetExhaustedHandler | None = None,
) -> str:
    """Read initial_a.md if present, else ask author_a to produce it."""
    init_file = task_dir / "initial_a.md"
    if init_file.exists():
        return init_file.read_text()
    if dry_run:
        return "[DRY RUN — initial_a placeholder]"
    system, user = prompts.render("author_a", task_prompt=task_prompt)
    text = await call_llm(
        system,
        user,
        config.model_for_role("author_a"),
        config.author_temperature,
        config.max_tokens,
        max_retries=config.max_retries,
        cost_tracker=cost_tracker,
        on_budget_exhausted=on_budget_exhausted,
    )
    init_file.write_text(text)
    return text


def _write_history(task_dir: Path, history: list[dict[str, Any]]) -> None:
    (task_dir / "history.json").write_text(json.dumps(history, indent=2, ensure_ascii=False))
