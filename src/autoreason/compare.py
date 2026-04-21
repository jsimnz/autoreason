"""Run enumeration and side-by-side comparison across runs/<id>/ directories."""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from autoreason.aggregate import parse_ranking
from autoreason.artifacts import (
    FINAL_FILE,
    HISTORY_FILE,
    INITIAL_FILE,
    PROMPT_FILE,
    read_config_snapshot,
    read_state,
)
from autoreason.config import Config
from autoreason.llm import CostTracker, call_llm


@dataclass
class RunSummary:
    """Minimal stats for a run dir (for list/compare output)."""

    run_dir: Path
    status: str
    num_passes: int
    cost_usd: float
    trajectory: str
    final_words: int
    converged: bool
    prompt_head: str
    author_model: str


def summarize_run(run_dir: Path) -> RunSummary | None:
    """Return a RunSummary for a single run dir, or None if not a valid run."""
    try:
        state_path = run_dir / "state.json"
        if not state_path.exists():
            return None
    except (PermissionError, OSError):
        return None
    try:
        state = read_state(run_dir)
    except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError, ValueError):
        return None
    trajectory = _trajectory_string(run_dir)
    final_words = _word_count(run_dir / FINAL_FILE) or _word_count(run_dir / INITIAL_FILE) or 0
    prompt_head = _first_line(run_dir / PROMPT_FILE, max_len=80)
    return RunSummary(
        run_dir=run_dir,
        status=state.status,
        num_passes=state.num_passes,
        cost_usd=state.cost_usd,
        trajectory=trajectory,
        final_words=final_words,
        converged=state.status == "converged",
        prompt_head=prompt_head,
        author_model=state.author_model,
    )


def list_run_summaries(root: Path) -> list[RunSummary]:
    """Enumerate all immediate subdirectories of `root` that look like runs."""
    if not root.exists():
        return []
    out: list[RunSummary] = []
    try:
        children = sorted(root.iterdir())
    except (PermissionError, OSError):
        return []
    for child in children:
        try:
            if not child.is_dir():
                continue
        except (PermissionError, OSError):
            continue
        summary = summarize_run(child)
        if summary is not None:
            out.append(summary)
    return out


def render_list_table(summaries: list[RunSummary]) -> Table:
    """Render a list of runs as a rich Table."""
    table = Table(title="AutoReason runs", header_style="bold cyan", show_lines=False)
    table.add_column("Run", style="cyan", overflow="fold")
    table.add_column("Status")
    table.add_column("Passes", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Words", justify="right")
    table.add_column("Trajectory", overflow="fold")
    table.add_column("Prompt", overflow="fold")
    for s in summaries:
        status_style = {
            "converged": "green",
            "accepted": "green",
            "max_passes_reached": "yellow",
            "error": "red",
            "interrupted": "yellow",
            "running": "blue",
        }.get(s.status, "dim")
        table.add_row(
            str(s.run_dir.name),
            f"[{status_style}]{s.status}[/]",
            str(s.num_passes),
            f"${s.cost_usd:.4f}",
            str(s.final_words),
            s.trajectory or "—",
            s.prompt_head,
        )
    return table


def render_compare_table(summaries: list[RunSummary]) -> Table:
    """Render a side-by-side comparison of runs."""
    table = Table(title="AutoReason — compare", header_style="bold cyan")
    table.add_column("Run")
    table.add_column("Status")
    table.add_column("Passes", justify="right")
    table.add_column("Converged")
    table.add_column("Cost", justify="right")
    table.add_column("Words", justify="right")
    table.add_column("Trajectory")
    for s in summaries:
        table.add_row(
            str(s.run_dir.name),
            s.status,
            str(s.num_passes),
            "yes" if s.converged else "no",
            f"${s.cost_usd:.4f}",
            str(s.final_words),
            s.trajectory,
        )
    return table


# ── LLM-based head-to-head judge for compare --judge ───────────────────────


async def judge_runs(
    run_dirs: list[Path],
    *,
    num_judges: int = 3,
    model: str | None = None,
) -> dict:
    """Spawn a judge panel to rank each run's final_output against the common prompt.

    Supports 2 or 3 runs. Returns a dict with rankings + scores.
    """
    if not 2 <= len(run_dirs) <= 3:
        raise ValueError("compare --judge supports exactly 2 or 3 runs")

    prompt_text = (run_dirs[0] / PROMPT_FILE).read_text().strip()
    finals: list[tuple[str, str]] = []  # (label, text)
    for i, d in enumerate(run_dirs):
        label = chr(ord("X") + i)  # X, Y, [Z]
        final = (d / FINAL_FILE)
        if not final.exists():
            raise FileNotFoundError(f"{d} has no final_output.md; cannot compare")
        finals.append((label, final.read_text()))

    cfg: Config = read_config_snapshot(run_dirs[0])
    judge_model = model or cfg.judge_model or cfg.author_model
    cost = CostTracker()

    # Use the existing judge pattern: shuffle per judge, parse RANKING, Borda aggregate.
    scores: dict[str, int] = {label: 0 for label, _ in finals}
    raw_rankings: list[list[str]] = []

    for j in range(num_judges):
        shuffled = list(finals)
        random.shuffle(shuffled)
        order_map: dict[str, str] = {}
        parts: list[str] = []
        for i, (label, text) in enumerate(shuffled, start=1):
            order_map[str(i)] = label
            parts.append(f"PROPOSAL {i}:\n---\n{text}\n---")
        proposals_text = "\n\n".join(parts)

        rank_instruction = _rank_instruction(len(finals))

        user = (
            f"ORIGINAL TASK:\n---\n{prompt_text}\n---\n\n"
            f"{len(finals)} proposals were produced independently to accomplish this task. "
            "Evaluate how well each one accomplishes what the task asks for.\n\n"
            f"{proposals_text}\n\n"
            "For each proposal, state specifically:\n"
            "1. Which aspects of the original task it handles well\n"
            "2. Which aspects it handles poorly or misses\n"
            "3. Any issues with feasibility or coherence\n\n"
            f"Then rank them from best to worst. Respond with your ranking in this exact format at the end:\n\n"
            f"{rank_instruction}\n"
        )
        system = (
            "You are an independent evaluator. You have no authorship stake in any version. "
            "Your job is to determine which version best accomplishes the original task as described."
        )
        response = await call_llm(
            system, user,
            judge_model, cfg.judge_temperature, cfg.max_tokens,
            max_retries=cfg.max_retries, cost_tracker=cost,
        )
        ranking = parse_ranking(response, order_map)
        if ranking is None:
            continue
        raw_rankings.append(ranking)
        n = len(finals)
        for pos, label in enumerate(ranking):
            if label in scores and pos < n:
                scores[label] += (n - pos)

    # Map labels back to run dirs
    label_to_dir = {chr(ord("X") + i): d for i, d in enumerate(run_dirs)}
    ranked_labels = sorted(scores.keys(), key=lambda k: -scores[k])
    return {
        "num_judges": num_judges,
        "model": judge_model,
        "rankings": raw_rankings,
        "scores": scores,
        "winner_dir": str(label_to_dir[ranked_labels[0]]),
        "ordered": [{"label": l, "dir": str(label_to_dir[l]), "score": scores[l]} for l in ranked_labels],
        "cost_usd": round(cost.total_usd, 6),
    }


def _rank_instruction(n: int) -> str:
    if n == 2:
        return "RANKING: [better], [worse]"
    return "RANKING: [best], [second], [worst]"


# ── helpers ────────────────────────────────────────────────────────────────


def _trajectory_string(run_dir: Path) -> str:
    history = run_dir / HISTORY_FILE
    if not history.exists():
        return ""
    try:
        entries = json.loads(history.read_text())
    except (json.JSONDecodeError, ValueError, OSError):
        return ""
    return " → ".join(str(e.get("winner", "?")) for e in entries)


def _word_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(path.read_text().split())
    except OSError:
        return 0


def _first_line(path: Path, max_len: int = 80) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text().strip()
    except OSError:
        return ""
    line = text.splitlines()[0] if text else ""
    return line if len(line) <= max_len else line[: max_len - 1] + "…"


def run_judge_sync(run_dirs: list[Path], num_judges: int = 3, model: str | None = None) -> dict:
    """Synchronous wrapper around judge_runs for CLI use."""
    return asyncio.run(judge_runs(run_dirs, num_judges=num_judges, model=model))
