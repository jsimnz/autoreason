"""Run-directory layout, state.json, heartbeat, events."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autoreason.config import Config
from autoreason.llm import CostTracker
from autoreason.prompts import Prompts

# Filenames under runs/<run-id>/
CONFIG_FILE = "config.yaml"
PROMPTS_FILE = "prompts.yaml"
PROMPT_FILE = "prompt.md"
STATE_FILE = "state.json"
HEARTBEAT_FILE = "heartbeat.json"
COMMANDS_FILE = "commands.jsonl"
EVENTS_FILE = "events.jsonl"
INJECTIONS_FILE = "injections.jsonl"
HISTORY_FILE = "history.json"
FINAL_FILE = "final_output.md"
INITIAL_FILE = "initial_a.md"

# Phase name constants (used by monitor + UI)
PHASE_IDLE = "idle"
PHASE_INITIAL = "initial"
PHASE_CRITIC = "critic"
PHASE_AUTHOR_B = "author_b"
PHASE_SYNTH = "synthesizer"
PHASE_JUDGES = "judges"
PHASES_IN_PASS = (PHASE_CRITIC, PHASE_AUTHOR_B, PHASE_SYNTH, PHASE_JUDGES)


@dataclass
class RunState:
    """Persistent per-run state (written to state.json)."""

    status: str = "initializing"  # initializing|running|converged|max_passes_reached|stopped|error|dry_run|interrupted|accepted
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    last_heartbeat: str | None = None
    author_model: str = ""
    judge_model: str = ""
    current_pass: int = 0
    num_passes: int = 0
    streak: int = 0
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    num_calls: int = 0
    cost_tracked: bool = False
    pid: int | None = None
    commands_cursor: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


# ── live loop monitor (in-memory, shared) ──────────────────────────────────


@dataclass
class LoopMonitor:
    """Thread-safe snapshot of what the loop is doing right now.

    pass_.py and loop.py call `.set_phase()` as they progress; a background
    task reads `.snapshot()` to write the heartbeat file.
    """

    run_dir: Path
    pass_num: int = 0
    phase: str = PHASE_IDLE
    phase_started_at: float = field(default_factory=time.monotonic)
    streak: int = 0
    num_passes: int = 0
    cost_tracker: CostTracker | None = None

    def set_phase(self, pass_num: int, phase: str) -> None:
        self.pass_num = pass_num
        self.phase = phase
        self.phase_started_at = time.monotonic()

    def snapshot(self) -> dict[str, Any]:
        tracker = self.cost_tracker
        return {
            "pass": self.pass_num,
            "phase": self.phase,
            "elapsed_in_phase_s": round(time.monotonic() - self.phase_started_at, 1),
            "streak": self.streak,
            "num_passes": self.num_passes,
            "total_cost_usd": round(tracker.total_usd, 6) if tracker else 0.0,
            "prompt_tokens": tracker.total_prompt_tokens if tracker else 0,
            "completion_tokens": tracker.total_completion_tokens if tracker else 0,
            "num_calls": tracker.num_calls if tracker else 0,
            "cost_tracked": bool(tracker.track_cost) if tracker else False,
            "pid": os.getpid(),
            "ts": _now_iso(),
        }

    def write_heartbeat(self) -> None:
        atomic_write(self.run_dir / HEARTBEAT_FILE, json.dumps(self.snapshot()))


async def heartbeat_task(monitor: LoopMonitor, interval: float = 5.0) -> None:
    """Background coroutine: write heartbeat.json every `interval` seconds."""
    while True:
        try:
            monitor.write_heartbeat()
        except OSError:
            pass  # disk full / permission flake — don't take down the run
        await asyncio.sleep(interval)


# ── events.jsonl append-only log ───────────────────────────────────────────


class EventSink:
    """Append-only JSONL event log."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def emit(self, event_type: str, **fields: Any) -> None:
        entry: dict[str, Any] = {"ts": _now_iso(), "type": event_type, **fields}
        with self.path.open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── dir + slug + file helpers ──────────────────────────────────────────────


_SLUG_BAD = re.compile(r"[^a-z0-9]+")


def make_slug(text: str, max_len: int = 40) -> str:
    slug = _SLUG_BAD.sub("-", text.lower()).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "run"


def make_run_dir(root: Path, prompt: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    first_line = prompt.strip().splitlines()[0] if prompt.strip() else "run"
    run_dir = root / f"{ts}-{make_slug(first_line)}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_prompt(run_dir: Path, prompt: str) -> None:
    (run_dir / PROMPT_FILE).write_text(prompt)


def read_prompt(run_dir: Path) -> str:
    return (run_dir / PROMPT_FILE).read_text()


def write_config_snapshot(run_dir: Path, config: Config) -> None:
    (run_dir / CONFIG_FILE).write_text(config.to_yaml())


def read_config_snapshot(run_dir: Path) -> Config:
    return Config.load(config_path=run_dir / CONFIG_FILE)


def write_prompts_snapshot(run_dir: Path, prompts: Prompts) -> None:
    (run_dir / PROMPTS_FILE).write_text(prompts.to_yaml())


def read_prompts_snapshot(run_dir: Path) -> Prompts:
    return Prompts.load(override_path=run_dir / PROMPTS_FILE)


def atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` via temp file + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)


def write_state(run_dir: Path, state: RunState) -> None:
    atomic_write(run_dir / STATE_FILE, json.dumps(state.to_dict(), indent=2, ensure_ascii=False))


def read_state(run_dir: Path) -> RunState:
    raw = json.loads((run_dir / STATE_FILE).read_text())
    return RunState.from_dict(raw)


def pid_is_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
