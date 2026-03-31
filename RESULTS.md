# Autoreason Experiment Results

Full data and analysis. For the narrative, see `paper/autoreason.pdf`.

---

## Summary of All Experiments

| Experiment | Model | Task | Passes | Converged? | Key Finding |
|:---|:---|:---|---:|:---|:---|
| Multi-task (5 tasks) | Sonnet 4 | T1–T5 | 9–28 | Yes (all) | Autoreason wins 3/5, never below 2nd |
| Single-pass (5 tasks) | Sonnet 4 | T1–T5 | 1 | N/A | Autoreason loses to simpler methods |
| CoT judges | Sonnet 4 | T1, T2 | 5, 8 | Yes | 3× faster convergence |
| Monte Carlo (5 runs) | Sonnet 4 | T1 | 6–30 | 4/5 | Consistent quality ceiling |
| Constrained (Sonnet 4) | Sonnet 4 | T1 | 25 | No | Checklist constraints prevent convergence |
| Scaling baseline | Sonnet 4.6 | T2 | 50 | No | Autoreason dead last (Borda 7/35) |
| Remedy: margin | Sonnet 4.6 | T2 | 15 | Yes | Converges but quality still loses |
| Remedy: scope-aware | Sonnet 4.6 | T2 | 35 | No | No effect |
| Remedy: plateau | Sonnet 4.6 | T2 | 35 | No | A scores too low to trigger |
| Remedy: combined | Sonnet 4.6 | T2 | 17 | Yes | Margin rule does the work |
| Remedy: margin quality | Sonnet 4.6 | T2 | — | — | Borda 23–26/49, still loses to baselines |
| Remedy: anchored judges | Sonnet 4.6 | T2 | 25 | No | Best unconstrained (4 A wins) but no convergence |
| Remedy: subtractive synth | Sonnet 4.6 | T2 | 17 | No | 0 A wins |
| Remedy: anchored+subtractive | Sonnet 4.6 | T2 | 17 | No | Worse than either alone |
| **Constrained (Sonnet 4.6)** | **Sonnet 4.6** | **Pitch** | **10** | **Yes** | **Autoreason wins (Borda 30/35, 3 first)** |
| Paper-writing | Opus 4 | Paper | 9 | Yes | Ground-truth critic eliminates hallucination |

**Total: ~$85 in API costs across all experiments.**

---

## Sonnet 4: Multi-Task Results (5 tasks, iterative)

| Method | T1 | T2 | T3 | T4 | T5 | Avg | Rank |
|:---|---:|---:|---:|---:|---:|---:|---:|
| **Autoreason** | **35** | 19 | **29** | 25 | **31** | **27.8** | **1.4** |
| Critique & revise | 13 | **22** | 26 | **32** | 19 | 22.4 | 2.0 |
| Harsh critic | 18 | 19 | 27 | 20 | 26 | 22.0 | 2.6 |
| Conservative | 21 | 19 | 15 | 18 | 15 | 17.6 | 3.6 |
| Improve this | 18 | 11 | 8 | 10 | 14 | 12.2 | 4.4 |

Autoreason won tasks 1 (GTM strategy), 3 (remote work policy), 5 (incident response). Critique-and-revise won tasks 2 (notification system) and 4 (competitive positioning).

Pattern: autoreason excels on tasks with genuine tradeoffs where the A/B/AB structure surfaces different valid perspectives. Critique-and-revise wins on tasks with concrete technical requirements where a direct find-and-fix loop is more efficient.

## Single-Pass Results (1 pass each)

| Method | Calls | T1 | T2 | T3 | T4 | T5 | Avg |
|:---|---:|---:|---:|---:|---:|---:|---:|
| Harsh critic | 1 | **30** | **31** | 23 | **30** | **31** | 29.0 |
| Critique & revise | 1 | **30** | 30 | **31** | 28 | 23 | 28.4 |
| Autoreason | 5 | 24 | 22 | 24 | 17 | 24 | 22.2 |
| Improve this | 1 | 14 | 14 | 18 | 23 | 20 | 17.8 |
| Conservative | 1 | 7 | 8 | 9 | 7 | 7 | 7.6 |

Single-pass autoreason loses at 5× the cost. The value is in the loop.

## Chain-of-Thought Judges

| Judge Variant | Task 1 | Task 2 |
|:---|---:|---:|
| Baseline (holistic) | 14–15 passes | 12 passes |
| **Chain-of-thought** | **5 passes** | **8 passes** |
| Decomposed (3 specialists) | 7 passes | — |

CoT judges produce more decisive scores (A wins at 8–9 vs baseline's 6–7). The reasoning step acts as a debiasing mechanism. All subsequent experiments use CoT judges.

## Monte Carlo (5 runs, Task 1)

| Run | Passes | Converged? | Final Words |
|:---|---:|:---|---:|
| 1 | 30 | No (cap) | 1654 |
| 2 | 6 | Yes | 1453 |
| 3 | 14 | Yes | 1451 |
| 4 | 17 | Yes | 1618 |
| 5 | 8 | Yes | 1660 |

80% convergence rate. Final word counts cluster tightly (1451–1660) despite variable path length, suggesting a consistent quality ceiling.

## Game-Theoretic Analysis (91 passes)

- **Transitivity**: 1 Condorcet cycle in 91 passes (1.1%). Near-perfect.
- **Elo plateau**: Ratings stabilize at ~1540 by pass 5–10. Pass 15 (1547) vs pass 25 (1560), barely different.
- **Pairwise dominance**: Fully transitive: autoreason > critique-and-revise > harsh_critic > conservative > improve_this. 90% win rate (18/20 matchups).

---

## Sonnet 4.6: Scaling Failure + Remedies

### Baseline (unconstrained, Task 2)

50 passes, no convergence. A won 6 times (12%). AB dominated with 30+ wins.

7-judge blind panel:

| Method | Borda (/35) | 1st |
|:---|---:|---:|
| Critique & revise | **31** | 3 |
| Improve this | 30 | 4 |
| Harsh critic | 23 | 0 |
| Conservative | 14 | 0 |
| Autoreason | 7 | 0 |

### Round 1: Convergence Remedies

| Remedy | Passes | A | AB | B | Converged? |
|:---|---:|---:|---:|---:|:---|
| Margin (≥2 pts) | 15 | 3 | 8 | 4 | **Yes** |
| All combined | 17 | 3 | 12 | 2 | **Yes** |
| Scope-aware judges | 35 | 4 | 25 | 6 | No |
| Plateau detection | 35 | 2 | 22 | 11 | No |
| *Baseline* | *50* | *6* | *30+* | *rest* | *No* |

Only the margin requirement produced convergence. But convergence ≠ quality:

| Method | Borda (/49) | 1st |
|:---|---:|---:|
| Critique & revise | **43** | 2 |
| Improve this | 42 | 4 |
| Harsh critic | 39 | 1 |
| Autoreason (combined) | 26 | 0 |
| Autoreason (margin) | 23 | 0 |
| Conservative | 12 | 0 |
| Autoreason (baseline) | 11 | 0 |

Margin roughly doubles quality over baseline (23–26 vs 11) but still loses to all active baselines.

### Round 2: Root Cause

| Modification | Passes | A | AB | B | Converged? |
|:---|---:|---:|---:|---:|:---|
| **Constrained task** | **10** | **4** | **6** | **0** | **Yes** |
| Anchored judges | 25 | 4 | 12 | 9 | No |
| Subtractive synthesis | 17 | 0 | 10 | 7 | No |
| Anchored + subtractive | 17 | 1 | 6 | 10 | No |

Only the constrained task converged. Anchored judges were the most promising unconstrained modification (4 A wins in 25 passes) but not enough.

### Constrained Task Quality

| Method | Borda (/35) | 1st |
|:---|---:|---:|
| **Autoreason** | **30** | **3** |
| Improve this | 27 | 2 |
| Conservative | 25 | 2 |
| Harsh critic | 13 | 0 |
| Critique & revise | 10 | 0 |

Rankings invert vs unconstrained. Critique-and-revise (winner unconstrained at 31) now last at 10. It expanded to 932 words, violating the 500-word constraint. Autoreason stayed at 632 words.

### Root Cause Diagnosis

The scaling failure is about scope, not evaluation:
- Margin requirement: converges but not quality (termination ≠ quality)
- Scope-aware judges: no effect (AB preferred for reasons beyond verbosity)
- Plateau detection: can't trigger (A scores consistently 3–4)
- Anchored judges: slight improvement but insufficient
- Subtractive synthesis: no effect
- **Constrained task: converges AND wins quality comparison**

The synthesis operator needs a bounded improvement space. When scope is mechanically limited, the incumbent can reach a ceiling. When it isn't, there is always something to add.

---

## Paper-Writing Experiment (Opus 4)

Ran autoreason on the paper itself using claude-opus-4 with 3 Opus judges and ground-truth context. Converged in 9 passes: AB→A→AB→AB→AB→AB→AB→A→A.

**Ground-truth critic**: Without reference data, the initial draft hallucinated 4 claims (fabricated ablation study, fake confidence intervals, wrong model names, incorrect role descriptions). With ground-truth access, the critic caught all 4 on pass 1.

**Judge panel integrity**: A mixed panel (Opus + Sonnet + Gemini) failed for 11+ passes because Gemini's output failed the ranking parser, reducing the panel to 2 judges. Fixed to 3 working judges, convergence in 2 passes.

---

## Design Space

| Dimension | Tested | Notes |
|:---|:---|:---|
| Agent isolation: shared | v1 | Single agent, authorship bias |
| Agent isolation: fresh per role | v2 | Confirmed: B re-emerges after 15 passes |
| Judges: single | v1 | Noisy |
| Judges: 3 same-model | v2 | Stable. Correlated biases remain |
| Judges: mixed-model | Paper exp. | Gemini parser broke; untested properly |
| Evaluation: pick one | v1 | Loses information |
| Evaluation: ranked + Borda | v2 | Rich signal |
| Tiebreak: conservative | v2 | Load-bearing (3 saves in 26 passes) |
| Convergence: k=3 | v2 initial | Too strict (never reached) |
| Convergence: k=2 | v2 final | Correct for Sonnet 4 |
| Convergence: margin ≥2 | Remedy | Recovers convergence with 4.6, not quality |
| Convergence: plateau | Remedy | Failed (A scores too low) |
| Judge: holistic | v2 initial | Slow convergence |
| Judge: CoT | v2 | 3× faster, should be default |
| Judge: decomposed | v2 | 2× faster, more complex |
| Judge: scope-aware | Remedy | No effect |
| Judge: anchored | Remedy | Slight improvement, not enough |
| Synthesis: additive | v2 | Default. Drift vector with strong models |
| Synthesis: subtractive | Remedy | No effect |
| Task: unconstrained | v2 | Works with Sonnet 4, fails with 4.6 |
| Task: constrained (checklist) | v2 | Prevents convergence (critic finds violations) |
| **Task: constrained (scope)** | **Remedy** | **Works with Sonnet 4.6. The fix.** |

---

## Repository Structure

```
experiments/
├── v2/
│   ├── results_v2/                  Task 1 (26 passes, original)
│   ├── results_multi_task/          Tasks 1–5
│   ├── results_v1_comparison/       Single-pass comparison
│   ├── results_v1_lite/             v1 comparison (lite)
│   ├── results_monte_carlo/         5 runs of Task 1
│   ├── results_46_task02/           Sonnet 4.6 baseline (50 passes)
│   ├── results_46_remedy_margin/    Margin requirement
│   ├── results_46_remedy_scope/     Scope-aware judges
│   ├── results_46_remedy_plateau/   Plateau detection
│   ├── results_46_remedy_combined/  All three combined
│   ├── results_46_remedy_eval/      7-judge quality eval of margin outputs
│   ├── results_46_v3_anchored/      Anchored judges
│   ├── results_46_v3_subtractive/   Subtractive synthesis
│   ├── results_46_v3_anchored_subtractive/  Both
│   ├── results_46_v3_constrained/   500-word pitch (converged!)
│   └── results_46_constrained_eval/ 7-judge quality eval of constrained
├── v1/                              Original single-pass experiments
└── prior/                           Exploratory experiments
```
