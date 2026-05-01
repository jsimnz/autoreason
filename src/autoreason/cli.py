"""Click CLI entry point for AutoReason."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import click

from autoreason import __version__
from autoreason.artifacts import (
    CONFIG_FILE,
    EVENTS_FILE,
    FINAL_FILE,
    HISTORY_FILE,
    INITIAL_FILE,
    PROMPTS_FILE,
    PROMPT_FILE,
    EventSink,
    LoopMonitor,
    RunState,
    heartbeat_task,
    make_run_dir,
    pid_is_alive,
    read_prompt,
    read_state,
    write_config_snapshot,
    write_prompt,
    write_prompts_snapshot,
    write_state,
)
from autoreason.config import Config
from autoreason.llm import CostTracker, format_spend, load_dotenv
from autoreason.loop import RunResult, run_autoreason_loop
from autoreason.prompts import Prompts
from autoreason.resume import (
    cached_cost_total,
    is_resumable,
    load_resume_context,
)
from autoreason.compare import (
    list_run_summaries,
    render_compare_table,
    render_list_table,
    run_judge_sync,
    summarize_run,
)
from autoreason.interactive import InteractivePauser
from autoreason.signals import VALID_COMMANDS, SignalHandler, append_command
from autoreason.ui import attach_loop, ui_enabled, ui_task


def _load_envs() -> None:
    """Best-effort dotenv load from common locations."""
    for candidate in (".env", "~/.hermes/.env", "~/.config/autoreason/.env"):
        load_dotenv(candidate)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="autoreason")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output.")
@click.option("--no-color", is_flag=True, help="Disable colored output.")
@click.option("--log-file", type=click.Path(dir_okay=False), help="Write log to FILE.")
@click.pass_context
def main(ctx: click.Context, verbose: bool, quiet: bool, no_color: bool, log_file: str | None) -> None:
    """AutoReason — iterative multi-agent refinement for subjective work."""
    _load_envs()
    ctx.ensure_object(dict)
    ctx.obj.update({"verbose": verbose, "quiet": quiet, "no_color": no_color, "log_file": log_file})


@main.command()
@click.option("--prompt", type=str, help="Prompt text (inline).")
@click.option("--prompt-file", type=click.Path(exists=True, dir_okay=False), help="Read prompt from FILE.")
@click.option("--output", "-o", type=click.Path(file_okay=False), help="Output directory for this run.")
@click.option("--model", type=str, help="Author model (litellm ID).")
@click.option(
    "--judge-model",
    "judge_model",
    type=str,
    multiple=True,
    help="Judge model. Pass once for a homogeneous panel, or repeat to configure a heterogeneous panel. With --judges N, models round-robin across N judges (e.g. 2 models + --judges 4 → A,B,A,B).",
)
@click.option("--judges", type=int, help="Number of judges in the panel.")
@click.option("--max-passes", type=int, help="Maximum number of refinement passes.")
@click.option("--max-tokens", type=int, help="Max completion tokens per LLM call.")
@click.option("--convergence", type=int, help="Consecutive A wins required to converge.")
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False), help="YAML config file.")
@click.option("--prompts", "prompts_path", type=click.Path(exists=True, dir_okay=False), help="YAML prompts override file.")
@click.option("--interactive", is_flag=True, help="Pause after each pass for user input.")
@click.option("--dry-run", is_flag=True, help="Print plan without calling any LLM.")
@click.option(
    "--track-cost/--no-track-cost",
    "track_cost",
    default=None,
    help="Opt in to dollar-cost tracking (default: token counts only).",
)
@click.pass_context
def run(
    ctx: click.Context,
    prompt: str | None,
    prompt_file: str | None,
    output: str | None,
    model: str | None,
    judge_model: tuple[str, ...],
    judges: int | None,
    max_passes: int | None,
    max_tokens: int | None,
    convergence: int | None,
    config_path: str | None,
    prompts_path: str | None,
    interactive: bool,
    dry_run: bool,
    track_cost: bool | None,
) -> None:
    """Run a new refinement loop on a prompt."""
    prompt_text = _resolve_prompt(prompt, prompt_file)

    judge_model_single: str | None = None
    judge_models_list: list[str] | None = None
    if judge_model:
        if len(judge_model) == 1:
            judge_model_single = judge_model[0]
        else:
            judge_models_list = list(judge_model)

    overrides: dict[str, Any] = {
        "author_model": model,
        "judge_model": judge_model_single,
        "judge_models": judge_models_list,
        "num_judges": judges,
        "max_passes": max_passes,
        "max_tokens": max_tokens,
        "convergence_threshold": convergence,
        "track_cost": track_cost,
    }
    cfg = Config.load(config_path=config_path, overrides=overrides)
    prompts_obj = Prompts.load(override_path=prompts_path)

    run_dir = Path(output) if output else make_run_dir(Path("runs"), prompt_text)
    if output:
        run_dir.mkdir(parents=True, exist_ok=True)

    write_config_snapshot(run_dir, cfg)
    write_prompts_snapshot(run_dir, prompts_obj)
    write_prompt(run_dir, prompt_text)

    if dry_run:
        _print_dry_run(run_dir, cfg, prompts_obj, prompt_text)
        write_state(
            run_dir,
            RunState(
                status="dry_run",
                author_model=cfg.author_model,
                judge_model=cfg.judge_model or cfg.author_model,
            ),
        )
        return

    quiet = ctx.obj.get("quiet", False)
    no_color = ctx.obj.get("no_color", False)
    if not quiet:
        _print_run_header(run_dir, cfg)
    _execute_loop(
        run_dir, cfg, prompts_obj, prompt_text,
        quiet=quiet, no_color=no_color, is_resume=False,
        interactive=interactive,
    )


@main.command()
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False))
@click.pass_context
def resume(ctx: click.Context, run_dir: str) -> None:
    """Resume an interrupted run from RUN_DIR."""
    rd = Path(run_dir)
    try:
        cfg, prompts_obj, prompt_text, state = load_resume_context(rd)
    except FileNotFoundError as exc:
        click.secho(f"Cannot resume: missing artifact ({exc}).", fg="red", err=True)
        sys.exit(1)

    ok, reason = is_resumable(state)
    if not ok:
        click.secho(f"Cannot resume: {reason}.", fg="red", err=True)
        sys.exit(1)

    quiet = ctx.obj.get("quiet", False)
    no_color = ctx.obj.get("no_color", False)
    if not quiet:
        prior_spend = format_spend(
            state.prompt_tokens, state.completion_tokens, state.cost_usd, state.cost_tracked
        )
        click.echo(f"Resuming: {rd}")
        click.echo(f"Prior status: {state.status}, {state.num_passes} passes, {prior_spend}")
        click.echo("")

    _execute_loop(
        rd, cfg, prompts_obj, prompt_text,
        quiet=quiet, no_color=no_color, is_resume=True, interactive=False,
    )


@main.command()
@click.argument("previous_run_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--prompt", type=str, help="Prompt text (inline). Defaults to the previous run's prompt.")
@click.option("--prompt-file", type=click.Path(exists=True, dir_okay=False), help="Read prompt from FILE.")
@click.option("--output", "-o", type=click.Path(file_okay=False), help="Output directory for this run.")
@click.option("--model", type=str, help="Author model (litellm ID).")
@click.option(
    "--judge-model",
    "judge_model",
    type=str,
    multiple=True,
    help="Judge model. Pass once for a homogeneous panel, or repeat to configure a heterogeneous panel.",
)
@click.option("--judges", type=int, help="Number of judges in the panel.")
@click.option("--max-passes", type=int, help="Maximum number of refinement passes.")
@click.option("--max-tokens", type=int, help="Max completion tokens per LLM call.")
@click.option("--convergence", type=int, help="Consecutive A wins required to converge.")
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False), help="YAML config file.")
@click.option("--prompts", "prompts_path", type=click.Path(exists=True, dir_okay=False), help="YAML prompts override file.")
@click.option("--interactive", is_flag=True, help="Pause after each pass for user input.")
@click.option("--dry-run", is_flag=True, help="Print plan without calling any LLM.")
@click.option(
    "--track-cost/--no-track-cost",
    "track_cost",
    default=None,
    help="Opt in to dollar-cost tracking (default: token counts only).",
)
@click.pass_context
def extend(
    ctx: click.Context,
    previous_run_dir: str,
    prompt: str | None,
    prompt_file: str | None,
    output: str | None,
    model: str | None,
    judge_model: tuple[str, ...],
    judges: int | None,
    max_passes: int | None,
    max_tokens: int | None,
    convergence: int | None,
    config_path: str | None,
    prompts_path: str | None,
    interactive: bool,
    dry_run: bool,
    track_cost: bool | None,
) -> None:
    """Start a new run that continues from the final output of a completed run.

    Seeds the new run's incumbent from PREVIOUS_RUN_DIR/final_output.md, then
    executes as an independent run. By default the new run inherits the prompt,
    config, and prompts override from the previous run; pass any of the same
    flags as `run` to override.
    """
    prev_dir = Path(previous_run_dir)

    final_path = prev_dir / FINAL_FILE
    if not final_path.exists():
        click.secho(
            f"Cannot extend: {prev_dir} has no {FINAL_FILE} (run did not complete).",
            fg="red",
            err=True,
        )
        sys.exit(1)

    # Resolve prompt: explicit CLI flags win, otherwise inherit from previous run.
    if prompt or prompt_file:
        prompt_text = _resolve_prompt(prompt, prompt_file)
    else:
        prev_prompt_path = prev_dir / PROMPT_FILE
        if not prev_prompt_path.exists():
            raise click.UsageError(
                f"Previous run is missing {PROMPT_FILE}; pass --prompt or --prompt-file."
            )
        prompt_text = read_prompt(prev_dir).strip()

    judge_model_single: str | None = None
    judge_models_list: list[str] | None = None
    if judge_model:
        if len(judge_model) == 1:
            judge_model_single = judge_model[0]
        else:
            judge_models_list = list(judge_model)

    overrides: dict[str, Any] = {
        "author_model": model,
        "judge_model": judge_model_single,
        "judge_models": judge_models_list,
        "num_judges": judges,
        "max_passes": max_passes,
        "max_tokens": max_tokens,
        "convergence_threshold": convergence,
        "track_cost": track_cost,
    }

    # Inherit base config / prompts from the previous run unless the user passed their own.
    base_config_path = config_path or str(prev_dir / CONFIG_FILE)
    base_prompts_path = prompts_path or str(prev_dir / PROMPTS_FILE)
    if not Path(base_config_path).exists():
        base_config_path = None  # type: ignore[assignment]
    if not Path(base_prompts_path).exists():
        base_prompts_path = None  # type: ignore[assignment]

    cfg = Config.load(config_path=base_config_path, overrides=overrides)
    prompts_obj = Prompts.load(override_path=base_prompts_path)

    run_dir = Path(output) if output else make_run_dir(Path("runs"), prompt_text)
    if output:
        run_dir.mkdir(parents=True, exist_ok=True)

    write_config_snapshot(run_dir, cfg)
    write_prompts_snapshot(run_dir, prompts_obj)
    write_prompt(run_dir, prompt_text)

    # Seed the new run's initial incumbent from the previous run's final output.
    # loop._generate_or_reuse_initial picks this up and skips the author_a call.
    (run_dir / INITIAL_FILE).write_text(final_path.read_text())

    # Record lineage so `status` / future tooling can trace the chain.
    (run_dir / "extends.txt").write_text(str(prev_dir.resolve()) + "\n")

    if dry_run:
        _print_dry_run(run_dir, cfg, prompts_obj, prompt_text)
        write_state(
            run_dir,
            RunState(
                status="dry_run",
                author_model=cfg.author_model,
                judge_model=cfg.judge_model or cfg.author_model,
            ),
        )
        return

    quiet = ctx.obj.get("quiet", False)
    no_color = ctx.obj.get("no_color", False)
    if not quiet:
        click.echo(f"Extending: {prev_dir}")
        _print_run_header(run_dir, cfg)
    _execute_loop(
        run_dir, cfg, prompts_obj, prompt_text,
        quiet=quiet, no_color=no_color, is_resume=False,
        interactive=interactive,
    )


@main.command()
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False))
def status(run_dir: str) -> None:
    """Show status of a run, including trajectory."""
    rd = Path(run_dir)
    try:
        s = read_state(rd)
    except FileNotFoundError:
        click.secho("No state.json — this does not look like a run dir.", fg="red", err=True)
        sys.exit(1)

    live = s.status == "running" and pid_is_alive(s.pid)
    status_display = f"{s.status}{' (active)' if live else ''}"

    click.echo(f"Dir:       {rd}")
    click.echo(f"Status:    {status_display}")
    click.echo(f"Started:   {s.started_at}")
    if s.finished_at:
        click.echo(f"Finished:  {s.finished_at}")
    if s.last_heartbeat:
        click.echo(f"Heartbeat: {s.last_heartbeat}")
    click.echo(f"Author:    {s.author_model}")
    click.echo(f"Judge:     {s.judge_model}")
    click.echo(f"Passes:    {s.num_passes}")
    spend = format_spend(s.prompt_tokens, s.completion_tokens, s.cost_usd, s.cost_tracked)
    label = "Cost" if s.cost_tracked else "Usage"
    click.echo(f"{label}:     {spend}  ({s.num_calls} calls)")
    if s.pid:
        click.echo(f"PID:       {s.pid} ({'alive' if live else 'not running'})")
    if s.error:
        click.secho(f"Error:     {s.error}", fg="red")

    trajectory = _format_trajectory(rd)
    if trajectory:
        click.echo(f"Trajectory: {trajectory}")


@main.command(name="list")
@click.option(
    "--root",
    type=click.Path(file_okay=False),
    default="runs",
    show_default=True,
    help="Directory containing runs.",
)
def list_runs(root: str) -> None:
    """List runs discovered under ROOT."""
    from rich.console import Console

    summaries = list_run_summaries(Path(root))
    if not summaries:
        click.secho(f"No runs found under {root}.", fg="yellow")
        return
    Console().print(render_list_table(summaries))


@main.command()
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False))
def attach(run_dir: str) -> None:
    """Attach to a running refinement loop (read-only live view)."""
    rd = Path(run_dir)
    try:
        prompt_text = (rd / "prompt.md").read_text()
        cfg = read_state(rd)  # just to verify state.json exists
    except FileNotFoundError:
        click.secho("Not an AutoReason run dir (missing prompt.md or state.json).", fg="red", err=True)
        sys.exit(1)
    prompt_preview = prompt_text.splitlines()[0] if prompt_text.splitlines() else prompt_text
    cfg_summary = f"{cfg.author_model}  •  judge: {cfg.judge_model}"
    try:
        final = asyncio.run(attach_loop(rd, prompt_preview, cfg_summary))
    except KeyboardInterrupt:
        click.echo("\nDetached.")
        return
    click.echo(f"\nRun finished: {final}")


@main.command()
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False))
@click.argument("command", type=click.Choice(list(VALID_COMMANDS)))
@click.argument("payload", required=False)
def signal(run_dir: str, command: str, payload: str | None) -> None:
    """Send a signal to a running run.

    \b
    Commands:
        stop                    graceful stop after current pass
        accept                  accept current incumbent, stop
        inject <text>           inject user guidance into the next critic prompt
    """
    if command == "inject" and not payload:
        raise click.UsageError("`inject` requires a text payload.")
    entry = append_command(Path(run_dir), command, payload)
    click.echo(f"signal written: {entry['cmd']}" + (f" — {payload}" if payload else ""))


@main.command()
@click.argument("run_dirs", nargs=-1, required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--judge", is_flag=True, help="Spawn an LLM judge panel to rank the final outputs (2-3 runs).")
@click.option("--judges", "num_judges", type=int, default=3, show_default=True, help="Number of judges when using --judge.")
@click.option("--model", type=str, default=None, help="Judge model override (litellm ID).")
def compare(run_dirs: tuple[str, ...], judge: bool, num_judges: int, model: str | None) -> None:
    """Compare two or more runs side-by-side."""
    from rich.console import Console

    if len(run_dirs) < 2:
        raise click.UsageError("compare requires at least 2 run directories.")
    summaries = []
    for rd in run_dirs:
        s = summarize_run(Path(rd))
        if s is None:
            click.secho(f"Skipping {rd} — not a valid run dir.", fg="yellow", err=True)
            continue
        summaries.append(s)
    if len(summaries) < 2:
        raise click.UsageError("Need at least 2 valid runs to compare.")

    console = Console()
    console.print(render_compare_table(summaries))

    if judge:
        if len(summaries) not in (2, 3):
            raise click.UsageError("--judge supports exactly 2 or 3 runs.")
        click.echo("")
        click.echo(f"Running {num_judges}-judge panel on final outputs…")
        result = run_judge_sync(
            [s.run_dir for s in summaries],
            num_judges=num_judges,
            model=model,
        )
        click.echo("")
        click.secho("Judge panel result:", bold=True)
        for rank, item in enumerate(result["ordered"], start=1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, "  ") if not ctx_no_color() else f"#{rank}"
            click.echo(f"  {medal}  {item['dir']}  (score {item['score']})")
        judge_spend = format_spend(
            result.get("prompt_tokens", 0),
            result.get("completion_tokens", 0),
            result["cost_usd"],
            result.get("cost_tracked", False),
        )
        label = "cost" if result.get("cost_tracked", False) else "usage"
        click.echo(f"\nJudge {label}: {judge_spend}  ({result['model']})")


def ctx_no_color() -> bool:
    ctx = click.get_current_context(silent=True)
    return bool(ctx.obj.get("no_color", False)) if ctx and ctx.obj else False


# ── helpers ────────────────────────────────────────────────────────────────

def _execute_loop(
    run_dir: Path,
    cfg: Config,
    prompts_obj: Prompts,
    prompt_text: str,
    *,
    quiet: bool,
    no_color: bool,
    is_resume: bool,
    interactive: bool = False,
) -> None:
    """Run (or resume) the loop, persist state throughout, print a summary."""
    cost = CostTracker(track_cost=cfg.track_cost)
    cached_cost = cached_cost_total(run_dir) if is_resume else 0.0

    state = RunState(
        status="running",
        author_model=cfg.author_model,
        judge_model=cfg.judge_model or cfg.author_model,
        pid=os.getpid(),
        cost_usd=cached_cost,
        cost_tracked=cfg.track_cost,
    )
    # Preserve started_at across resumes
    if is_resume:
        try:
            prior = read_state(run_dir)
            state.started_at = prior.started_at
        except FileNotFoundError:
            pass
    write_state(run_dir, state)

    monitor = LoopMonitor(run_dir=run_dir, cost_tracker=cost)
    events = EventSink(run_dir / EVENTS_FILE)

    # Signal handler — seed cursor from prior state (so resumes don't replay old cmds)
    handler = SignalHandler(run_dir, cursor=state.commands_cursor if is_resume else 0)
    pauser = InteractivePauser(run_dir, handler) if interactive else None

    def _on_pass_complete(result: dict, incumbent: str) -> bool:
        handler.poll()
        state.commands_cursor = handler.cursor
        if handler.stop_requested:
            return False
        if pauser is not None:
            cont = pauser.pause(result, incumbent)
            handler.poll()
            state.commands_cursor = handler.cursor
            if not cont:
                return False
            if handler.stop_requested:
                return False
        return True

    def _get_injection() -> str:
        handler.poll()
        state.commands_cursor = handler.cursor
        return handler.drain_injection()

    # Rich Live fights with stdin prompts — disable it when interactive.
    show_ui = ui_enabled(quiet=quiet, no_color=no_color) and not interactive
    cfg_summary = (
        f"{cfg.author_model}  •  {cfg.num_judges} judges  •  "
        f"max {cfg.max_passes} passes  •  converge @ {cfg.convergence_threshold}"
    )
    prompt_preview = prompt_text.splitlines()[0] if prompt_text.splitlines() else prompt_text

    async def _driver() -> RunResult:
        tasks: list[asyncio.Task[None]] = []
        tasks.append(asyncio.create_task(heartbeat_task(monitor)))
        if show_ui:
            tasks.append(asyncio.create_task(
                ui_task(monitor, run_dir, prompt_preview, cfg_summary)
            ))
        try:
            return await run_autoreason_loop(
                prompt_text,
                run_dir,
                cfg,
                prompts_obj,
                cost_tracker=cost,
                monitor=monitor,
                events=events,
                on_pass_complete=_on_pass_complete,
                injections_getter=_get_injection,
            )
        finally:
            for t in tasks:
                t.cancel()
            for t in tasks:
                try:
                    await t
                except asyncio.CancelledError:
                    pass
            try:
                monitor.write_heartbeat()
            except OSError:
                pass

    result: RunResult | None = None
    try:
        result = asyncio.run(_driver())
    except KeyboardInterrupt:
        state.status = "interrupted"
        _finalize_state(state, cost, cached_cost, result=None, run_dir=run_dir)
        click.secho("\nInterrupted. Use `autoreason resume` to continue.", fg="yellow", err=True)
        sys.exit(130)
    except Exception as exc:
        state.status = "error"
        state.error = str(exc)
        _finalize_state(state, cost, cached_cost, result=None, run_dir=run_dir)
        click.secho(f"Error: {exc}", fg="red", err=True)
        raise

    # If the loop ended because of a signal, reflect that in the final status
    if result is not None and result.status == "stopped" and handler.accept_requested:
        result = RunResult(
            status="accepted",
            final_text=result.final_text,
            history=result.history,
            num_passes=result.num_passes,
            elapsed_seconds=result.elapsed_seconds,
            cost_usd=result.cost_usd,
        )

    _finalize_state(state, cost, cached_cost, result=result, run_dir=run_dir)

    if not quiet:
        click.echo("")
        click.echo(f"Status:  {result.status}")
        click.echo(f"Passes:  {result.num_passes}")
        spend = format_spend(
            state.prompt_tokens, state.completion_tokens, state.cost_usd, cfg.track_cost
        )
        cached_hint = ""
        if cached_cost > 0 and cfg.track_cost:
            cached_hint = f", ${cached_cost:.4f} cached"
        label = "Cost" if cfg.track_cost else "Usage"
        click.echo(
            f"{label}:   {spend}  ({cost.num_calls} new LLM calls{cached_hint})"
        )
        click.echo(f"Output:  {run_dir / 'final_output.md'}")


def _finalize_state(
    state: RunState,
    cost: CostTracker,
    cached_cost: float,
    result: RunResult | None,
    run_dir: Path,
) -> None:
    """Update `state` with live cost/token figures, then persist."""
    state.cost_usd = round(cost.total_usd + cached_cost, 6)
    state.num_calls = cost.num_calls
    state.prompt_tokens = cost.total_prompt_tokens
    state.completion_tokens = cost.total_completion_tokens
    if result is not None and state.status == "running":
        state.status = result.status
        state.num_passes = result.num_passes
    state.finished_at = _now_iso()
    state.pid = None
    write_state(run_dir, state)


def _resolve_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if prompt and prompt_file:
        raise click.UsageError("--prompt and --prompt-file are mutually exclusive.")
    if not prompt and not prompt_file:
        raise click.UsageError("Must provide --prompt or --prompt-file.")
    if prompt_file:
        return Path(prompt_file).read_text().strip()
    return prompt.strip()  # type: ignore[union-attr]


def _print_run_header(run_dir: Path, cfg: Config) -> None:
    click.echo(f"Run dir: {run_dir}")
    click.echo(f"Author:  {cfg.author_model} (temp={cfg.author_temperature})")
    if cfg.judge_panel_is_heterogeneous:
        panel = ", ".join(cfg.judge_models or [])
        click.echo(f"Judges:  [{panel}] (temp={cfg.judge_temperature})")
    else:
        click.echo(
            f"Judge:   {cfg.judge_model or cfg.author_model} × {cfg.num_judges} (temp={cfg.judge_temperature})"
        )
    click.echo(
        f"Max passes: {cfg.max_passes}, converge: {cfg.convergence_threshold} consecutive A wins"
    )
    click.echo("")


def _print_dry_run(run_dir: Path, cfg: Config, prompts_obj: Prompts, prompt_text: str) -> None:
    click.secho(f"[DRY RUN] Run dir: {run_dir}", fg="cyan")
    click.echo("")
    click.secho("--- Resolved config ---", fg="cyan")
    click.echo(cfg.to_yaml())
    click.secho("--- Initial prompt (author_a) ---", fg="cyan")
    system, user = prompts_obj.render("author_a", task_prompt=prompt_text)
    click.secho("[system]", bold=True)
    click.echo(system.rstrip())
    click.echo("")
    click.secho("[user]", bold=True)
    click.echo(user.rstrip())
    click.echo("")
    click.secho(
        f"Would run up to {cfg.max_passes} passes; converge at {cfg.convergence_threshold} consecutive A wins.",
        fg="cyan",
    )
    click.secho(
        f"Calls per pass: 1 critic + 1 author_b + 1 synthesizer + {cfg.num_judges} judges "
        f"= {3 + cfg.num_judges} LLM calls.",
        fg="cyan",
    )


def _format_trajectory(run_dir: Path) -> str:
    """Render history.json as `A→AB→A→A` or similar."""
    history_path = run_dir / HISTORY_FILE
    if not history_path.exists():
        return ""
    try:
        entries = json.loads(history_path.read_text())
    except (json.JSONDecodeError, ValueError):
        return ""
    return " → ".join(str(e.get("winner", "?")) for e in entries)


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
