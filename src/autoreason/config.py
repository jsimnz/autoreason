"""Typed configuration for an AutoReason run.

Precedence (highest wins): CLI flags → user YAML config → defaults baked here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


class Config(BaseModel):
    """Resolved configuration for a single run."""

    model_config = {"extra": "forbid", "frozen": False}

    author_model: str = Field(
        default="anthropic/claude-sonnet-4-5",
        description="Model used for author_a, author_b, and synthesizer roles.",
    )
    judge_model: str | None = Field(
        default=None,
        description="Model used for judges. Falls back to author_model when None.",
    )
    author_temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    judge_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    num_judges: int = Field(default=3, ge=1)
    max_passes: int = Field(default=30, ge=1)
    convergence_threshold: int = Field(
        default=2,
        ge=1,
        description="Consecutive A wins required to declare convergence.",
    )
    max_retries: int = Field(default=5, ge=1, description="Retries per LLM call on rate/overload errors.")

    @model_validator(mode="after")
    def _default_judge_model(self) -> "Config":
        if self.judge_model is None:
            self.judge_model = self.author_model
        return self

    @classmethod
    def load(
        cls,
        config_path: str | Path | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> "Config":
        """Build a Config by layering: defaults → file → overrides."""
        data: dict[str, Any] = {}
        if config_path is not None:
            loaded = yaml.safe_load(Path(config_path).read_text()) or {}
            if not isinstance(loaded, dict):
                raise ValueError(f"Config file {config_path} must contain a YAML mapping.")
            data.update(loaded)
        if overrides:
            data.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**data)

    def to_yaml(self) -> str:
        """Serialize to YAML for reproducibility artifacts."""
        return yaml.safe_dump(self.model_dump(), sort_keys=True)
