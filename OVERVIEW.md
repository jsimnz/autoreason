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

## Results

Tested across 5 tasks with claude-sonnet-4. Each task ran autoreason to convergence plus four baselines (conservative, improve_this, harsh_critic, critique_and_revise) at 15 iterative passes, evaluated by a 7-judge blind panel.

**A single autoreason pass loses to simpler methods.** Harsh critic and critique-and-revise both outperform it at 1/5th the cost. But with iteration:

| Method | Avg Borda (max 35) | Avg Rank | Tasks Won |
|---|---|---|---|
| **autoreason** | **27.8** | **1.4** | **3/5** |
| critique & revise | 22.4 | 2.0 | 2/5 |
| harsh critic | 22.0 | 2.6 | 0/5 |
| conservative | 17.6 | 3.6 | 0/5 |
| improve this | 12.2 | 4.4 | 0/5 |

Autoreason won 3/5 tasks and never placed below 2nd. It excels on tasks with genuine tradeoffs (strategy, policy, incident response). Critique-and-revise wins on tasks with concrete technical requirements (system design, competitive positioning).

**Chain-of-thought judges** reduce convergence from 14 passes to 5 (3x) with no architecture changes — just adding "think step by step about each version" to the judge prompt.

**Continuing past convergence hurts.** Pass 15 output beat pass 25 by 6–1 in a blind panel. The first convergence point is the quality ceiling.

**Monte Carlo analysis** (5 independent runs): 80% convergence rate, final outputs cluster tightly regardless of path length.

**Game-theoretic validation**: nearly perfect transitivity (1.1% Condorcet cycle rate), ELO plateau by pass 5–10, fully transitive pairwise dominance across all methods.

### Model Scaling: A Cautionary Result

With a stronger model (claude-sonnet-4-6), autoreason came dead last (Borda 7/35) after 50 passes without converging. The stronger model produced AB syntheses so consistently preferred by judges that the incumbent could never survive. The convergence mechanism assumes the incumbent can eventually become good enough that challengers can't improve on it — with a sufficiently capable model, this assumption breaks. Whether architectural modifications (score-based plateau detection, asymmetric evaluation, tiered models) can recover the advantage remains open.

## The Qualitative Story

The initial Task 1 output was a generic startup playbook: $49/user pricing, $100K MRR with 3 people, no customer validation. After 14 passes of adversarial pressure, the converged version had: quantified customer pain ($15K/incident × 6/yr), team-based pricing ($1,499/mo matching how teams actually buy), validation from 50+ customer interviews, competitive positioning against named tools, and realistic unit economics (CAC $2K, LTV $54K).

The adversarial process didn't polish the prose — it forced the proposal to get concrete. It killed the unrealistic revenue numbers.

## Paper

A 6-page paper covering all experiments: `paper/autoreason.pdf` ([source](paper/autoreason.tex)). The paper was itself written using autoreason with claude-opus-4 and ground-truth critic access to prevent hallucination.

## Code

Everything lives in this repo. See [README.md](README.md) for setup and running instructions.

Full findings, trajectory data, and design space matrix: [RESULTS.md](RESULTS.md)
