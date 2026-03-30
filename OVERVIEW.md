<p align="center">
  <h1 align="center">Autoreason</h1>
  <p align="center"><em>Autoresearch for subjective domains</em></p>
</p>

---

## The Problem

Andrej Karpathy, [March 28, 2026](https://x.com/karpathy/status/2037921699824607591):

> Drafted a blog post. Used an LLM to meticulously improve the argument over 4 hours. Wow, feeling great, it's so convincing! Fun idea let's ask it to argue the opposite. LLM demolishes the entire argument and convinces me that the opposite is in fact true. lol

The draft didn't fail because the LLM was wrong. It failed because the loop had no fitness function. There was no independent evaluation — just a mirror.

## The Idea

Karpathy's autoresearch proved an agent can autonomously improve code overnight: mutate, train, check val_bpb, keep or revert. It works because the metric is the fitness function — drift is impossible when a worse number always gets discarded.

Many domains have no such metric. Proposals, strategy, architecture decisions, policy — there's no number to check.

**Autoreason extends autoresearch to these domains** by constructing a subjective fitness function through independent blind evaluation. The same way science uses peer review where math can use proofs.

## How It Works

```
   ┌──────────┐
   │ Author A │ ─── generate initial version
   └────┬─────┘
        │
        ▼ ═══════════════════ LOOP ═══════════════════
        │
   ┌────┴──────┐
   │  Critic   │ ─── find problems (no fixes)
   └────┬──────┘
        │
   ┌────┴──────┐
   │ Author B  │ ─── revise A based on critique
   └────┬──────┘
        │
   ┌────┴──────────┐
   │ Synthesizer   │ ─── merge best of A + B
   └────┬──────────┘
        │
   ┌────┴──────────────────────────────────────┐
   │          Judge Panel  (3 judges)          │
   │  blind evaluation · ranked choice · Borda │
   │  chooses best of A, B, AB                 │
   └────┬──────────────────────────────────────┘
        │
        ├─── A wins  →  streak++
        └─── A loses →  winner becomes new A
        │
        ▼ ═══════════════════ /LOOP ══════════════════
          converged when streak = 2
```

Every role is a **fresh, isolated agent**. No shared context. The original task prompt anchors all evaluation.

## Results

Five tasks (strategy, system design, policy, positioning, incident response) · claude-sonnet-4 · 7-judge blind panel.

**A single pass loses to simpler methods.** With iteration:

| Method | Avg Borda | Avg Rank | Tasks Won |
|:---|---:|---:|---:|
| **Autoreason** | **27.8 / 35** | **1.4** | **3 / 5** |
| Critique & revise | 22.4 | 2.0 | 2 / 5 |
| Harsh critic | 22.0 | 2.6 | 0 / 5 |
| Conservative | 17.6 | 3.6 | 0 / 5 |
| Improve this | 12.2 | 4.4 | 0 / 5 |

**Chain-of-thought judges** cut convergence from 14 passes to 5 (3×). No architecture changes.

**Continuing past convergence hurts.** Pass 15 beat pass 25 by 6–1 in a blind panel.

**Monte Carlo** (5 runs, same task): 80% convergence. Outputs cluster tightly regardless of path.

**Game-theoretic validation** across 91 passes: near-perfect transitivity, ELO plateau by pass 5–10, fully transitive pairwise dominance.

### What the improvement looks like

Initial output: generic startup playbook ($49/user pricing, $100K MRR with 3 people, no validation). After 14 passes: quantified customer pain ($15K/incident × 6/yr), team-based pricing ($1,499/mo), 50+ customer interviews, competitive positioning against named tools, realistic unit economics (CAC $2K, LTV $54K). The adversarial process killed the unrealistic numbers.

### Model scaling: a cautionary result

With claude-sonnet-4-6 (stronger model), autoreason came **dead last** (Borda 7/35) after 50 passes without converging. The stronger model produced AB syntheses so consistently preferred by judges that the incumbent could never survive. The convergence mechanism may require adaptation as models improve — score-based plateau detection, asymmetric evaluation, or tiered model configs. Open question.

## Paper

Six pages covering all experiments: [`paper/autoreason.pdf`](paper/autoreason.pdf). The paper was itself written using autoreason with claude-opus-4 and ground-truth critic access.

---

Full findings, trajectory data, and design space matrix: [RESULTS.md](RESULTS.md)
Code and setup: [README.md](README.md)
