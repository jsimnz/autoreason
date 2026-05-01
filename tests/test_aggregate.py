"""Tests for Borda aggregation and ranking parser."""

from __future__ import annotations

from autoreason.aggregate import (
    DEFAULT_LABELS,
    aggregate_rankings,
    parse_ranking,
    randomize_for_judge,
)


class TestParseRanking:
    def test_basic_comma_separated(self):
        order = {"1": "A", "2": "B", "3": "AB"}
        text = "some reasoning\n\nRANKING: 1, 2, 3"
        assert parse_ranking(text, order) == ["A", "B", "AB"]

    def test_bracketed(self):
        order = {"1": "A", "2": "B", "3": "AB"}
        text = "RANKING: [3], [1], [2]"
        assert parse_ranking(text, order) == ["AB", "A", "B"]

    def test_markdown_bold(self):
        order = {"1": "A", "2": "B", "3": "AB"}
        text = "**RANKING: 2, 3, 1**"
        assert parse_ranking(text, order) == ["B", "AB", "A"]

    def test_case_insensitive_prefix(self):
        order = {"1": "A", "2": "B", "3": "AB"}
        text = "ranking: 1, 3, 2"
        assert parse_ranking(text, order) == ["A", "AB", "B"]

    def test_takes_last_occurrence(self):
        order = {"1": "A", "2": "B", "3": "AB"}
        text = "RANKING: 1, 2, 3\n\nOn reflection:\nRANKING: 3, 2, 1"
        assert parse_ranking(text, order) == ["AB", "B", "A"]

    def test_missing_returns_none(self):
        order = {"1": "A", "2": "B", "3": "AB"}
        assert parse_ranking("no ranking here", order) is None

    def test_too_few_digits_returns_none(self):
        order = {"1": "A", "2": "B", "3": "AB"}
        assert parse_ranking("RANKING: just some text", order) is None

    def test_only_two_ranks_accepted(self):
        order = {"1": "A", "2": "B", "3": "AB"}
        assert parse_ranking("RANKING: 1, 2", order) == ["A", "B"]


class TestAggregateRankings:
    def test_unanimous_a(self):
        rankings = [["A", "B", "AB"]] * 3
        winner, scores, valid = aggregate_rankings(rankings)
        assert winner == "A"
        assert scores == {"A": 9, "B": 6, "AB": 3}
        assert len(valid) == 3

    def test_split_decision_ab_wins(self):
        rankings = [
            ["AB", "A", "B"],
            ["AB", "B", "A"],
            ["A", "AB", "B"],
        ]
        winner, scores, _ = aggregate_rankings(rankings)
        assert winner == "AB"
        assert scores["AB"] == 8
        assert scores["A"] == 6
        assert scores["B"] == 4

    def test_tiebreak_favors_incumbent_a(self):
        rankings = [
            ["B", "A", "AB"],
            ["A", "B", "AB"],
        ]
        winner, scores, _ = aggregate_rankings(rankings)
        assert scores["A"] == scores["B"] == 5
        assert winner == "A"

    def test_tiebreak_custom_label(self):
        rankings = [
            ["B", "A", "AB"],
            ["A", "B", "AB"],
        ]
        winner, _, _ = aggregate_rankings(rankings, tiebreak="B")
        assert winner == "B"

    def test_none_rankings_dropped(self):
        rankings = [["A", "B", "AB"], None, ["A", "AB", "B"]]
        winner, _, valid = aggregate_rankings(rankings)
        assert winner == "A"
        assert len(valid) == 2

    def test_all_none(self):
        winner, scores, valid = aggregate_rankings([None, None])
        assert valid == []
        assert all(v == 0 for v in scores.values())
        assert winner == "A"

    def test_default_labels(self):
        assert DEFAULT_LABELS == ("A", "B", "AB")


class TestRandomizeForJudge:
    def test_all_positions_filled(self, monkeypatch):
        monkeypatch.setattr("random.shuffle", lambda x: None)
        text, order = randomize_for_judge("aaa", "bbb", "ccc")
        assert order == {"1": "A", "2": "B", "3": "AB"}
        assert "PROPOSAL 1:" in text and "PROPOSAL 2:" in text and "PROPOSAL 3:" in text
        assert "aaa" in text and "bbb" in text and "ccc" in text

    def test_shuffles_produce_complete_map(self):
        import random as _random
        _random.seed(42)
        for _ in range(50):
            _, order = randomize_for_judge("a", "b", "c")
            assert set(order.keys()) == {"1", "2", "3"}
            assert set(order.values()) == {"A", "B", "AB"}
