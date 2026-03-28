# Autoreason

**Autoresearch for subjective domains.**

Autoreason is an iterative refinement method for LLM-generated content where no objective metric exists. It constructs a subjective fitness function through independent blind evaluation — the same way science uses peer review where math can use proofs.

## The Problem

LLMs exhibit three compounding failure modes when used for iterative refinement on subjective work:

- **Sycophancy** — always strengthens whatever you hand it
- **Overcriticism** — always finds problems when prompted to critique, even when the work is sound  
- **Overcompromise** — produces mushy synthesis that averages instead of selecting the best answer

The output is shaped more by how you prompt than by what's actually better. There is no independent evaluation happening — just a mirror.

## The Method

Every role is a fresh, isolated agent with no shared context. The artifact is the thread of continuity, not the agent's memory.

```
ORIGINAL TASK PROMPT (anchor — seen by all roles)
        │
        ▼
   ┌──────────┐
   │ Author A │   generate initial version
   └────┬─────┘
        │
        ▼ ══════════════════ LOOP ══════════════════
        │
   ┌────┴──────┐
   │ Strawman  │   fresh agent, sees only current A
   └────┬──────┘   finds problems — no fixes
        │
   ┌────┴──────┐
   │ Author B  │   fresh agent, sees task + A + critique
   └────┬──────┘   revises A to address valid criticisms
        │
   ┌────┴───────────┐
   │  Synthesizer   │   fresh agent, sees task + A + B (randomized)
   └────┬───────────┘   keeps the strongest elements of each
        │
        ▼
   ┌─────────────────────────────────────────────────┐
   │            Judge Panel (3 judges)                │
   │  fresh agents, blind evaluation                  │
   │  ranked choice + Borda count                     │
   │                                                  │
   │  chooses best of:                                │
   │    A  — the incumbent (unchanged)                │
   │    B  — the adversarial revision                 │
   │    AB — the synthesis (best of both)             │
   └────┬─────────────────────────────────────────────┘
        │
        ├── Winner = A → streak++
        └── Winner = B or AB → streak = 0, winner becomes new A
        │
        ▼  loop until streak = 2 (converged)
```

**A** represents conservatism — "the current version is fine, the changes made things worse." **B** represents adversarial editing — "the critique found real problems and the revision fixes them." **AB** represents what happens when you ask an agent to be objective — "both versions got some things right, here's a synthesis that keeps the best of each." The judge panel decides which of these three framings actually produced the best result for the task, with no knowledge of which is which.

### Why It Works

| | Autoresearch | Autoreason |
|---|---|---|
| **Generate** | Mutate code | Produce A, B, AB |
| **Test** | Run experiment, check val_bpb | Independent judge panel evaluates |
| **Keep/revert** | Better metric → keep | Judges pick best → advance |
| **Anchor** | Last known good commit | Original task prompt |
| **Drift prevention** | Objective metric | Blind judges + incumbent always a candidate |

## Key Findings

Tested over 26 passes on a go-to-market strategy task (claude-sonnet-4, 3-judge panel).

**The loop works.** Pass 1 judges unanimously picked the revised version over initial generation (Borda 9-3-6). Early passes show genuine quality improvement.

**Fresh agents prevent authorship bias.** Author B re-emerged as winner at passes 17-21 after 15 passes of irrelevance. A persistent agent would have learned to defer.

**Bloat/prune oscillation.** On tasks with ambiguous scope, the synthesizer (AB) adds complexity while Author B prunes it. Word counts: 847 → 1800 → 1644 → 1758. The loop oscillates between "comprehensive" and "focused" without settling — a real signal that the task is underdetermined.

**Conservative tiebreak is load-bearing.** Incumbent wins ties. Removed 3 unnecessary churn events in 26 passes.

![Trajectory](experiments/v2/trajectory_chart.png)

Full trajectory data, analysis, and design space matrix: [RESULTS.md](RESULTS.md)

Shareable project overview: [OVERVIEW.md](OVERVIEW.md)

## Repository Structure

```
├── README.md              ← you are here
├── OVERVIEW.md            ← shareable intro (starts with Karpathy hook)
├── RESULTS.md             ← full findings, trajectory data, design space matrix
├── tasks/                 ← task prompts used across all experiments
├── experiments/
│   ├── v2/                ← current: iterative loop, judge panel, fresh agents
│   │   ├── run_v2.py
│   │   ├── config_v2.yaml
│   │   ├── results_v2/   ← all artifacts per pass
│   │   ├── make_chart.py
│   │   └── trajectory_chart.png
│   ├── v1/                ← original: single-pass, single judge, Monte Carlo
│   │   ├── run.py
│   │   ├── config.yaml
│   │   └── results/
│   └── prior/             ← exploratory experiments (blind eval, comparison, matrix)
```

## Running

```bash
pip install litellm pyyaml

# Dry run
python experiments/v2/run_v2.py --task 1 --dry-run

# Single task, unlimited passes
python experiments/v2/run_v2.py --task 1

# Cap at 20 passes
python experiments/v2/run_v2.py --task 1 --max-passes 20
```

Requires `ANTHROPIC_API_KEY` in environment or `~/.hermes/.env`.

## Next Experiments

1. Convergence threshold 2 — confirm pass 15 was the right stopping point
2. Constrained task prompt — test if scope constraints eliminate oscillation
3. Mixed-model judge panel (sonnet + gpt-4o + gemini) — decorrelate judge biases
4. Monte Carlo — N runs same task, test convergence consistency
5. Different task types — generalizability

## License

MIT
