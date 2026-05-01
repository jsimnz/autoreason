"""Prompt templates: defaults shipped in the package, overridable by user YAML."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

ROLES = ("author_a", "critic", "author_b", "synthesizer", "judge")


class RolePrompts(BaseModel):
    """System persona + user template for one role."""

    model_config = {"extra": "forbid"}

    system: str
    user: str


class Prompts(BaseModel):
    """Full prompt set for all roles."""

    model_config = {"extra": "forbid"}

    author_a: RolePrompts
    critic: RolePrompts
    author_b: RolePrompts
    synthesizer: RolePrompts
    judge: RolePrompts

    @classmethod
    def load_defaults(cls) -> "Prompts":
        """Load the default prompts shipped with the package."""
        text = files("autoreason").joinpath("default_prompts.yaml").read_text()
        return cls._from_yaml_text(text)

    @classmethod
    def load(cls, override_path: str | Path | None = None) -> "Prompts":
        """Load defaults, then merge role-level overrides from a user YAML file."""
        defaults = cls.load_defaults()
        if override_path is None:
            return defaults
        override = yaml.safe_load(Path(override_path).read_text()) or {}
        if not isinstance(override, dict):
            raise ValueError(f"Prompts file {override_path} must contain a YAML mapping.")
        merged = defaults.model_dump()
        for role, role_data in override.items():
            if role not in ROLES:
                raise ValueError(
                    f"Unknown role '{role}' in {override_path}. Known roles: {', '.join(ROLES)}"
                )
            if not isinstance(role_data, dict):
                raise ValueError(f"Role '{role}' must be a mapping with 'system' and/or 'user'.")
            merged[role].update(role_data)
        return cls(**merged)

    @classmethod
    def _from_yaml_text(cls, text: str) -> "Prompts":
        data = yaml.safe_load(text) or {}
        missing = [r for r in ROLES if r not in data]
        if missing:
            raise ValueError(f"Prompts YAML is missing required roles: {', '.join(missing)}")
        return cls(**data)

    def to_yaml(self) -> str:
        """Serialize to YAML for reproducibility artifacts."""
        return yaml.safe_dump(self.model_dump(), sort_keys=False, default_style="|")

    def render(self, role: str, **kwargs: Any) -> tuple[str, str]:
        """Return (system, user) for the given role, with str.format substitution on user."""
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'. Known: {', '.join(ROLES)}")
        rp: RolePrompts = getattr(self, role)
        return rp.system, rp.user.format(**kwargs)
