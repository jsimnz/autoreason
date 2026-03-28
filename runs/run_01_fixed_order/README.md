# Run 01: Fixed Order (baseline, flawed)

**Date:** 2026-03-26
**Tasks:** 5 × 5 runs = 25 trials
**Author:** claude-sonnet-4-20250514 (temp=0.8)
**Judge:** claude-sonnet-4-20250514 (temp=0.3)
**Batch size:** 10

## Known Flaw

Judge saw versions labeled "Version A", "Version B", "Version AB" in fixed order.
Positional bias and label bias (AB implies synthesis/best-of-both) likely inflated AB picks.

## Results

- A: 2 (9%)
- B: 0 (0%)
- AB: 21 (91%)
- Parse errors: 2

## Conclusion

Cannot distinguish genuine AB superiority from positional/label bias. Run 02 fixes this with randomized order and neutral labels (Proposal 1/2/3).
