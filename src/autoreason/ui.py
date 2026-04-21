"""Rich-based streaming UI for a running loop.

Renders a single Live panel that updates as the loop progresses. Falls back to
`None` (caller shows only a summary at end) when stdout is not a TTY, or when
the user passed --quiet or --no-color.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from autoreason.artifacts import (
    EVENTS_FILE,
    HEARTBEAT_FILE,
    HISTORY_FILE,
    PHASE_IDLE,
    PHASE_INITIAL,
    PHASES_IN_PASS,
    LoopMonitor,
    read_state,
)

_PHASE_ORDER = (PHASE_INITIAL,) + PHASES_IN_PASS  # initial, critic, author_b, synth, judges


def ui_enabled(quiet: bool, no_color: bool) -> bool:
    """Whether to render the rich Live UI."""
    if quiet or no_color:
        return False
    return sys.stdout.isatty()


async def ui_task(
    monitor: LoopMonitor,
    run_dir: Path,
    prompt_preview: str,
    config_summary: str,
    interval: float = 0.3,
) -> None:
    """Background coroutine that redraws the UI until cancelled."""
    console = Console()
    with Live(
        _render(monitor, run_dir, prompt_preview, config_summary),
        console=console,
        refresh_per_second=10,
        transient=False,
    ) as live:
        try:
            while True:
                live.update(_render(monitor, run_dir, prompt_preview, config_summary))
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            live.update(_render(monitor, run_dir, prompt_preview, config_summary))
            raise


def _render(
    monitor: LoopMonitor, run_dir: Path, prompt_preview: str, config_summary: str
) -> Panel:
    header = Text.from_markup(
        f"[bold]prompt[/]: [italic cyan]{_truncate(prompt_preview, 80)}[/]\n"
        f"[dim]{config_summary}[/]\n"
        f"[dim]output: {run_dir}[/]"
    )
    body = Group(
        header,
        Text(""),
        _phase_row(monitor.phase),
        Text(""),
        _trajectory(run_dir, monitor),
        Text(""),
        _stats(monitor),
        Text(""),
        _events_tail(run_dir),
    )
    return Panel(body, title="[bold cyan]AutoReason[/]", border_style="cyan")


def _phase_row(current_phase: str) -> Text:
    current_idx = _PHASE_ORDER.index(current_phase) if current_phase in _PHASE_ORDER else -1
    parts: list[str] = []
    for i, ph in enumerate(_PHASE_ORDER):
        if current_phase == PHASE_IDLE:
            marker, style = "·", "dim"
        elif i < current_idx:
            marker, style = "✓", "green"
        elif i == current_idx:
            marker, style = "▶", "bold yellow"
        else:
            marker, style = " ", "dim"
        parts.append(f"[{style}]\\[{marker} {ph}][/]")
    return Text.from_markup("  ".join(parts))


def _trajectory(run_dir: Path, monitor: LoopMonitor) -> Text:
    history_path = run_dir / HISTORY_FILE
    if not history_path.exists():
        return Text.from_markup("[dim]trajectory: (no passes yet)[/]")
    try:
        entries = json.loads(history_path.read_text())
    except (json.JSONDecodeError, ValueError, OSError):
        return Text.from_markup("[dim]trajectory: —[/]")
    if not entries:
        return Text.from_markup("[dim]trajectory: (no passes yet)[/]")

    pieces = []
    for e in entries:
        w = str(e.get("winner", "?"))
        color = "green" if w == "A" else ("magenta" if w == "AB" else "yellow")
        pieces.append(f"[{color}]{w}[/]")
    streak_hint = f"   [dim](streak {monitor.streak})[/]" if monitor.streak else ""
    return Text.from_markup("trajectory: " + " → ".join(pieces) + streak_hint)


def _stats(monitor: LoopMonitor) -> Text:
    snap = monitor.snapshot()
    return Text.from_markup(
        f"pass [bold]{snap['pass']}[/]    "
        f"phase elapsed [bold]{snap['elapsed_in_phase_s']:.1f}s[/]    "
        f"cost [bold]${snap['total_cost_usd']:.4f}[/]    "
        f"calls [bold]{snap['num_calls']}[/]"
    )


def _events_tail(run_dir: Path, n: int = 3) -> Text:
    events_path = run_dir / EVENTS_FILE
    if not events_path.exists():
        return Text("")
    try:
        lines = events_path.read_text().splitlines()[-n:]
    except OSError:
        return Text("")
    rendered: list[str] = []
    for line in lines:
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = str(d.get("ts", ""))[11:19]
        t = str(d.get("type", ""))
        extras = []
        for k in ("pass_num", "phase", "winner", "elapsed_seconds"):
            if k in d:
                extras.append(f"{k}={d[k]}")
        tail = "  ".join(extras)
        rendered.append(f"[dim]{ts}[/] [cyan]{t}[/]  [dim]{tail}[/]")
    return Text.from_markup("\n".join(rendered) or "")


def _truncate(s: str, n: int) -> str:
    s = s.strip().splitlines()[0] if s.strip() else s
    return s if len(s) <= n else s[: n - 1] + "…"


# ── attach (read-only from another terminal) ───────────────────────────────


async def attach_loop(
    run_dir: Path,
    prompt_preview: str,
    config_summary: str,
    interval: float = 1.0,
) -> str:
    """Watch a running run until it reaches a terminal state. Returns final status."""
    console = Console()
    with Live(
        _render_from_files(run_dir, prompt_preview, config_summary),
        console=console,
        refresh_per_second=4,
        transient=False,
    ) as live:
        while True:
            live.update(_render_from_files(run_dir, prompt_preview, config_summary))
            final = _terminal_status(run_dir)
            if final is not None:
                live.update(_render_from_files(run_dir, prompt_preview, config_summary))
                return final
            await asyncio.sleep(interval)


def _render_from_files(run_dir: Path, prompt_preview: str, config_summary: str) -> Panel:
    """Read heartbeat + state + history from disk and render a Panel (no monitor)."""
    hb = _read_heartbeat(run_dir)
    current_phase = hb.get("phase", PHASE_IDLE) if hb else PHASE_IDLE
    pass_num = hb.get("pass", 0) if hb else 0
    elapsed = hb.get("elapsed_in_phase_s", 0.0) if hb else 0.0
    cost = hb.get("total_cost_usd", 0.0) if hb else 0.0
    calls = hb.get("num_calls", 0) if hb else 0
    streak = hb.get("streak", 0) if hb else 0

    try:
        state = read_state(run_dir)
        status_line = f"status: [bold]{state.status}[/]"
    except FileNotFoundError:
        status_line = "[dim]status: unknown[/]"

    header = Text.from_markup(
        f"[bold]prompt[/]: [italic cyan]{_truncate(prompt_preview, 80)}[/]\n"
        f"[dim]{config_summary}[/]\n"
        f"[dim]dir: {run_dir}[/]  {status_line}"
    )

    # fake monitor-like namespace for trajectory helper
    class _M:
        pass

    m = _M()
    m.streak = streak  # type: ignore[attr-defined]

    stats_text = Text.from_markup(
        f"pass [bold]{pass_num}[/]    phase elapsed [bold]{elapsed:.1f}s[/]    "
        f"cost [bold]${cost:.4f}[/]    calls [bold]{calls}[/]"
    )

    body = Group(
        header,
        Text(""),
        _phase_row(current_phase),
        Text(""),
        _trajectory(run_dir, m),  # type: ignore[arg-type]
        Text(""),
        stats_text,
        Text(""),
        _events_tail(run_dir, n=5),
    )
    return Panel(body, title="[bold cyan]AutoReason — attached[/]", border_style="cyan")


def _read_heartbeat(run_dir: Path) -> dict | None:
    path = run_dir / HEARTBEAT_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


_TERMINAL = {"converged", "max_passes_reached", "stopped", "error", "dry_run", "accepted", "interrupted"}


def _terminal_status(run_dir: Path) -> str | None:
    try:
        s = read_state(run_dir)
    except FileNotFoundError:
        return None
    if s.status in _TERMINAL:
        return s.status
    return None
