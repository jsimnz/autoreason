# Run 02: Randomized Blind Labels

**Date:** 2026-03-26
**Tasks:** 5 × 5 runs = 25 trials
**Author:** claude-sonnet-4-20250514 (temp=0.8)
**Judge:** claude-sonnet-4-20250514 (temp=0.3)
**Batch size:** 25
**Fix:** Randomized presentation order, neutral labels (Proposal 1/2/3), judge blind to provenance

## Results

- A: 4 (18%)
- B: 7 (32%)
- AB: 11 (50%)
- Parse errors: 3

## Per Task

- Task 01 (GTM strategy): AB=75%, B=25%
- Task 02 (notification system): B=75%, A=25%
- Task 03 (remote work policy): AB=80%, B=20%
- Task 04 (positioning doc): A=60%, B=20%, AB=20%
- Task 05 (incident response): AB=75%, B=25%

## Key Findings

1. Randomization completely changed the distribution. Run 01 (fixed order) had AB=91%, B=0%. Run 02 (blind) has AB=50%, B=32%. The fixed-order run was heavily biased.
2. B wins 32% — the revision alone often beats the synthesis. The AB step isn't always necessary.
3. A wins 18% — real selection pressure. The judge rejects revisions when the original was better.
4. Task 04 (positioning doc) is an outlier — A won 60%. The strawman may not have found real problems on that task type.
5. No task has all three versions winning — each task has a dominant pattern. Suggests task type affects which version benefits most.

## Comparison to Run 01

| Version | Run 01 (biased) | Run 02 (blind) |
|---------|----------------|----------------|
| A       | 9%             | 18%            |
| B       | 0%             | 32%            |
| AB      | 91%            | 50%            |
