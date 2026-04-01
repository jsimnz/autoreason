# Compute-Matched Evaluation Results

## Task 1: GTM Strategy (Unconstrained, Sonnet 4)

3-way comparison: autoreason vs critique_and_revise@15 vs critique_and_revise@90

| Method | Borda (/21) | 1st | Words | LLM Calls |
|:---|---:|---:|---:|---:|
| critique_and_revise@15 | 16 | 4 | 2225 | ~15 |
| autoreason | 15 | 2 | 1539 | ~90 |
| critique_and_revise@90 | 11 | 1 | 2433 | ~90 |

### Key Findings

1. **More compute doesn't help baselines**: critique_and_revise@90 is *worse* than @15 (11 vs 16 Borda). 
   The extra 75 passes cause drift and bloat (2433 vs 2225 words).

2. **Autoreason is competitive but doesn't win on unconstrained tasks**: 15 Borda vs 16, close but 2nd.
   The 6x compute cost is not justified here — on unconstrained tasks.

3. **Autoreason prevents degradation**: Unlike cr@90, autoreason at equivalent compute doesn't degrade.
   The judge panel rejects regressions, keeping quality stable. But on unconstrained tasks, 
   "stable" ≈ "plateau" ≈ "good but not better than cheaper methods."

4. **This supports the paper's scope thesis**: On unconstrained tasks, the method's advantage is defensive 
   (prevents drift) not offensive (achieves higher quality). The quality ceiling is similar for all methods; 
   the difference is which methods degrade when given more compute.

### Implications for Paper

This result addresses the reviewer's compute-normalization concern:
- At equal compute, autoreason is competitive but doesn't clearly win on unconstrained tasks
- The value proposition changes: autoreason's advantage is that it *uses* compute safely, 
  while baselines waste it (or actively harm quality) with more compute
- This reinforces the scope finding: on constrained tasks, autoreason wins; on unconstrained, it's neutral-to-slightly-worse but doesn't degrade
