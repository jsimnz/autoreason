"""Prompts: default load, override merge, rendering."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from autoreason.prompts import ROLES, Prompts


class TestPrompts:
    def test_defaults_load(self):
        p = Prompts.load_defaults()
        for role in ROLES:
            rp = getattr(p, role)
            assert rp.system.strip(), f"{role}.system is empty"
            assert rp.user.strip(), f"{role}.user is empty"

    def test_render_author_a(self):
        p = Prompts.load_defaults()
        system, user = p.render("author_a", task_prompt="do X")
        assert "do X" in user
        assert "senior consultant" in system

    def test_render_critic_with_injection(self):
        p = Prompts.load_defaults()
        _, user = p.render("critic", version_a="draft text", task_prompt="", injection="")
        assert "draft text" in user
        # With injection populated
        _, user2 = p.render(
            "critic", version_a="draft", task_prompt="", injection="\n\nExtra guidance: foo"
        )
        assert "Extra guidance: foo" in user2

    def test_unknown_role_rejects(self):
        p = Prompts.load_defaults()
        with pytest.raises(ValueError):
            p.render("marketer", task_prompt="x")  # type: ignore[arg-type]

    def test_override_merge_single_role(self, tmp_path: Path):
        override = tmp_path / "custom.yaml"
        override.write_text(yaml.safe_dump({"critic": {"system": "Blunt critic only.", "user": "Problems with: {version_a}"}}))
        p = Prompts.load(override_path=override)
        assert p.critic.system == "Blunt critic only."
        # Other roles still default
        defaults = Prompts.load_defaults()
        assert p.author_a.system == defaults.author_a.system

    def test_override_partial_role(self, tmp_path: Path):
        """If override supplies only 'system', 'user' keeps the default."""
        override = tmp_path / "p.yaml"
        override.write_text(yaml.safe_dump({"critic": {"system": "New persona"}}))
        p = Prompts.load(override_path=override)
        defaults = Prompts.load_defaults()
        assert p.critic.system == "New persona"
        assert p.critic.user == defaults.critic.user

    def test_override_unknown_role_rejects(self, tmp_path: Path):
        override = tmp_path / "bad.yaml"
        override.write_text(yaml.safe_dump({"author_c": {"system": "x", "user": "y"}}))
        with pytest.raises(ValueError):
            Prompts.load(override_path=override)

    def test_to_yaml_roundtrip(self, tmp_path: Path):
        p1 = Prompts.load_defaults()
        out = tmp_path / "out.yaml"
        out.write_text(p1.to_yaml())
        p2 = Prompts.load(override_path=out)
        assert p2.critic.system == p1.critic.system
        assert p2.judge.user == p1.judge.user
