# Autoreason: Autoresearch for Subjective Domains

## The Problem in 30 Seconds

Andrej Karpathy [tweeted](https://x.com/karpathy/status/2037921699824607591) on March 28, 2026:

> Drafted a blog post. Used an LLM to meticulously improve the argument over 4 hours. Wow, feeling great, it's so convincing! Fun idea let's ask it to argue the opposite. LLM demolishes the entire argument and convinces me that the opposite is in fact true. lol

This is the core problem with using LLMs for iterative refinement on subjective work. The model is always sycophantic when asked to improve, overly critical when asked to critique, and overly compromising when asked to synthesize. The output is shaped more by how you prompt than by what's actually better.

Karpathy's 4-hour draft didn't fail because the LLM was wrong. It failed because the loop had no fitness function. There was no independent evaluation — just a mirror.

## The Idea

Karpathy's autoresearch proved that an agent can autonomously improve code overnight: mutate, train, check val_bpb, keep or revert, repeat. It works because the metric is the fitness function — drift is impossible because a worse number always gets discarded.

Many domains have no such metric. Proposals, strategy, architecture decisions, policy — there's no number to check.

Autoreason extends autoresearch to these domains by constructing a subjective fitness function through independent blind evaluation. The same way science uses peer review where math can use proofs.

## How It Works

Every role is a fresh, isolated agent. No agent sees another agent's drafting process. The artifact is the thread of continuity, not the agent's memory.

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
   │ Critic  │   fresh agent, sees only current A
   └────┬──────┘   finds problems — no fixes
        │
   ┌────┴──────┐
   │ Author B  │   fresh agent, sees task + A + critique
   └────┬──────┘   revises A based on valid criticisms
        │
   ┌────┴───────────┐
   │  Synthesizer   │   fresh agent, sees task + A + B (randomized labels)
   └────┬───────────┘   takes strongest elements from each
        │
   ┌────┴───────────────────┐
   │ Judge Panel (3 judges) │   fresh agents, blind evaluation
   │ Ranked choice + Borda  │   sees task + A/B/AB (randomized labels + order)
   └────┬───────────────────┘
        │
        ├── Winner = A → streak++  (incumbent survives)
        └── Winner ≠ A → streak=0  (new incumbent)
        │
        ▼  loop until streak = 2
```

Why each piece matters:

- **Fresh agents per role** prevent authorship bias. An agent that wrote version A will unconsciously defend it even while "incorporating feedback." A fresh agent treats the critic's critique on its merits.

- **Original task prompt as anchor** keeps judges evaluating "which version best accomplishes what was asked for" rather than "which sounds most impressive." The task defines what "better" means.

- **Ranked choice (not scoring)** avoids injecting our assumptions about which dimensions matter. No rubric. The task prompt is the rubric.

- **Conservative tiebreak** — incumbent wins ties. New versions must earn a clear win. Favors stability over churn.

- **3-judge panel** averages out individual judge biases. Each judge gets a different random ordering of the versions.

## What We Found

We ran 26 passes on a go-to-market strategy task (claude-sonnet-4, 3-judge panel, Borda count aggregation).

### It Works for Quality Improvement

Pass 1: judges unanimously picked the revised version over the initial generation (9-3-6 Borda score). The method's value as a refinement mechanism is clear — the first few passes produce genuine, measurable improvement.

### It Surfaces a Real Structural Problem

After ~10 passes, the loop entered a **bloat/prune oscillation**:

- The synthesizer (AB) systematically adds detail. Judges reward thoroughness.
- Author B systematically prunes it. Fresh agents working from critique alone strip the bloat.
- The incumbent swings between "comprehensive" and "focused" without settling.

Word count tells the story: 847 → 1800 → 1644 → 1758 across 26 passes.

This isn't a bug — it's a signal that the task itself is underdetermined along the scope dimension. When you ask for "a strategy" without specifying depth or length, there's no stable answer to "how detailed should this be?" The loop honestly reflects that ambiguity.

### The Convergence Threshold Matters

We set convergence at 3 consecutive incumbent wins. Never reached it. But the loop hit 2 consecutive wins twice (passes 14-15 and 24-25), both times broken by 1 Borda point. A threshold of 2 would have converged at pass 15 — arguably the right stopping point based on the quality plateau.

### Fresh Agents Are Essential

Author B re-emerged as the dominant winner at passes 17-21 after being nearly irrelevant for 15 passes. A persistent agent would have learned to defer to the synthesis pattern. Fresh agents can't be captured by the trajectory.

### Conservative Tiebreak Is Load-Bearing

The incumbent won on tiebreak 3 times in 26 passes. Without that rule, each would have been an unnecessary incumbent change. Small rule, real impact on stability.

## Trajectory (26 Passes)

```
Pass  Winner  Scores (A/B/AB)  Notes
────  ──────  ───────────────  ─────
  1   B       3 / 9 / 6        Unanimous. Initial A clearly weakest.
  2   AB      4 / 6 / 8
  3   A       7 / 7 / 4        Tiebreak.
  4   AB      6 / 3 / 9        Unanimous AB.
  5   AB      5 / 5 / 8
  6   A       6 / 6 / 6        Perfect 3-way tie. Tiebreak.
  7   AB      4 / 6 / 8
  8   AB      5 / 5 / 8
  9   A       7 / 6 / 5        First clean A win.
 10   AB      5 / 5 / 8
 11   AB      5 / 6 / 7        Margins narrowing.
 12   A       7 / 4 / 7        Tiebreak.
 13   AB      7 / 3 / 8
 14   A       8 / 6 / 4        Strongest A score.
 15   A       7 / 4 / 7      ★ 2 consecutive — would converge here at threshold=2
 16   AB      7 / 3 / 8        Breaks streak by 1 point.
 17   B       6 / 7 / 5        B returns. Regime shift.
 18   AB      5 / 5 / 8
 19   B       4 / 8 / 6        B pruning bloat.
 20   B       4 / 8 / 6
 21   B       4 / 9 / 5
 22   AB      5 / 6 / 7
 23   AB      5 / 5 / 8
 24   A       9 / 5 / 4        Strongest A score ever.
 25   A       7 / 5 / 6      ★ 2 consecutive again
 26   AB      4 / 6 / 8        Broken again. Run killed here.
```

Winner distribution: A 31%, B 19%, AB 50%

## What's Next

In priority order:

1. **Convergence threshold = 2** — rerun to confirm pass 15 is the right stopping point
2. **Constrained task prompt** — add scope/length guidance, test if oscillation disappears
3. **Mixed-model judge panel** (sonnet + gpt-4o + gemini) — decorrelate judge biases
4. **Monte Carlo** — run the same task N times to test if the loop converges to the same place or different local optima
5. **Different task types** — generalizability across domains

## Code

Everything lives in `~/autoreason-experiment/`:

- `run_v2.py` — the iterative loop runner
- `config_v2.yaml` — model, temperature, judge count, convergence settings
- `tasks/` — task prompts
- `results_v2/` — all artifacts per pass (versions A/B/AB, critic, judge responses)
- `RESULTS.md` — detailed findings + full design space matrix of tested/untested permutations
