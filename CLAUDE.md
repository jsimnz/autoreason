# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo context

This repo is being repurposed as a CLI tool for iterative multi-agent refinement. Paper artifacts (paper/, tasks/, human_eval/, experiments/) live in a separate repo and are not constraints on this codebase.

Use `uv` for all Python tooling — the dev machine has no `pip` or `venv` on the system path.

```bash
uv venv
uv pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-...   # or any litellm-supported provider
```

## Common commands

```bash
# Run the test suite
uv run pytest

# Run a single test file / single test
uv run pytest tests/test_aggregate.py
uv run pytest tests/test_aggregate.py::test_borda_breaks_ties_with_incumbent

# Smoke-check the CLI without any LLM calls
uv run autoreason run --prompt "hello" --dry-run

# Live read-only view of an in-progress run from another terminal
uv run autoreason attach runs/<dir>
```

There is no separate lint or typecheck command configured — pytest is the only gate.

## Architecture

The system is an async refinement loop. One run = one prompt iterated until convergence; one **pass** = one critic→author_b→synthesizer→judge-panel cycle that picks a new incumbent.

### Module map (read these together to understand control flow)

- `cli.py` — Click entry point. `run` / `resume` / `status` / `list` / `attach` / `signal` / `compare`. `_execute_loop` wires together CostTracker, LoopMonitor, EventSink, SignalHandler, optional InteractivePauser, the rich UI task, and the heartbeat task — then drives `run_autoreason_loop`.
- `loop.py` — `run_autoreason_loop`: generates `initial_a.md` (or reuses it), then calls `run_pass` repeatedly. Tracks the convergence streak (consecutive A wins). Converges, hits max_passes, or stops on signal. Writes `history.json`, `incumbent_after_NN.md` (only when incumbent changes), and `final_output.md`.
- `pass_.py` — `run_pass`: the four-stage pipeline. Critic, author_b, synthesizer all hit `config.author_model`. Judges run **in parallel via `asyncio.gather`** and may use a heterogeneous panel via `config.model_for_judge(i)` (round-robin over `judge_models`). Existence of `pass_NN/result.json` is the resume sentinel — re-entering a completed pass returns the cached winner without LLM calls.
- `aggregate.py` — `randomize_for_judge` shuffles A/B/AB into PROPOSAL 1/2/3 with a per-judge `order_map`. `parse_ranking` extracts the **last** `RANKING:` line (lenient about separators). `aggregate_rankings` does Borda count; **ties always go to A (the incumbent)** — this is load-bearing for "no changes needed" being a first-class outcome.
- `prompts.py` + `default_prompts.yaml` — Five roles (`author_a`, `critic`, `author_b`, `synthesizer`, `judge`). User overrides merge per-role over defaults. Available format placeholders per role: `{task_prompt}`, `{version_a}`, `{critic}`, `{version_x}`, `{version_y}`, `{judge_proposals}`, `{injection}`.
- `config.py` — Pydantic Config with `extra=forbid`. Built by layering: defaults → YAML file → CLI overrides. **Heterogeneous judge panel rule**: passing multiple `--judge-model` flags without an explicit `--judges` makes the panel size equal `len(judge_models)`; with an explicit `--judges N`, models round-robin (`A,B,A,B`). `num_judges < len(judge_models)` is rejected.
- `llm.py` — `call_llm` is the only LLM entry point. Always streams (`stream=True` with `include_usage`). Retries with exponential backoff on rate/overload/timeout/connection errors. `CostTracker` records tokens for every call; **dollar cost is opt-in** (`--track-cost`) because it depends on litellm having pricing data. Empty completions raise with a hint about `max_tokens` being too low for reasoning-model budgets.
- `artifacts.py` — Run-directory layout, filenames, `RunState` dataclass (the `state.json` schema), `LoopMonitor` (in-memory snapshot of phase/cost), `EventSink` (append-only `events.jsonl`), `heartbeat_task` (writes `heartbeat.json` ~5s).
- `signals.py` — File-based inter-process signalling via `commands.jsonl`. `SignalHandler` is a stateful consumer with a cursor (`stop` / `accept` / `inject`). The cursor is persisted in `state.commands_cursor` so resumes don't replay old commands. POSIX line-atomic appends are how this works without a daemon — preserve that property.
- `interactive.py` — `InteractivePauser` blocks between passes and routes any injected text through the same `commands.jsonl` path as external signals. CLI disables the rich Live UI when `--interactive` is set (Live fights with stdin prompts).
- `resume.py` — Decides whether `state.json` is in a resumable status; reloads `Config` / `Prompts` / prompt text from the snapshot files written at run start. Refuses to resume runs whose recorded PID is still alive.
- `compare.py` — `autoreason list` / `compare` summarization and the optional LLM head-to-head judge panel for comparing 2–3 finished runs.
- `ui.py` — Rich Live panel renderer. `ui_enabled` returns False when stdout isn't a TTY or when `--quiet`/`--no-color`/`--interactive` is set.

### Key design invariants

- **Three candidates per pass, not two.** A (incumbent), B (adversarial revision), AB (synthesis). Keeping A as a real option is what lets the loop converge on "no changes needed."
- **Judges are blind.** The judge prompt only sees PROPOSAL 1/2/3 in shuffled order. Don't leak the A/B/AB labels into prompts.
- **Resume semantics live in two places.** `pass_NN/result.json` existence skips that pass; `state.commands_cursor` skips already-consumed signals. Both must be preserved when changing pass output behavior.
- **Borda ties go to A.** `aggregate_rankings(..., tiebreak="A")`. Don't change this default without understanding the convergence behavior — strong models converge fast precisely because A wins ties.
- **One LLM entry point.** All model calls go through `llm.call_llm`. New roles or features should reuse it so retry/cost-tracking/streaming behave consistently.

## Run directory layout

Self-contained per-run; see README "Artifact layout" for the full tree. Every file written during a run is either a content artifact (`*.md`), state (`state.json`, `heartbeat.json`), an append-only log (`events.jsonl`, `commands.jsonl`, `injections.jsonl`), or a reproducibility snapshot (`config.yaml`, `prompts.yaml`, `prompt.md`). `runs/` is gitignored.

## Test conventions

- `pytest-asyncio` is configured with `asyncio_mode = "auto"` — async test functions don't need a marker.
- `tests/test_cli_smoke.py` exercises the Click CLI end-to-end via `--dry-run`; touch this when changing CLI surface.
- `tests/test_aggregate.py` covers the parser and Borda — exact tie behavior is asserted, so a change in tiebreak ordering will fail tests loudly.
