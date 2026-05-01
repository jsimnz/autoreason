"""Config precedence: flags > file > defaults."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from autoreason.config import Config


class TestConfig:
    def test_defaults(self):
        c = Config()
        assert c.num_judges == 3
        assert c.max_passes == 30
        assert c.convergence_threshold == 2
        assert c.author_temperature == 0.8
        assert c.judge_temperature == 0.3
        assert c.max_tokens == 4096
        # judge_model falls back to author_model
        assert c.judge_model == c.author_model

    def test_judge_model_explicit(self):
        c = Config(author_model="a/x", judge_model="b/y")
        assert c.judge_model == "b/y"

    def test_overrides_none_ignored(self):
        c = Config.load(overrides={"num_judges": None, "max_passes": 10})
        assert c.num_judges == 3  # None ignored, default used
        assert c.max_passes == 10

    def test_file_merge(self, tmp_path: Path):
        p = tmp_path / "c.yaml"
        p.write_text(yaml.safe_dump({"num_judges": 5, "max_passes": 20}))
        c = Config.load(config_path=p)
        assert c.num_judges == 5
        assert c.max_passes == 20
        assert c.convergence_threshold == 2  # still default

    def test_overrides_beat_file(self, tmp_path: Path):
        p = tmp_path / "c.yaml"
        p.write_text(yaml.safe_dump({"num_judges": 5, "max_passes": 20}))
        c = Config.load(config_path=p, overrides={"num_judges": 7})
        assert c.num_judges == 7  # override wins
        assert c.max_passes == 20  # from file

    def test_unknown_field_rejected(self):
        with pytest.raises(Exception):
            Config(not_a_field=42)  # type: ignore[call-arg]

    def test_validation_ranges(self):
        with pytest.raises(Exception):
            Config(num_judges=0)  # ge=1
        with pytest.raises(Exception):
            Config(author_temperature=3.0)  # le=2.0

    def test_to_yaml_roundtrip(self, tmp_path: Path):
        c1 = Config(num_judges=7, max_passes=12)
        y = c1.to_yaml()
        p = tmp_path / "out.yaml"
        p.write_text(y)
        c2 = Config.load(config_path=p)
        assert c2.num_judges == 7
        assert c2.max_passes == 12

    def test_file_must_be_mapping(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text("- a\n- b\n")
        with pytest.raises(ValueError):
            Config.load(config_path=p)
