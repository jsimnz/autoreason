# Autoreason: Self-Refinement That Knows When to Stop

**SHL0MS | HERMES AGENT**

[Paper (PDF)](paper/autoreason.pdf) · [Human Eval Materials](human_eval/)

---

Iterative self-refinement fails for three structural reasons: *prompt bias* (models hallucinate flaws when asked to critique), *scope creep* (outputs expand unchecked each pass), and *lack of restraint* (models never say "no changes needed"). Autoreason fixes all three.

Each iteration produces three competing versions — the **unchanged incumbent (A)**, an **adversarial revision (B)**, and a **synthesis (AB)** — judged by fresh agents with no shared context via blind Borda count. "Do nothing" is always a first-class option.

## Key Results

| Finding | Detail |
|---------|--------|
| **42/42 perfect sweep** | Haiku 3.5 + autoreason scored perfect Borda across 3 tasks; all baselines *degraded* below single-pass |
| **77% vs 73%** | Sonnet 4.6 on 150 CodeContests problems (private-test), autoreason vs single-pass |
| **40% vs 31%** | Haiku 3.5 autoreason vs best-of-6 sampling at matched compute (150 problems) |
| **Haiku 4.5: transition point** | At 60% private accuracy, autoreason's held-out gains vanish — the generation-evaluation gap has closed |
| **Code scaling curve** | Haiku 3.5 (40%) → Haiku 4.5 (60%) → Sonnet 4 (64%) → Sonnet 4.6 (77%) private-test with autoreason |
| **Refinement destroys weak models** | Critique-and-revise reduced Haiku 3.5 outputs by 59–70% in word count over 15 passes |
| **7 judges → 3× faster convergence** | Than 3 judges; 1 judge is noisy and slow |
| **Length-controlled: 21/28 wins** | Autoreason beats 3 of 4 baselines even at matched word count |
| **Both B and AB necessary** | Removing either collapses the tournament (convergence in 2–3 passes vs 24) |

## Method

```
Task Prompt → Incumbent A
                  ↓
        ┌─── Critic (fresh agent) ───→ Critique
        │
        ├─── Author B (fresh agent) ──→ Revision (B)
        │
        └─── Synthesizer (fresh) ─────→ Synthesis (AB)
                  ↓
          Judge Panel (3 fresh agents, Borda count)
                  ↓
              Winner → new A  (or converge if A wins k=2 times)
```

## Paper Contents

- **Writing experiments**: 5 open-ended tasks, 3 constrained tasks, 4 baselines, 15-pass iterations
- **Competitive programming**: 150 CodeContests problems × 3 strategies × 4 model tiers (Sonnet 4, Sonnet 4.6, Haiku 3.5, Haiku 4.5)
- **Model scaling**: 5-tier comparison (Llama 8B → Gemini Flash → Haiku 3.5 → Haiku 4.5 → Sonnet 4)
- **Ablations**: Judge count (1/3/7), Borda vs majority, component necessity, length-controlled evaluation
- **Robustness**: Monte Carlo (5 runs), multi-seed replication (15 runs across 5 tasks)
- **Failure analysis**: 8 remedy experiments for Sonnet 4.6 scaling failure, failure taxonomy

## Repository Structure

```
paper/                      # LaTeX source, figures, compiled PDF
tasks/                      # Task prompts (5 open-ended, 3 constrained)
human_eval/                 # Blinded evaluation materials for human raters
experiments/
  v2/
    run_overnight.py        # Main experiment runner (writing tasks)
    run_code_overnight.py   # Code experiment runner (CodeContests)
    run_code_haiku45.py     # Haiku 4.5 code experiment runner
    run_multi_seed.py       # Multi-seed replication
    run_ablations.py        # Component, judge, aggregation, length ablations
    compute_stats.py        # Bootstrap CIs and McNemar tests
    results_code_s46/       # Sonnet 4.6 code results (150 problems)
    results_code_haiku/     # Haiku 3.5 code results (150 problems)
    results_code_haiku45/   # Haiku 4.5 code results (150 problems)
    results_code_best_of_n/ # Best-of-N compute-matched control
    results_multi_seed/     # 15 independent writing runs
    results_ablations/      # Judge count, aggregation, component, length
    results_baselines/      # Baseline comparison outputs
    results_multi_task/     # Multi-task autoreason + baselines
    results_monte_carlo/    # Monte Carlo replication (5 runs)
    results_*_constrained/  # Constrained task experiments
    results_*_remedy/       # Scaling remedy experiments
```

## Human Evaluation

Blinded materials for human raters are in [`human_eval/`](human_eval/). 5 tasks × 3 methods (autoreason, critique-and-revise, single-pass), randomized 4-character codes. See [`human_eval/README.md`](human_eval/README.md) for the rubric and instructions.

## Citation

```
@article{shl0ms2026autoreason,
  title={Autoreason: Self-Refinement That Knows When to Stop},
  author={SHL0MS and Hermes Agent},
  year={2026},
  url={https://github.com/NousResearch/autoreason}
}
```
