"""LLM call wrapper with retry, backoff, and cost tracking.

Uses litellm to support any provider (Anthropic, OpenAI, Google, OpenRouter,
local, etc.) via a single `model` string like "anthropic/claude-sonnet-4-5".
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import litellm

litellm.suppress_debug_info = True


def load_dotenv(path: str | Path) -> None:
    """Populate os.environ from a dotenv file, without overriding existing vars."""
    p = Path(path).expanduser()
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


@dataclass
class CallRecord:
    """Bookkeeping for a single LLM call."""

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class CostTracker:
    """Accumulates tokens and cost across all calls in a run."""

    calls: list[CallRecord] = field(default_factory=list)

    @property
    def total_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls)

    @property
    def total_completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.calls)

    @property
    def num_calls(self) -> int:
        return len(self.calls)

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        self.calls.append(
            CallRecord(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
            )
        )

    def summary(self) -> dict[str, Any]:
        return {
            "num_calls": self.num_calls,
            "total_usd": round(self.total_usd, 6),
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
        }


_RETRYABLE_MARKERS = ("rate", "429", "overloaded", "529", "timeout", "connection")


def _is_retryable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(m in msg for m in _RETRYABLE_MARKERS)


async def call_llm(
    system: str,
    user: str,
    model: str,
    temperature: float,
    max_tokens: int,
    *,
    max_retries: int = 5,
    cost_tracker: CostTracker | None = None,
) -> str:
    """Invoke `model` with one system + one user message. Returns the text response.

    Retries with exponential backoff on rate-limit / overload / transient errors.
    Records token usage and dollar cost to `cost_tracker` if provided.
    """
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if cost_tracker is not None:
                _record(cost_tracker, response, model)
            return response.choices[0].message.content  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 — we genuinely want broad retry
            last_exc = exc
            if not _is_retryable(exc) or attempt == max_retries - 1:
                raise
            wait = min((2**attempt) * 5, 120)
            await asyncio.sleep(wait)
    # Unreachable in practice — the raise above covers final attempts.
    raise RuntimeError(f"call_llm failed after {max_retries} retries") from last_exc


def _record(tracker: CostTracker, response: Any, model: str) -> None:
    """Best-effort token + cost extraction from a litellm response."""
    prompt_tokens = 0
    completion_tokens = 0
    usage = getattr(response, "usage", None)
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0

    cost_usd = 0.0
    try:
        cost_usd = float(litellm.completion_cost(completion_response=response) or 0.0)
    except Exception:  # noqa: BLE001 — missing pricing data shouldn't fail a run
        cost_usd = 0.0

    tracker.record(model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost_usd)
