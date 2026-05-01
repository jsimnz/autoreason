"""Per-pass interactive steering.

When the user passes --interactive, after each pass we pause, show a summary,
and offer a small menu (continue / stop / accept / inject / diff / view-full).
Injections route through the same commands.jsonl / SignalHandler mechanism
as `autoreason signal inject`, so the two paths remain consistent.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from autoreason.signals import SignalHandler, append_command


class InteractivePauser:
    """Blocking pause + menu invoked between passes."""

    def __init__(self, run_dir: Path, handler: SignalHandler) -> None:
        self.run_dir = run_dir
        self.handler = handler
        self.console = Console()

    def pause(self, result: dict[str, Any], incumbent: str) -> bool:
        """Show the summary + menu. Returns True to continue, False to stop."""
        while True:
            self._render_summary(result, incumbent)
            choice = self._prompt_choice()

            if choice == "c":
                return True
            if choice == "s":
                return False
            if choice == "a":
                append_command(self.run_dir, "accept")
                self.handler.poll()
                return False
            if choice == "i":
                text = click.prompt("Enter guidance text", type=str, default="", show_default=False)
                if text.strip():
                    append_command(self.run_dir, "inject", text.strip())
                    self.handler.poll()
                    self.console.print("[green]Injection queued for next pass.[/]")
                else:
                    self.console.print("[yellow]No text entered — skipping inject.[/]")
                return True
            if choice == "d":
                self._show_diff(result, incumbent)
                continue
            if choice == "v":
                self._show_full(result, incumbent)
                continue
            self.console.print("[red]Unknown choice.[/]")

    def _prompt_choice(self) -> str:
        raw = click.prompt(
            "[c]ontinue  [s]top  [a]ccept  [i]nject  [d]iff  [v]iew-full",
            default="c",
            show_default=False,
        )
        raw = (raw or "c").strip().lower()
        return raw[:1] if raw else "c"

    def _render_summary(self, result: dict[str, Any], incumbent: str) -> None:
        pass_num = result.get("pass", "?")
        winner = result.get("winner", "?")
        scores = result.get("scores", {}) or {}
        elapsed = result.get("elapsed_seconds", 0.0)
        cost = result.get("cost_usd", 0.0) or 0.0

        score_str = "  ".join(f"{k}={v}" for k, v in scores.items())
        winner_color = {"A": "green", "B": "yellow", "AB": "magenta"}.get(winner, "cyan")
        spend_bit = f"cost: [dim]${cost:.4f}[/]" if cost > 0 else "[dim](tokens only)[/]"

        header = Text.from_markup(
            f"[bold]Pass {pass_num}[/] complete   "
            f"winner: [{winner_color} bold]{winner}[/]   "
            f"scores: [dim]{score_str}[/]   "
            f"elapsed: [dim]{elapsed}s[/]   {spend_bit}"
        )

        critic_snippet = _read_snippet(self.run_dir / f"pass_{int(pass_num):02d}" / "critic.md", max_lines=12)
        winner_snippet = _first_lines(incumbent, n=12)

        body = Text.assemble(
            header, "\n\n",
            Text.from_markup("[bold]Critic (first 12 lines):[/]"), "\n",
            Text(critic_snippet, style="dim"), "\n",
            Text.from_markup("[bold]Winning version (first 12 lines):[/]"), "\n",
            Text(winner_snippet, style="dim"),
        )
        self.console.print(Panel(body, border_style=winner_color, title="AutoReason — pause"))

    def _show_diff(self, result: dict[str, Any], incumbent: str) -> None:
        """Diff the prior incumbent (version_a.md of this pass) against the new one."""
        pass_num = int(result.get("pass", 0))
        prior_file = self.run_dir / f"pass_{pass_num:02d}" / "version_a.md"
        if not prior_file.exists():
            self.console.print("[yellow]No prior incumbent file to diff against.[/]")
            return
        prior = prior_file.read_text()
        diff = "\n".join(
            difflib.unified_diff(
                prior.splitlines(),
                incumbent.splitlines(),
                fromfile="prior_incumbent",
                tofile="new_incumbent",
                lineterm="",
                n=2,
            )
        )
        if not diff:
            self.console.print("[dim](no textual diff — incumbent unchanged)[/]")
            return
        self.console.print(Syntax(diff, "diff", theme="ansi_dark", line_numbers=False))

    def _show_full(self, result: dict[str, Any], incumbent: str) -> None:
        self.console.print(Panel(
            incumbent,
            title=f"Full incumbent after pass {result.get('pass', '?')}",
            border_style="cyan",
        ))


def _read_snippet(path: Path, max_lines: int = 12) -> str:
    if not path.exists():
        return "(file not found)"
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return "(read error)"
    return "\n".join(lines[:max_lines]) + (f"\n… (+{len(lines) - max_lines} more lines)" if len(lines) > max_lines else "")


def _first_lines(text: str, n: int = 12) -> str:
    lines = text.splitlines()
    head = "\n".join(lines[:n])
    if len(lines) > n:
        head += f"\n… (+{len(lines) - n} more lines)"
    return head
