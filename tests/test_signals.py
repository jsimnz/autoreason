"""commands.jsonl append/consume, cursor advancement, injection formatting."""

from __future__ import annotations

from pathlib import Path

import pytest

from autoreason.signals import (
    VALID_COMMANDS,
    SignalHandler,
    append_command,
    read_commands,
)


class TestAppendCommand:
    def test_append_creates_file(self, tmp_path: Path):
        entry = append_command(tmp_path, "stop")
        assert entry["cmd"] == "stop"
        assert entry["payload"] is None
        lines = (tmp_path / "commands.jsonl").read_text().splitlines()
        assert len(lines) == 1

    def test_inject_with_payload(self, tmp_path: Path):
        append_command(tmp_path, "inject", "focus on speed")
        cmds = read_commands(tmp_path)
        assert cmds[0]["cmd"] == "inject"
        assert cmds[0]["payload"] == "focus on speed"

    def test_unknown_cmd_rejected(self, tmp_path: Path):
        with pytest.raises(ValueError):
            append_command(tmp_path, "fire_ze_missiles")

    def test_valid_commands_set(self):
        assert VALID_COMMANDS == ("stop", "accept", "inject", "resume")


class TestSignalHandler:
    def test_stop(self, tmp_path: Path):
        append_command(tmp_path, "stop")
        h = SignalHandler(tmp_path)
        h.poll()
        assert h.stop_requested
        assert not h.accept_requested
        assert h.cursor == 1

    def test_accept_is_stop(self, tmp_path: Path):
        append_command(tmp_path, "accept")
        h = SignalHandler(tmp_path)
        h.poll()
        assert h.stop_requested
        assert h.accept_requested

    def test_inject_drains(self, tmp_path: Path):
        append_command(tmp_path, "inject", "a")
        append_command(tmp_path, "inject", "b")
        h = SignalHandler(tmp_path)
        h.poll()
        text = h.drain_injection()
        assert "a" in text
        assert "b" in text
        assert "Additional user guidance" in text
        # Drain is single-use
        assert h.drain_injection() == ""

    def test_injection_persists_to_file(self, tmp_path: Path):
        append_command(tmp_path, "inject", "foo")
        h = SignalHandler(tmp_path)
        h.poll()
        h.drain_injection()
        inj_lines = (tmp_path / "injections.jsonl").read_text().splitlines()
        assert len(inj_lines) == 1

    def test_cursor_advances_no_duplicate(self, tmp_path: Path):
        append_command(tmp_path, "inject", "first")
        h = SignalHandler(tmp_path)
        h.poll()
        first = h.drain_injection()
        append_command(tmp_path, "inject", "second")
        h.poll()
        second = h.drain_injection()
        assert "first" in first and "second" not in first
        assert "second" in second and "first" not in second

    def test_seeded_cursor_skips_past(self, tmp_path: Path):
        append_command(tmp_path, "inject", "old")
        append_command(tmp_path, "inject", "new")
        # Seed cursor=1 — only the second command is visible
        h = SignalHandler(tmp_path, cursor=1)
        h.poll()
        text = h.drain_injection()
        assert "new" in text
        assert "old" not in text

    def test_poll_with_no_file(self, tmp_path: Path):
        h = SignalHandler(tmp_path)
        h.poll()  # must not raise
        assert not h.stop_requested

    def test_malformed_line_skipped(self, tmp_path: Path):
        (tmp_path / "commands.jsonl").write_text('{"cmd":"stop"}\nnot json\n')
        cmds = read_commands(tmp_path)
        assert len(cmds) == 1
        assert cmds[0]["cmd"] == "stop"

    def test_resume_signal(self, tmp_path: Path):
        append_command(tmp_path, "resume")
        h = SignalHandler(tmp_path)
        h.poll()
        assert h.resume_requested
        # consume_resume is one-shot
        assert h.consume_resume() is True
        assert h.resume_requested is False
        assert h.consume_resume() is False
        # resume by itself is NOT a stop
        assert not h.stop_requested

    def test_resume_independent_of_stop(self, tmp_path: Path):
        append_command(tmp_path, "resume")
        append_command(tmp_path, "stop")
        h = SignalHandler(tmp_path)
        h.poll()
        assert h.resume_requested
        assert h.stop_requested
