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
        description=(
            "Default author-side model. Used for author_a, critic, author_b, and "
            "synthesizer when their per-role model is not set."
        ),
    )
    author_a_model: str | None = Field(
        default=None,
        description="Per-role override for the initial author. Falls back to author_model.",
    )
    critic_model: str | None = Field(
        default=None,
        description="Per-role override for the critic. Falls back to author_model.",
    )
    author_b_model: str | None = Field(
        default=None,
        description="Per-role override for the adversarial author_b. Falls back to author_model.",
    )
    synthesizer_model: str | None = Field(
        default=None,
        description="Per-role override for the synthesizer. Falls back to author_model.",
    )
    judge_model: str | None = Field(
        default=None,
        description="Model used for judges. Falls back to author_model when None.",
    )
    judge_models: list[str] | None = Field(
        default=None,
        description=(
            "Optional heterogeneous judge panel. If num_judges is left at its default, "
            "len(judge_models) defines the panel size. If num_judges is set explicitly, "
            "it wins and judge_models is round-robined across the panel (e.g. 4 judges "
            "from 2 models → A,B,A,B). num_judges < len(judge_models) is rejected."
        ),
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
    track_cost: bool = Field(
        default=False,
        description="Opt in to dollar-cost tracking via litellm.completion_cost. "
        "When False (default), only token counts are recorded.",
    )

    @model_validator(mode="after")
    def _default_judge_model(self) -> "Config":
        if self.judge_models:
            num_judges_explicit = "num_judges" in self.model_fields_set
            if len(self.judge_models) > 1 and not num_judges_explicit:
                # Ergonomic case: user listed N models, panel size follows.
                self.num_judges = len(self.judge_models)
            elif self.num_judges < len(self.judge_models):
                raise ValueError(
                    f"num_judges ({self.num_judges}) is smaller than the number of "
                    f"judge_models provided ({len(self.judge_models)}); "
                    f"raise --judges or remove models."
                )
            if self.judge_model is None:
                self.judge_model = self.judge_models[0]
        if self.judge_model is None:
            self.judge_model = self.author_model
        return self

    def model_for_role(self, role: str) -> str:
        """Resolve the model for an author-side role, falling back to author_model.

        Recognized roles: 'author_a', 'critic', 'author_b', 'synthesizer'.
        Unknown roles also fall back to author_model so callers don't have to
        special-case future additions.
        """
        per_role = {
            "author_a": self.author_a_model,
            "critic": self.critic_model,
            "author_b": self.author_b_model,
            "synthesizer": self.synthesizer_model,
        }.get(role)
        return per_role or self.author_model

    def model_for_judge(self, i: int) -> str:
        """Resolve the model string for the i-th judge (0-indexed).

        If judge_models is shorter than num_judges, the list is round-robined:
        judge i uses judge_models[i % len(judge_models)].
        """
        if self.judge_models:
            return self.judge_models[i % len(self.judge_models)]
        return self.judge_model or self.author_model

    @property
    def judge_panel_is_heterogeneous(self) -> bool:
        return bool(self.judge_models) and len(set(self.judge_models)) > 1

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
