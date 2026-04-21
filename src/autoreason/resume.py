"""Resume an interrupted run by rehydrating state from the run directory."""

from __future__ import annotations

import json
from pathlib import Path

from autoreason.artifacts import (
    HISTORY_FILE,
    RunState,
    pid_is_alive,
    read_config_snapshot,
    read_prompt,
    read_prompts_snapshot,
    read_state,
)
from autoreason.config import Config
from autoreason.prompts import Prompts

# Statuses from which we can meaningfully re-enter the loop.
RESUMABLE_STATUSES = {"running", "interrupted", "error", "stopped", "initializing"}
TERMINAL_STATUSES = {"converged", "max_passes_reached", "accepted", "dry_run"}


def load_resume_context(run_dir: Path) -> tuple[Config, Prompts, str, RunState]:
    """Read everything needed to re-enter the loop for a previously-started run."""
    state = read_state(run_dir)
    config = read_config_snapshot(run_dir)
    prompts = read_prompts_snapshot(run_dir)
    prompt_text = read_prompt(run_dir)
    return config, prompts, prompt_text, state


def is_resumable(state: RunState) -> tuple[bool, str]:
    """Return (ok, reason). ok=False means do not resume."""
    if state.status in TERMINAL_STATUSES:
        return False, f"run is terminal ({state.status})"
    if state.status == "running" and pid_is_alive(state.pid):
        return False, f"run appears active (pid {state.pid}); use `attach` or `signal stop` first"
    return True, "resumable"


def cached_cost_total(run_dir: Path) -> float:
    """Sum `cost_usd` across all history entries, defaulting to 0 if history is missing."""
    history_path = run_dir / HISTORY_FILE
    if not history_path.exists():
        return 0.0
    try:
        entries = json.loads(history_path.read_text())
    except (json.JSONDecodeError, ValueError):
        return 0.0
    return float(sum(e.get("cost_usd") or 0.0 for e in entries if isinstance(e, dict)))
