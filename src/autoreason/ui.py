"""Interactive Rich-based TUI for the AutoReason loop.

Two views:
- overview: phases, trajectory, spend, key map (default)
- agent:    live tail of one agent's stream (token flow), with pass nav

Keys (overview & agent):
  i           initial author_a output
  1 / 2 / 3   critic / author_b / synthesizer
  4 .. 9      judge_01 .. judge_06
  j / k       previous / next pass
  J / K       jump to first / latest pass
  o, Esc      back to overview
  q           quit (in attach: detach; in run: graceful stop signal)

Both run-mode (`autoreason run`) and attach-mode (`autoreason attach`) use the
same renderer; the only difference is whether a LoopMonitor is in-process or we
read everything from disk.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from autoreason.artifacts import (
    EVENTS_FILE,
    HEARTBEAT_FILE,
    HISTORY_FILE,
    INITIAL_FILE,
    PHASE_IDLE,
    PHASE_INITIAL,
    PHASE_PAUSED,
    PHASES_IN_PASS,
    LoopMonitor,
    read_state,
)
from autoreason.llm import format_spend
from autoreason.signals import append_command

_PHASE_ORDER = (PHASE_INITIAL,) + PHASES_IN_PASS  # initial, critic, author_b, synth, judges


def ui_enabled(quiet: bool, no_color: bool) -> bool:
    """Whether to render the rich Live UI."""
    if quiet or no_color:
        return False
    return sys.stdout.isatty()


# ── view state ─────────────────────────────────────────────────────────────


@dataclass
class ViewState:
    """Mutable UI state shared between renderer and keyboard reader."""

    mode: str = "overview"            # "overview" | "agent"
    pass_num: int = -1                # -1 = follow current pass; else explicit
    agent: str | None = None          # "initial" | "critic" | "author_b" | "synthesizer" | "judge_NN"
    quit: bool = False
    status_msg: str = ""              # transient line ("sent stop signal", etc.)


_AGENT_KEYS: dict[str, str] = {
    "i": "initial",
    "1": "critic",
    "2": "author_b",
    "3": "synthesizer",
    "4": "judge_01",
    "5": "judge_02",
    "6": "judge_03",
    "7": "judge_04",
    "8": "judge_05",
    "9": "judge_06",
}

# canonical (post-call) filename per agent, relative to pass_NN/
_CANONICAL_IN_PASS: dict[str, str] = {
    "critic": "critic.md",
    "author_b": "version_b.md",
    "synthesizer": "version_ab.md",
}


def _agent_label(agent: str) -> str:
    if agent.startswith("judge_"):
        return f"judge {int(agent.split('_')[1])}"
    return agent


# ── path resolution ────────────────────────────────────────────────────────


def _current_pass(run_dir: Path) -> int:
    """Best-effort current pass number from heartbeat or state.json."""
    hb = _read_json(run_dir / HEARTBEAT_FILE)
    if hb and hb.get("pass"):
        return int(hb["pass"])
    try:
        s = read_state(run_dir)
        return s.current_pass or s.num_passes or 0
    except FileNotFoundError:
        return 0


def _max_pass_with_dir(run_dir: Path) -> int:
    """Highest pass_NN/ that exists on disk (0 if none)."""
    best = 0
    for p in run_dir.glob("pass_*"):
        if not p.is_dir():
            continue
        try:
            n = int(p.name.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        if n > best:
            best = n
    return best


def _resolve_pass(run_dir: Path, view_pass: int) -> int:
    """Translate a ViewState.pass_num (which may be -1 = follow) into a real number."""
    if view_pass == -1:
        cur = _current_pass(run_dir)
        if cur > 0:
            return cur
        return _max_pass_with_dir(run_dir)
    return view_pass


def _agent_stream_path(run_dir: Path, pass_num: int, agent: str) -> Path | None:
    """Return the best file path to display for (pass_num, agent).

    Prefers the live `streams/` file (token-by-token); falls back to the
    canonical post-call artifact when the stream file is absent (e.g. an old
    completed pass).
    """
    if agent == "initial":
        live = run_dir / "streams" / "initial.md"
        if live.exists():
            return live
        canonical = run_dir / INITIAL_FILE
        return canonical if canonical.exists() else None

    if pass_num < 1:
        return None
    pass_dir = run_dir / f"pass_{pass_num:02d}"
    live = pass_dir / "streams" / f"{agent}.md"
    if live.exists():
        return live
    if agent in _CANONICAL_IN_PASS:
        canonical = pass_dir / _CANONICAL_IN_PASS[agent]
        return canonical if canonical.exists() else None
    if agent.startswith("judge_"):
        canonical = pass_dir / f"{agent}.md"
        return canonical if canonical.exists() else None
    return None


# ── keyboard reader ────────────────────────────────────────────────────────


def _stdin_is_interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except (ValueError, OSError):
        return False


class _RawTTY:
    """Context manager: put stdin into cbreak mode for single-keystroke reads."""

    def __init__(self, fd: int) -> None:
        self.fd = fd
        self._saved: list | None = None

    def __enter__(self) -> "_RawTTY":
        try:
            import termios
            import tty
            self._saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        except Exception:  # noqa: BLE001 — termios may be unavailable; fall back gracefully
            self._saved = None
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._saved is None:
            return
        try:
            import termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._saved)
        except Exception:  # noqa: BLE001
            pass


async def _read_key(fd: int) -> str:
    """Async: wait for at least one byte on stdin and decode it."""
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[str] = loop.create_future()

    def _on_ready() -> None:
        try:
            buf = os.read(fd, 8)
        except (OSError, BlockingIOError):
            buf = b""
        loop.remove_reader(fd)
        if not fut.done():
            fut.set_result(buf.decode("utf-8", errors="replace"))

    loop.add_reader(fd, _on_ready)
    return await fut


def _on_quit_default(state: ViewState) -> None:
    state.quit = True


async def keyboard_task(
    state: ViewState,
    run_dir: Path,
    on_quit: Callable[[ViewState], None] = _on_quit_default,
) -> None:
    """Background coroutine: read keys, mutate ViewState. Quiet on non-tty."""
    if not _stdin_is_interactive():
        return
    fd = sys.stdin.fileno()
    try:
        with _RawTTY(fd):
            while not state.quit:
                ch = await _read_key(fd)
                if not ch:
                    continue
                _handle_key(ch, state, run_dir, on_quit)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 — never let the UI take down the loop
        return


def _handle_key(
    ch: str,
    state: ViewState,
    run_dir: Path,
    on_quit: Callable[[ViewState], None],
) -> None:
    """Apply a single key event to ViewState."""
    state.status_msg = ""

    # Esc: bare 0x1b returned alone (multi-byte sequences arrive as one read)
    if ch == "\x1b":
        state.mode = "overview"
        return

    first = ch[0]
    if first == "q":
        on_quit(state)
        return
    if first in ("o", "O"):
        state.mode = "overview"
        return

    if first in _AGENT_KEYS:
        agent = _AGENT_KEYS[first]
        # initial only makes sense at task_dir level — pass_num doesn't apply
        if agent == "initial":
            path = run_dir / INITIAL_FILE
            live = run_dir / "streams" / "initial.md"
            if not path.exists() and not live.exists():
                state.status_msg = "no initial output yet"
                return
        else:
            target_pass = _resolve_pass(run_dir, state.pass_num)
            if target_pass < 1:
                state.status_msg = "no pass running yet"
                return
        state.mode = "agent"
        state.agent = agent
        return

    if first in ("j", "J", "k", "K"):
        latest = max(_current_pass(run_dir), _max_pass_with_dir(run_dir))
        if latest < 1:
            state.status_msg = "no passes yet"
            return
        cur = _resolve_pass(run_dir, state.pass_num)
        if first == "j":
            new = max(1, (cur if cur > 0 else 1) - 1)
        elif first == "k":
            new = min(latest, (cur if cur > 0 else 0) + 1)
        elif first == "J":
            new = 1
        else:  # "K"
            new = latest
        state.pass_num = new
        # if user navigated while in overview, stay in overview
        return

    # other keys: ignore silently


# ── rendering ──────────────────────────────────────────────────────────────


def _truncate(s: str, n: int) -> str:
    s = s.strip().splitlines()[0] if s.strip() else s
    return s if len(s) <= n else s[: n - 1] + "…"


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _phase_row(current_phase: str) -> Text:
    # During a paused state we want every phase dimmed — no "▶" pointer
    # (the active phase is "paused", which isn't in _PHASE_ORDER).
    current_idx = _PHASE_ORDER.index(current_phase) if current_phase in _PHASE_ORDER else -1
    parts: list[str] = []
    for i, ph in enumerate(_PHASE_ORDER):
        if current_phase == PHASE_IDLE or current_phase == PHASE_PAUSED:
            marker, style = "·", "dim"
        elif i < current_idx:
            marker, style = "✓", "green"
        elif i == current_idx:
            marker, style = "▶", "bold yellow"
        else:
            marker, style = " ", "dim"
        parts.append(f"[{style}]\\[{marker} {ph}][/]")
    return Text.from_markup("  ".join(parts))


def _paused_banner(run_dir: Path, is_paused: bool) -> Text | None:
    """Yellow banner shown above the phase row while a budget pause is active.

    Pulls the latest budget_exhausted event for the failing-call message and
    surfaces the resume command verbatim so the user can copy it.
    """
    if not is_paused:
        return None
    err = _latest_event_field(run_dir, "budget_exhausted", "error") or "(no detail)"
    err_short = err if len(err) <= 200 else err[:197] + "…"
    return Text.from_markup(
        f"[bold yellow]⏸  PAUSED — budget exhausted[/]\n"
        f"[yellow]{err_short}[/]\n"
        f"[bold]resume:[/]  autoreason signal {run_dir} resume\n"
        f"[dim]or Ctrl-C, then `autoreason resume {run_dir}` to retry later[/]"
    )


def _latest_event_field(run_dir: Path, event_type: str, field: str) -> str | None:
    """Scan events.jsonl tail-first for the most recent matching event field."""
    path = run_dir / EVENTS_FILE
    if not path.exists():
        return None
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") == event_type and d.get(field):
            return str(d[field])
    return None


def _trajectory(run_dir: Path, streak: int) -> Text:
    history_path = run_dir / HISTORY_FILE
    entries = _read_json(history_path)
    if not entries:
        return Text.from_markup("[dim]trajectory: (no passes yet)[/]")
    pieces = []
    for e in entries:
        w = str(e.get("winner", "?"))
        color = "green" if w == "A" else ("magenta" if w == "AB" else "yellow")
        pieces.append(f"[{color}]{w}[/]")
    streak_hint = f"   [dim](streak {streak})[/]" if streak else ""
    return Text.from_markup("trajectory: " + " → ".join(pieces) + streak_hint)


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


def _key_help(mode: str) -> Text:
    if mode == "overview":
        return Text.from_markup(
            "[dim]keys:[/] "
            "[bold]i[/]:initial  [bold]1[/]:critic  [bold]2[/]:author_b  "
            "[bold]3[/]:synth  [bold]4-9[/]:judges  "
            "[bold]j/k[/]:pass  [bold]q[/]:quit"
        )
    return Text.from_markup(
        "[dim]keys:[/] "
        "[bold]o/Esc[/]:overview  [bold]j/k[/]:prev/next pass  "
        "[bold]J/K[/]:first/last  [bold]i 1-9[/]:other agents  [bold]q[/]:quit"
    )


def _stats_from_snapshot(snap: dict, status_line: str | None = None) -> Text:
    spend = format_spend(
        int(snap.get("prompt_tokens", 0)),
        int(snap.get("completion_tokens", 0)),
        float(snap.get("total_cost_usd", 0.0)),
        bool(snap.get("cost_tracked", False)),
    )
    bits = [
        f"pass [bold]{snap.get('pass', 0)}[/]",
        f"phase elapsed [bold]{float(snap.get('elapsed_in_phase_s', 0.0)):.1f}s[/]",
        f"[bold]{spend}[/]",
        f"calls [bold]{snap.get('num_calls', 0)}[/]",
    ]
    if status_line:
        bits.append(status_line)
    return Text.from_markup("    ".join(bits))


def _snapshot_from_disk(run_dir: Path) -> tuple[dict, str]:
    """Read heartbeat/state from disk and produce a snapshot + status line."""
    hb = _read_json(run_dir / HEARTBEAT_FILE) or {}
    snap = {
        "pass": hb.get("pass", 0),
        "phase": hb.get("phase", PHASE_IDLE),
        "elapsed_in_phase_s": hb.get("elapsed_in_phase_s", 0.0),
        "streak": hb.get("streak", 0),
        "prompt_tokens": hb.get("prompt_tokens", 0),
        "completion_tokens": hb.get("completion_tokens", 0),
        "total_cost_usd": hb.get("total_cost_usd", 0.0),
        "num_calls": hb.get("num_calls", 0),
        "cost_tracked": hb.get("cost_tracked", False),
    }
    status_line = ""
    try:
        s = read_state(run_dir)
        status_line = f"[dim]status:[/] [bold]{s.status}[/]"
        # state.json wins on cost_tracked (heartbeat may predate flag)
        snap["cost_tracked"] = bool(snap["cost_tracked"] or s.cost_tracked)
        if not hb:
            snap["prompt_tokens"] = s.prompt_tokens
            snap["completion_tokens"] = s.completion_tokens
            snap["total_cost_usd"] = s.cost_usd
            snap["pass"] = s.current_pass or s.num_passes
            snap["streak"] = s.streak
    except FileNotFoundError:
        pass
    return snap, status_line


def _render_overview(
    state: ViewState,
    snap: dict,
    run_dir: Path,
    prompt_preview: str,
    config_summary: str,
    title_suffix: str = "",
) -> Panel:
    extra = f"  {state.status_msg}" if state.status_msg else ""
    header = Text.from_markup(
        f"[bold]prompt[/]: [italic cyan]{_truncate(prompt_preview, 80)}[/]\n"
        f"[dim]{config_summary}[/]\n"
        f"[dim]dir: {run_dir}[/]{extra}"
    )
    cur_phase = str(snap.get("phase", PHASE_IDLE))
    is_paused = cur_phase == PHASE_PAUSED
    paused = _paused_banner(run_dir, is_paused)

    rows: list[Any] = [header, Text("")]
    if paused is not None:
        rows.extend([paused, Text("")])
    rows.extend([
        _phase_row(cur_phase),
        Text(""),
        _trajectory(run_dir, int(snap.get("streak", 0))),
        Text(""),
        _stats_from_snapshot(snap),
        Text(""),
        _events_tail(run_dir),
        Text(""),
        _key_help("overview"),
    ])
    title = "[bold cyan]AutoReason[/]"
    if title_suffix:
        title += f" — {title_suffix}"
    border = "yellow" if is_paused else "cyan"
    return Panel(Group(*rows), title=title, border_style=border)


def _read_tail(path: Path, max_lines: int = 30, max_bytes: int = 20_000) -> tuple[str, int, int]:
    """Read the tail of a stream file. Returns (text, total_lines, total_words)."""
    try:
        # Read whole file but only render the tail; agent outputs are bounded by max_tokens.
        data = path.read_text()
    except OSError:
        return ("(read error)", 0, 0)
    if len(data) > max_bytes:
        data = data[-max_bytes:]
        # drop the partial first line so we don't show a chopped word
        nl = data.find("\n")
        if nl > 0:
            data = data[nl + 1:]
    lines = data.splitlines()
    total_lines = len(lines)
    total_words = sum(len(l.split()) for l in lines)
    if total_lines > max_lines:
        shown = lines[-max_lines:]
        prefix = f"[dim]… ({total_lines - max_lines} earlier lines)[/]\n"
    else:
        shown = lines
        prefix = ""
    return prefix + "\n".join(shown), total_lines, total_words


def _render_agent(
    state: ViewState,
    snap: dict,
    run_dir: Path,
    prompt_preview: str,
    config_summary: str,
    title_suffix: str = "",
) -> Panel:
    agent = state.agent or "critic"
    target_pass = _resolve_pass(run_dir, state.pass_num)
    path = _agent_stream_path(run_dir, target_pass, agent)

    # Live indicator: are we tailing the in-progress phase?
    cur_phase = str(snap.get("phase", PHASE_IDLE))
    cur_pass = int(snap.get("pass", 0))
    is_live = (
        path is not None
        and target_pass == cur_pass
        and (
            (agent == "initial" and cur_phase == PHASE_INITIAL)
            or (agent == cur_phase)
            or (agent.startswith("judge_") and cur_phase == "judges")
        )
    )

    breadcrumb_pass = "initial" if agent == "initial" else f"pass {target_pass}"
    live_tag = "[bold green]●[/] live" if is_live else "[dim]○ static[/]"
    extra = f"  {state.status_msg}" if state.status_msg else ""
    header = Text.from_markup(
        f"[bold]{breadcrumb_pass} · {_agent_label(agent)}[/]   {live_tag}\n"
        f"[dim]prompt: {_truncate(prompt_preview, 70)}[/]\n"
        f"[dim]source: {path if path else '(no file yet)'}[/]{extra}"
    )

    if path is None:
        body_text = Text.from_markup("[dim](no output yet for this agent)[/]")
        meta_line = Text.from_markup("[dim]waiting…[/]")
    else:
        text, total_lines, total_words = _read_tail(path)
        body_text = Text.from_markup(text or "[dim](empty)[/]")
        meta_line = Text.from_markup(
            f"[dim]{total_lines} lines · {total_words} words[/]"
        )

    stats = _stats_from_snapshot(snap)
    is_paused = cur_phase == PHASE_PAUSED
    paused = _paused_banner(run_dir, is_paused)

    rows: list[Any] = [header, Text("")]
    if paused is not None:
        rows.extend([paused, Text("")])
    rows.extend([
        body_text,
        Text(""),
        meta_line,
        Text(""),
        stats,
        Text(""),
        _key_help("agent"),
    ])
    title = f"[bold cyan]AutoReason · {breadcrumb_pass} · {_agent_label(agent)}[/]"
    if title_suffix:
        title = f"[bold cyan]AutoReason — {title_suffix} · {breadcrumb_pass} · {_agent_label(agent)}[/]"
    if is_paused:
        border = "yellow"
    elif is_live:
        border = "green"
    else:
        border = "cyan"
    return Panel(Group(*rows), title=title, border_style=border)


def _render(
    state: ViewState,
    snap: dict,
    run_dir: Path,
    prompt_preview: str,
    config_summary: str,
    title_suffix: str = "",
) -> Panel:
    if state.mode == "agent" and state.agent:
        return _render_agent(state, snap, run_dir, prompt_preview, config_summary, title_suffix)
    return _render_overview(state, snap, run_dir, prompt_preview, config_summary, title_suffix)


# ── live UI for `autoreason run` ───────────────────────────────────────────


async def ui_task(
    monitor: LoopMonitor,
    run_dir: Path,
    prompt_preview: str,
    config_summary: str,
    state: ViewState | None = None,
    interval: float = 0.3,
) -> None:
    """Background coroutine that redraws the UI until cancelled.

    Reads live data from `monitor` (in-process); ViewState is shared with the
    keyboard reader.
    """
    state = state or ViewState()
    console = Console()

    def _snap() -> dict:
        return monitor.snapshot()

    with Live(
        _render(state, _snap(), run_dir, prompt_preview, config_summary),
        console=console,
        refresh_per_second=10,
        transient=False,
    ) as live:
        try:
            while True:
                live.update(_render(state, _snap(), run_dir, prompt_preview, config_summary))
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            live.update(_render(state, _snap(), run_dir, prompt_preview, config_summary))
            raise


def _run_quit_handler(run_dir: Path) -> Callable[[ViewState], None]:
    """`q` in run mode: send a graceful stop signal; UI keeps drawing until exit."""

    def _handler(state: ViewState) -> None:
        try:
            append_command(run_dir, "stop")
            state.status_msg = "stop signal sent — finishing pass…"
        except OSError:
            state.status_msg = "could not write stop signal"

    return _handler


# ── attach: read-only live view from another terminal ─────────────────────


_TERMINAL = {
    "converged", "max_passes_reached", "stopped", "error",
    "dry_run", "accepted", "interrupted",
}


def _terminal_status(run_dir: Path) -> str | None:
    try:
        s = read_state(run_dir)
    except FileNotFoundError:
        return None
    if s.status in _TERMINAL:
        return s.status
    return None


async def attach_loop(
    run_dir: Path,
    prompt_preview: str,
    config_summary: str,
    interval: float = 0.5,
    interactive: bool = True,
) -> str:
    """Watch a run from disk until it reaches a terminal state.

    With `interactive=True` (default) and a TTY, key bindings let the viewer
    explore phases and passes. `q` detaches without stopping the run.
    """
    state = ViewState()
    console = Console()

    def _attach_quit(s: ViewState) -> None:
        s.quit = True
        s.status_msg = "detaching…"

    kb_task: asyncio.Task[None] | None = None
    if interactive and _stdin_is_interactive():
        kb_task = asyncio.create_task(keyboard_task(state, run_dir, on_quit=_attach_quit))

    try:
        with Live(
            _render(state, _snapshot_from_disk(run_dir)[0], run_dir, prompt_preview, config_summary, title_suffix="attached"),
            console=console,
            refresh_per_second=4,
            transient=False,
        ) as live:
            while True:
                snap, status_line = _snapshot_from_disk(run_dir)
                # decorate header status into config_summary so user sees it
                cfg_with_status = (
                    f"{config_summary}    {status_line}" if status_line else config_summary
                )
                live.update(_render(state, snap, run_dir, prompt_preview, cfg_with_status, title_suffix="attached"))
                if state.quit:
                    return _terminal_status(run_dir) or "detached"
                final = _terminal_status(run_dir)
                if final is not None:
                    live.update(_render(state, snap, run_dir, prompt_preview, cfg_with_status, title_suffix="attached"))
                    return final
                await asyncio.sleep(interval)
    finally:
        if kb_task is not None:
            kb_task.cancel()
            try:
                await kb_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
