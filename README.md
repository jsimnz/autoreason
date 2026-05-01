# AutoReason

**Iterative multi-agent refinement for subjective work** — writing, strategy, proposals, policy, analysis.

You provide a prompt. AutoReason produces an initial draft, then for each pass it spawns three fresh agents — a critic, an adversarial reviser, and a synthesizer — and asks a panel of independent judges to rank the results via Borda count. The incumbent survives ties. The loop stops automatically when the incumbent wins enough consecutive passes, so "do nothing" is always a first-class option.

```
Prompt → A (incumbent)
           │
           ▼
    ┌──► Critic ───► critique ──┐
    │                           ▼
    ├──► Author B ◄──── reads A + critique ──► B
    │                                           │
    └──► Synthesizer (sees A and B equally) ──► AB
                                                 │
                         Judge panel (N fresh) ──┤
                                                 ▼
                              Borda → winner → new A
                                                 │
                        if A wins K consecutive ─┘ → converged
```

## Install

```bash
git clone https://github.com/<you>/autoreason.git
cd autoreason
uv venv && uv pip install -e .
export ANTHROPIC_API_KEY=sk-...
```

(Or pip: `python -m venv .venv && . .venv/bin/activate && pip install -e .`)

Any litellm-supported provider works (Anthropic, OpenAI, OpenRouter, Gemini, local). Pass the model as `--model provider/model-id`.

## Quickstart

```bash
autoreason run --prompt "Design a 3-month plan to reduce tech debt in a 200k-LOC Python monorepo"
```

A rich live panel shows the current phase (critic → author_b → synth → judges), the trajectory so far (`A → AB → A → A`), and cumulative token usage. Dollar-cost tracking is opt-in via `--track-cost`.

Or from a file:

```bash
autoreason run --prompt-file examples/gtm-strategy.md
```

When the loop converges, the final output lands at `runs/<timestamp>-<slug>/final_output.md`.

## CLI reference

| Command | Purpose |
|---|---|
| `autoreason run --prompt "…" [flags]` | Start a new run |
| `autoreason run --prompt "…" --dry-run` | Print resolved config + first prompt, no API calls |
| `autoreason run --prompt "…" --interactive` | Pause after each pass to steer (see below) |
| `autoreason resume <dir>` | Continue an interrupted or signalled-stopped run |
| `autoreason extend <dir> [flags]` | Start a new run seeded from a completed run's `final_output.md` |
| `autoreason status <dir>` | Show status, cost, trajectory of a run |
| `autoreason list [--root runs/]` | Enumerate runs with one-line summaries |
| `autoreason attach <dir>` | Live read-only view of another run (any terminal) |
| `autoreason signal <dir> <cmd> [text]` | Send `stop` / `accept` / `inject <text>` |
| `autoreason compare dir1 dir2 [--judge]` | Side-by-side comparison, optional LLM head-to-head |

Common `run` flags:

```
--prompt TEXT             Inline prompt
--prompt-file PATH        Read prompt from file
--output PATH             Output dir (default: runs/<timestamp>-<slug>)
--model MODEL             Author model (litellm ID)
--judge-model MODEL       Judge model (defaults to author model)
--judges N                Judges per panel (default 3; 5-7 reduces noise)
--max-passes N            Cap iterations (default 30)
--convergence N           Consecutive A wins to converge (default 2)
--config config.yaml      Load config overrides
--prompts prompts.yaml    Override role prompts
--interactive             Pause per-pass menu
--dry-run                 No API calls
--track-cost              Compute $ cost via litellm (default: tokens only)
```

## Artifact layout

Every run is self-contained:

```
runs/<timestamp>-<slug>/
├── prompt.md                      the input, verbatim
├── config.yaml                    resolved config
├── prompts.yaml                   resolved prompts
├── state.json                     status, cost, pid, cursor
├── heartbeat.json                 live phase (refreshed ~5s)
├── commands.jsonl                 signals inbox
├── events.jsonl                   structured event log
├── injections.jsonl               any user guidance injected
├── history.json                   trajectory with per-pass scores
├── initial_a.md                   first draft
├── pass_01/
│   ├── version_a.md               incumbent entering this pass
│   ├── critic.md                  identified problems
│   ├── version_b.md               adversarial revision
│   ├── version_ab.md              synthesis
│   ├── judge_01.md ... judge_NN.md  raw judge responses
│   └── result.json                winner, Borda scores, timings, cost
├── pass_02/ …
├── incumbent_after_NN.md          snapshot when incumbent changes
└── final_output.md                the converged winner
```

## Steering a running loop

From any terminal:

```bash
# Watch a run live
autoreason attach runs/2026-04-20-gtm

# Inject guidance into the next critic prompt
autoreason signal runs/2026-04-20-gtm inject "focus on enterprise buyers"

# Stop cleanly at the next pass boundary
autoreason signal runs/2026-04-20-gtm stop

# Accept the current incumbent and stop
autoreason signal runs/2026-04-20-gtm accept
```

Signals are atomic JSONL appends — they work across tmux panes, SSH sessions, and separate terminals without any daemon. No race conditions.

## Interactive mode

```bash
autoreason run --prompt-file idea.md --interactive
```

Pauses after every pass with a summary panel (winner, scores, critic snippet, incumbent snippet) and a menu:

```
[c]ontinue  [s]top  [a]ccept  [i]nject  [d]iff  [v]iew-full
```

`inject` appends free text to the next critic prompt as "Additional user guidance: …"; `diff` shows the change between the prior incumbent and the new one; `view-full` prints the whole current incumbent.

## Resume

Interrupted runs pick up cleanly:

```bash
autoreason run --prompt-file big.md --output runs/big
# ... kill mid-pass with Ctrl-C ...
autoreason resume runs/big
```

Completed passes (`pass_NN/result.json` present) are reused as cache; the loop restarts from the first incomplete pass with the correct incumbent and streak.

## Extend

`resume` finishes an interrupted run. `extend` does something different: it takes a **completed** run and starts a fresh, independent run seeded from its `final_output.md`. Use it when you want to keep iterating past convergence, swap models, or change the prompt with the previous output as the starting point.

```bash
# Continue from a converged run with the same prompt, models, and config
autoreason extend runs/2026-04-20-gtm

# Same starting incumbent, but redirect the next round
autoreason extend runs/2026-04-20-gtm --prompt "Now narrow this to enterprise buyers only"

# Same incumbent, stronger judge panel
autoreason extend runs/2026-04-20-gtm --judges 5 --judge-model anthropic/claude-opus-4-7
```

`extend` accepts the same flags as `run`. By default the new run inherits the previous run's `prompt.md`, `config.yaml`, and `prompts.yaml`; any CLI flag overrides the inherited value. The new run gets its own `runs/<timestamp>-<slug>/` directory, its own state, history, and cost — the parent is untouched. An `extends.txt` file in the new run records the parent path for traceability.

The seeded `initial_a.md` skips the author_a call, so the first pass starts the critic→author_b→synth→judges cycle directly against the previous final output.

## Configuration

All flags have corresponding config keys. A minimal `config.yaml`:

```yaml
author_model: "anthropic/claude-sonnet-4-5"
judge_model: "anthropic/claude-sonnet-4-5"
author_temperature: 0.8
judge_temperature: 0.3
num_judges: 3
max_passes: 30
convergence_threshold: 2
max_tokens: 4096
```

Precedence: CLI flags → config file → built-in defaults.

## Custom prompts

Override any role's system persona or user template via a YAML file matching the structure of `src/autoreason/default_prompts.yaml`:

```yaml
critic:
  system: |
    You are a senior operator with 20 years of experience. Be blunt.
    Only flag problems that would actually hurt this in practice.
```

```bash
autoreason run --prompt-file idea.md --prompts my-prompts.yaml
```

Placeholders available per role: `{task_prompt}`, `{version_a}`, `{critic}`, `{version_x}`, `{version_y}`, `{judge_proposals}`, `{injection}`.

## Design notes

- **Fresh agents, no shared context.** The critic doesn't know an author. The author_b doesn't know it was adversarial. The judges don't know the authorship order. This is the main defense against sycophancy and drift.
- **Three candidates, not two.** Keeping the incumbent (A) as a literal option lets the loop say "no changes needed" — which turns out to be the single most important feature for weak models.
- **Borda, not majority.** A three-candidate majority vote has too many ties; Borda counts full rankings and resolves cleanly. Incumbent wins ties.
- **Convergence, not fixed passes.** Strong models converge in 2-4 passes; weak models oscillate. A fixed iteration count wastes compute on the former and corrupts the latter.

## Credits

The method is described in an accompanying research paper maintained in a separate repository. This repo is the companion tool: a clean extraction of the core refinement loop as a usable CLI.

Inspired by Karpathy's [autoresearch](https://github.com/karpathy/autoresearch) and aiming-lab's [AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw).
