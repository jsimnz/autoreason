"""CLI smoke tests: --help and --dry-run exit 0 with expected content."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from autoreason.cli import main


class TestHelp:
    def test_top_level_help(self):
        r = CliRunner().invoke(main, ["--help"])
        assert r.exit_code == 0
        assert "AutoReason" in r.output
        for sub in ("run", "resume", "extend", "status", "list", "attach", "signal", "compare"):
            assert sub in r.output

    def test_run_help(self):
        r = CliRunner().invoke(main, ["run", "--help"])
        assert r.exit_code == 0
        assert "--prompt" in r.output
        assert "--dry-run" in r.output
        assert "--interactive" in r.output

    def test_version(self):
        r = CliRunner().invoke(main, ["--version"])
        assert r.exit_code == 0
        assert "autoreason" in r.output.lower()


class TestDryRun:
    def test_dry_run_prompt(self, tmp_path: Path):
        out = tmp_path / "run"
        r = CliRunner().invoke(
            main,
            ["run", "--prompt", "Design a small ETL system", "--dry-run", "--output", str(out)],
        )
        assert r.exit_code == 0, r.output
        assert (out / "config.yaml").exists()
        assert (out / "prompts.yaml").exists()
        assert (out / "prompt.md").exists()
        state = json.loads((out / "state.json").read_text())
        assert state["status"] == "dry_run"

    def test_dry_run_with_prompt_file(self, tmp_path: Path):
        src = tmp_path / "idea.md"
        src.write_text("Write a 500-word product brief\n")
        out = tmp_path / "run2"
        r = CliRunner().invoke(
            main,
            ["run", "--prompt-file", str(src), "--dry-run", "--output", str(out)],
        )
        assert r.exit_code == 0, r.output
        assert "product brief" in (out / "prompt.md").read_text()

    def test_requires_prompt(self, tmp_path: Path):
        out = tmp_path / "run3"
        r = CliRunner().invoke(main, ["run", "--dry-run", "--output", str(out)])
        assert r.exit_code != 0
        assert "prompt" in r.output.lower()

    def test_mutually_exclusive(self, tmp_path: Path):
        src = tmp_path / "idea.md"
        src.write_text("x")
        out = tmp_path / "run4"
        r = CliRunner().invoke(
            main,
            ["run", "--prompt", "a", "--prompt-file", str(src), "--dry-run", "--output", str(out)],
        )
        assert r.exit_code != 0


class TestExtend:
    def test_extend_help(self):
        r = CliRunner().invoke(main, ["extend", "--help"])
        assert r.exit_code == 0
        assert "previous" in r.output.lower() or "PREVIOUS_RUN_DIR" in r.output

    def test_extend_dry_run_seeds_initial(self, tmp_path: Path):
        # First do a dry-run on the parent to lay down config/prompts/prompt,
        # then drop a final_output.md by hand to simulate a finished run.
        parent = tmp_path / "parent"
        r = CliRunner().invoke(
            main,
            ["run", "--prompt", "Sketch an outline", "--dry-run", "--output", str(parent)],
        )
        assert r.exit_code == 0, r.output
        (parent / "final_output.md").write_text("FINAL TEXT FROM PREVIOUS RUN\n")

        child = tmp_path / "child"
        r = CliRunner().invoke(
            main,
            ["extend", str(parent), "--dry-run", "--output", str(child)],
        )
        assert r.exit_code == 0, r.output
        # initial_a.md must be seeded from the parent's final_output.md
        assert (child / "initial_a.md").read_text() == "FINAL TEXT FROM PREVIOUS RUN\n"
        # Lineage marker exists
        assert (child / "extends.txt").exists()
        assert str(parent.resolve()) in (child / "extends.txt").read_text()
        # Inherited the parent's prompt
        assert (child / "prompt.md").read_text().startswith("Sketch an outline")
        # Standard run snapshots are present
        assert (child / "config.yaml").exists()
        assert (child / "prompts.yaml").exists()
        state = json.loads((child / "state.json").read_text())
        assert state["status"] == "dry_run"

    def test_extend_overrides_prompt(self, tmp_path: Path):
        parent = tmp_path / "parent"
        CliRunner().invoke(
            main,
            ["run", "--prompt", "Original", "--dry-run", "--output", str(parent)],
        )
        (parent / "final_output.md").write_text("PREV FINAL\n")
        child = tmp_path / "child"
        r = CliRunner().invoke(
            main,
            ["extend", str(parent), "--prompt", "New direction", "--dry-run", "--output", str(child)],
        )
        assert r.exit_code == 0, r.output
        assert (child / "prompt.md").read_text().startswith("New direction")

    def test_extend_requires_final_output(self, tmp_path: Path):
        parent = tmp_path / "parent_incomplete"
        CliRunner().invoke(
            main,
            ["run", "--prompt", "x", "--dry-run", "--output", str(parent)],
        )
        # No final_output.md written.
        child = tmp_path / "child_should_fail"
        r = CliRunner().invoke(
            main,
            ["extend", str(parent), "--dry-run", "--output", str(child)],
        )
        assert r.exit_code != 0
        assert "final_output" in r.output.lower() or "cannot extend" in r.output.lower()


class TestStatus:
    def test_no_state_errors(self, tmp_path: Path):
        r = CliRunner().invoke(main, ["status", str(tmp_path)])
        assert r.exit_code != 0


class TestList:
    def test_empty_root(self, tmp_path: Path):
        r = CliRunner().invoke(main, ["list", "--root", str(tmp_path)])
        assert r.exit_code == 0
        assert "No runs found" in r.output


class TestSignal:
    def test_signal_writes_command(self, tmp_path: Path):
        r = CliRunner().invoke(main, ["signal", str(tmp_path), "stop"])
        assert r.exit_code == 0
        assert (tmp_path / "commands.jsonl").exists()

    def test_inject_requires_payload(self, tmp_path: Path):
        r = CliRunner().invoke(main, ["signal", str(tmp_path), "inject"])
        assert r.exit_code != 0
