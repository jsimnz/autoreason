"""Borda aggregation of judge rankings.

A pass produces three candidates labeled A (incumbent), B (adversarial
revision), and AB (synthesis). Each judge is shown the three candidates in a
randomized order and asked for a ranking in the form

    RANKING: [best], [second], [worst]

where each slot is 1, 2, or 3 referring to the judge's presentation order.
We map those numbers back to the original A/B/AB labels via the per-judge
order map, then Borda-aggregate across judges. On tie, the incumbent wins.
"""

from __future__ import annotations

import random

DEFAULT_LABELS: tuple[str, str, str] = ("A", "B", "AB")


def randomize_for_judge(
    version_a: str, version_b: str, version_ab: str
) -> tuple[str, dict[str, str]]:
    """Shuffle the three versions into randomized presentation order.

    Returns:
        (formatted_proposals, order_map) where order_map["1"] is the original
        label ("A"|"B"|"AB") of the proposal shown as PROPOSAL 1, etc.
    """
    versions = [("A", version_a), ("B", version_b), ("AB", version_ab)]
    random.shuffle(versions)
    order_map: dict[str, str] = {}
    parts: list[str] = []
    for i, (label, content) in enumerate(versions, start=1):
        order_map[str(i)] = label
        parts.append(f"PROPOSAL {i}:\n---\n{content}\n---")
    return "\n\n".join(parts), order_map


def parse_ranking(text: str, order_map: dict[str, str]) -> list[str] | None:
    """Extract the last `RANKING:` line from `text` and map positions to labels.

    Accepts ranks separated by commas, spaces, brackets, or any non-digit
    characters. Requires at least two digits in {1,2,3} to be considered valid.
    Returns the list of original labels in rank order (best first) or None.
    """
    for line in reversed(text.splitlines()):
        stripped = line.strip().strip("*").strip()
        if stripped.upper().startswith("RANKING:"):
            raw = stripped.split(":", 1)[1]
            nums = [c for c in raw if c in ("1", "2", "3")]
            if len(nums) >= 2:
                return [order_map.get(n, n) for n in nums]
    return None


def aggregate_rankings(
    rankings: list[list[str] | None],
    labels: tuple[str, ...] = DEFAULT_LABELS,
    tiebreak: str = "A",
) -> tuple[str, dict[str, int], list[list[str]]]:
    """Borda count over a list of rankings.

    N points for rank 1, N-1 for rank 2, ..., 1 for rank N (where N = len(labels)).
    None rankings (parse failures) are dropped. Ties are broken in favor of
    `tiebreak`, which defaults to "A" — the incumbent survives ties.

    Returns:
        (winner, scores, valid_rankings)
    """
    n = len(labels)
    points = list(range(n, 0, -1))
    scores: dict[str, int] = {label: 0 for label in labels}

    valid = [r for r in rankings if r is not None]
    for ranking in valid:
        for position, label in enumerate(ranking):
            if label in scores and position < n:
                scores[label] += points[position]

    priority: dict[str, int] = {
        label: (0 if label == tiebreak else i + 1) for i, label in enumerate(labels)
    }
    ordered = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))
    return ordered[0], scores, valid
