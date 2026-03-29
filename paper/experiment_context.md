=== README.md ===

# Autoreason

**Autoresearch for subjective domains.**

Autoreason is an iterative refinement method for LLM-generated content where no objective metric exists. It constructs a subjective fitness function through independent blind evaluation — the same way science uses peer review where math can use proofs.

## The Core Idea

```
                    ┌─────┐
                    │  A  │  the original
                    └──┬──┘
                       │
                  ┌────┴────┐
                  │strawman │  find problems
                  └────┬────┘
            ┌──────────┼──────────┐
            ▼          ▼          ▼
         ┌─────┐   ┌─────┐   ┌──────┐
         │  A  │   │  B  │   │  AB  │
         │keep │   │fix  │   │synth │
         └──┬──┘   └──┬──┘   └──┬───┘
            └──────────┼──────────┘
                       ▼
                 ┌───────────┐
                 │blind judge│  which best
                 │  panel    │  accomplishes
                 └─────┬─────┘  the task?
                       │
                       ▼
                 winner → new A
                 repeat until A survives
```

**A** is conservatism: the current version is fine, the changes made things worse. **B** is adversarial editing: the critique found real problems and the revision fixes them. **AB** is what happens when you ask an agent to be objective: both versions got some things right, here's a synthesis that keeps the best of each. The judge decides which of these three framings actually produced the best result, with no knowledge of which is which.

## The Problem This Solves

LLMs exhibit compounding failure modes when used for iterative refinement on subjective work:

| Failure Mode | What Happens | Why It Happens |
|---|---|---|
| **Sycophancy** | Ask it to improve something and it strengthens whatever you hand it, regardless of whether the argument is actually sound | The model follows the implied instruction: "make this better" becomes "make this more of what it already is" |
| **Overcriticism** | Ask it to find problems and it always finds something, even when the work is sound | The instruction to critique is interpreted as an instruction to change — saying "this is fine" feels like task failure |
| **Overcompromise** | Ask it to synthesize two perspectives and it hedges everything, producing a mushy average instead of selecting the best answer per dimension | The model treats both inputs as equally valid and tries to include something from each, losing the sharpness of either |
| **Authorship bias** | An agent that wrote version A will defend it even while "incorporating feedback" from a critique | The drafting history in the context window creates a completion bias toward continuing the established pattern |
| **Scope drift** | Each iteration adds hedging, caveats, and complexity — the output bloats away from what was asked for | No anchor back to the original task; the model optimizes for "impressiveness" rather than "accomplishes the 

=== RESULTS.md (key sections) ===

# Autoreason Experiment Results

## v2 Experiment: Task 01 — Go-to-Market Strategy

**Task:** Propose a go-to-market strategy for an open-source developer tool (CLI for managing Kubernetes configs) with 5k GitHub stars, no revenue, 3-person team.

**Config:** claude-sonnet-4-20250514 for both author (temp=0.8) and judge (temp=0.3). 3-judge panel, Borda count, conservative tiebreak. Convergence threshold: 3 consecutive A wins.

**Duration:** 26 passes (~2.5 min/pass, ~65 min total, ~160 LLM calls)

### Full Trajectory

```
Pass  Winner  Scores (A/B/AB)  Streak  Notes
────  ──────  ───────────────  ──────  ─────
  1   B       3 / 9 / 6        0/3    Unanimous B. Initial A clearly weakest.
  2   AB      4 / 6 / 8        0/3    Synthesis improves on B.
  3   A       7 / 7 / 4        1/3    Tiebreak to A (A=B=7, conservative rule).
  4   AB      6 / 3 / 9        0/3    Unanimous AB. Strong synthesis.
  5   AB      5 / 5 / 8        0/3    AB continues winning.
  6   A       6 / 6 / 6        1/3    Perfect 3-way tie. Tiebreak to A.
  7   AB      4 / 6 / 8        0/3
  8   AB      5 / 5 / 8        0/3
  9   A       7 / 6 / 5        1/3    First clean A win on merit.
 10   AB      5 / 5 / 8        0/3
 11   AB      5 / 6 / 7        0/3    Margins narrowing.
 12   A       7 / 4 / 7        1/3    Tiebreak to A.
 13   AB      7 / 3 / 8        0/3
 14   A       8 / 6 / 4        1/3    Strongest A score yet.
 15   A       7 / 4 / 7        2/3    ★ Two consecutive A wins!
 16   AB      7 / 3 / 8        0/3    AB breaks the streak by 1 point.
 17   B       6 / 7 / 5        0/3    First B win since pass 1. Regime shift.
 18   AB      5 / 5 / 8        0/3
 19   B       4 / 8 / 6        0/3    B dominant — pruning bloat.
 20   B       4 / 8 / 6        0/3    B wins again.
 21   B       4 / 9 / 5        0/3    B streak: 3 of last 5 passes.
 22   AB      5 / 6 / 7        0/3    AB recovers.
 23   AB      5 / 5 / 8        0/3
 24   A       9 / 5 / 4        1/3    Strongest A score ever.
 25   A       7 / 5 / 6        2/3    ★ Two consecutive again!
 26   AB      4 / 6 / 8        0/3    AB breaks the streak again.
```

**Winner distribution:** A: 8 wins (31%), B: 5 wins (19%), AB: 13 wins (50%)

### Phase Analysis

**Phase 1 — Rapid Improvement (Passes 1–5)**
Initial A is clearly weak. B and AB win easily with strong margins. The loop is finding genuine improvements. This is the high-value phase.

**Phase 2 — Quality Plateau (Passes 6–16)**
A starts surviving, mostly on close calls and tiebreaks. Scores tighten. Passes 14-15 reach 2/3 consecutive A wins but can't lock the third. The incumbent is strong but the synthesis still finds marginal improvements.

**Phase 3 — Bloat/Prune Oscillation (Passes 17–26)**
B re-emerges as a winner (passes 17, 19, 20, 21) after being absent since pass 1. Then the cycle restarts: AB adds complexity, judges reward it, B strips it back. Second 2/3 streak at passes 24-25, broken again.

### Word Count Analysis

The incumbent's word count tells the structural story:

```
Pass   Words   Winner   Effect
────   ─────   ──────   ──────
  1     847    B        Fresh start
  2    1079    AB       +27% growth
  3    1172    A(tie)   Held
  4    1172    AB       Synthesis adds
  5    1246    AB       +6%
  6    1340    A(tie)   Held
  7    1340    AB       Grows
  8    1574    AB       +17%
  9    1705    A        Held (plateau?)
 10    1705    AB       Growth
 11    1752    AB       +3%
 12    1622    A        Held (slight shrink)
 13    1622    AB       Grows
 14    1800    A        Held (peak)
 15    1800    A        Held ★
 16    1800    AB       Grows
 17    1839    B        ← B starts pruning
 18    2037    AB       Spike to peak
 19    1707    B        -16% prune
 20    1644    B        -4% prune
 21    2008    B        Grows (new B is larger?)
 22    1702    AB       Shrinks
 23    1639    AB
 24    1758    A        Held
 25    1758    A        Held ★
 26    ~1617   AB       Slight shrink
```

**Key insight:** The loop oscillates between two attractors — "comprehensive" (AB adds detail, judges reward thoroughness) and "focused" (B strips back to essentials, judges reward clarity). When the task prompt doesn't specify desired scope or length, there's no stable equilibrium between these attractors.

### Key Findings

#### 1. The Loop Works for Quality Improvement
Early passes show genuine, unanimous improvement. Pass 1 is a clear B win (9 vs 3 vs 6). The incumbent after 5-10 passes is meaningfully better than the initial generation. Autoreason's value as a refinement mechanism is confirmed.

#### 2. Convergence Threshold of 3 May Be Too Strict
Twice the loop reached 2/3 consecutive A wins (passes 14-15 and 24-25). Both times AB broke the streak by 1 Borda point. With ranked choice across 3 judges, a single judge ranking AB above A is enough to prevent convergence. A threshold of 2 consecutive wins would have converged at pass 15 — arguably the right point given the quality plateau was already reached.

#### 3. The Bloat/Prune Oscillation Is a Structural Finding
AB systematically adds complexity. B systematically prunes it. When the task is ambiguous about scope, these two forces create a stable oscillation rather than a stable equilibrium. This isn't a bug in the method — it's a real signal that the task itself is underdetermined along the scope dimension.

#### 4. Conservative Tiebreak Is Load-Bearing
A won on tiebreak at passes 3, 6, and 12. Without the conservative rule (incumbent wins ties), these would have gone to B or AB and the loop would have been even less stable. The tiebreak is doing real work in favoring stability over churn.

#### 5. Fresh Agents Per Role Prevent Authorship Bias
B's resurgence at passes 17-21 — after being nearly irrelevant for 15 passes — shows that fresh agents aren't captive to the trajectory. A persistent author B would have learned to defer to the synthesis pattern. Fresh agents evaluate the strawman's critique on its merits.

#### 6. Judge Panel D

=== Experiment Config ===

author_model: "anthropic/claude-sonnet-4-20250514"
judge_model: "anthropic/claude-sonnet-4-20250514"
author_temperature: 0.8
judge_temperature: 0.3
max_tokens: 4096
num_judges: 3
max_passes: 50
convergence_threshold: 3


=== 5-Way Judge Panel Results ===

Borda scores: {'autoreason': 35, 'conservative': 21, 'improve_this': 18, 'harsh_critic': 18, 'critique_and_revise': 13}

First place counts: {'autoreason': 7, 'critique_and_revise': 0, 'improve_this': 0, 'conservative': 0, 'harsh_critic': 0}

Word counts: {'autoreason': 1800, 'critique_and_revise': 2507, 'improve_this': 2116, 'conservative': 862, 'harsh_critic': 1961}

Num judges: 7

Model: anthropic/claude-sonnet-4-20250514

=== Pass 15 vs Pass 25 ===

Pass 15 wins: 6/7

Pass 25 wins: 1/7

=== Autoreason vs Adversarial (with baseline) ===

Autoreason wins: 7/7

Adversarial wins: 0/7

=== Task Used ===

Propose a go-to-market strategy for an open-source developer tool that has 5k GitHub stars but no revenue. The tool is a CLI for managing Kubernetes configs. The team is 3 people. Cover: target customer segments, pricing model, distribution channels, first-year milestones, and what you'd explicitly not do yet.