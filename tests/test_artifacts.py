"""Run-dir artifacts: state round-trip, slug, atomic write, resume detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoreason.artifacts import (
    LoopMonitor,
    RunState,
    atomic_write,
    make_run_dir,
    make_slug,
    pid_is_alive,
    read_state,
    write_state,
)
from autoreason.llm import CostTracker


class TestSlug:
    def test_basic(self):
        assert make_slug("Hello World") == "hello-world"

    def test_punctuation_stripped(self):
        assert make_slug("Hello, World! Yes?") == "hello-world-yes"

    def test_empty_fallback(self):
        assert make_slug("   ") == "run"
        assert make_slug("###") == "run"

    def test_truncation(self):
        long = "a" * 100
        assert len(make_slug(long, max_len=10)) <= 10


class TestStateRoundTrip:
    def test_write_read(self, tmp_path: Path):
        s = RunState(
            status="running",
            author_model="m/1",
            judge_model="m/2",
            num_passes=5,
            cost_usd=1.234567,
            streak=2,
        )
        write_state(tmp_path, s)
        s2 = read_state(tmp_path)
        assert s2.status == "running"
        assert s2.author_model == "m/1"
        assert s2.num_passes == 5
        assert abs(s2.cost_usd - 1.234567) < 1e-9
        assert s2.streak == 2

    def test_unknown_keys_ignored(self, tmp_path: Path):
        (tmp_path / "state.json").write_text(
            json.dumps({"status": "converged", "num_passes": 3, "bogus": 42})
        )
        s = read_state(tmp_path)
        assert s.status == "converged"
        assert s.num_passes == 3


class TestAtomicWrite:
    def test_replaces_existing(self, tmp_path: Path):
        p = tmp_path / "f.txt"
        p.write_text("old")
        atomic_write(p, "new")
        assert p.read_text() == "new"
        # no leftover tmp
        assert not any(x.name.endswith(".tmp") for x in tmp_path.iterdir())


class TestMakeRunDir:
    def test_creates_new(self, tmp_path: Path):
        d = make_run_dir(tmp_path, "my idea\nmore text")
        assert d.exists()
        assert d.is_dir()
        assert "my-idea" in d.name


class TestPidLiveness:
    def test_self_pid_alive(self):
        import os
        assert pid_is_alive(os.getpid())

    def test_none_pid_false(self):
        assert pid_is_alive(None) is False

    def test_zero_pid_false(self):
        assert pid_is_alive(0) is False


class TestLoopMonitor:
    def test_snapshot_fields(self, tmp_path: Path):
        ct = CostTracker()
        ct.record("m", 10, 5, 0.001)
        m = LoopMonitor(run_dir=tmp_path, cost_tracker=ct)
        m.set_phase(3, "critic")
        m.streak = 1
        m.num_passes = 2
        snap = m.snapshot()
        assert snap["pass"] == 3
        assert snap["phase"] == "critic"
        assert snap["total_cost_usd"] == 0.001
        assert snap["num_calls"] == 1
        assert snap["streak"] == 1

    def test_write_heartbeat(self, tmp_path: Path):
        m = LoopMonitor(run_dir=tmp_path)
        m.set_phase(1, "judges")
        m.write_heartbeat()
        data = json.loads((tmp_path / "heartbeat.json").read_text())
        assert data["phase"] == "judges"
