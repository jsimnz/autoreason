"""File-based inter-terminal signalling via commands.jsonl.

A runner polls `commands.jsonl` at each pass boundary, consuming any new
entries. Another terminal calls `autoreason signal <dir> <cmd>` which appends
one JSON line. Atomicity relies on POSIX append-mode writes being
line-atomic for small writes (well under PIPE_BUF).

Commands:
    stop                    graceful stop at next pass boundary
    accept                  accept current incumbent and stop
    inject <free text>      append guidance to the next critic prompt
    resume                  release a budget-exhaustion pause and retry the
                            failing call (used after restoring credits/quota)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autoreason.artifacts import COMMANDS_FILE, INJECTIONS_FILE

VALID_COMMANDS = ("stop", "accept", "inject", "resume")


def append_command(run_dir: Path, cmd: str, payload: str | None = None) -> dict[str, Any]:
    """Append a signal entry to commands.jsonl. Returns the entry written."""
    if cmd not in VALID_COMMANDS:
        raise ValueError(f"Unknown command '{cmd}'. Valid: {', '.join(VALID_COMMANDS)}")
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cmd": cmd,
        "payload": payload,
    }
    path = run_dir / COMMANDS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_commands(run_dir: Path) -> list[dict[str, Any]]:
    """Return all commands in the file (ignoring malformed lines)."""
    path = run_dir / COMMANDS_FILE
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


class SignalHandler:
    """Stateful consumer of commands.jsonl.

    Usage:
        handler = SignalHandler(run_dir, cursor=state.commands_cursor)
        handler.poll()
        if handler.stop_requested: ...
        text = handler.drain_injection()
        handler.record_consumed()  # persist advance to caller
    """

    def __init__(self, run_dir: Path, cursor: int = 0) -> None:
        self.run_dir = run_dir
        self.cursor = cursor
        self._stop = False
        self._accept = False
        self._resume = False
        self._pending: list[str] = []

    def poll(self) -> None:
        all_cmds = read_commands(self.run_dir)
        new = all_cmds[self.cursor :]
        self.cursor = len(all_cmds)
        for c in new:
            cmd = c.get("cmd")
            payload = c.get("payload")
            if cmd == "stop":
                self._stop = True
            elif cmd == "accept":
                self._accept = True
            elif cmd == "resume":
                self._resume = True
            elif cmd == "inject" and payload:
                self._pending.append(payload)

    @property
    def stop_requested(self) -> bool:
        return self._stop or self._accept

    @property
    def accept_requested(self) -> bool:
        return self._accept

    @property
    def resume_requested(self) -> bool:
        return self._resume

    def consume_resume(self) -> bool:
        """One-shot consume of a pending resume signal. Returns True if one was set."""
        if self._resume:
            self._resume = False
            return True
        return False

    def drain_injection(self) -> str:
        """Consume any pending injections, return the formatted append text (or '')."""
        if not self._pending:
            return ""
        body = "\n".join(self._pending)
        self._pending = []
        # Log to injections.jsonl for reproducibility
        with (self.run_dir / INJECTIONS_FILE).open("a") as f:
            for text in body.splitlines() or [body]:
                pass
            f.write(
                json.dumps(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "source": "signal",
                        "text": body,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return "\n\nAdditional user guidance:\n" + body
