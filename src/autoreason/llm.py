"""LLM call wrapper with retry, backoff, and cost tracking.

Uses litellm to support any provider (Anthropic, OpenAI, Google, OpenRouter,
local, etc.) via a single `model` string like "anthropic/claude-sonnet-4-5".
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import litellm

# Async callback invoked when a budget/quota/credit-exhaustion error is detected.
# It must block until the user has (presumably) restored their budget and
# wants the failing call to be retried. Raising from inside the handler aborts
# the call (e.g. KeyboardInterrupt → propagated up through `call_llm`).
BudgetExhaustedHandler = Callable[[BaseException], Awaitable[None]]

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
    """Accumulates tokens across all calls in a run; dollar cost is opt-in.

    By default, only token counts are recorded. Set `track_cost=True` to also
    compute dollar cost per call via `litellm.completion_cost`. Cost tracking
    requires litellm to have pricing data for the model; when missing, cost is
    silently 0.0.
    """

    calls: list[CallRecord] = field(default_factory=list)
    track_cost: bool = False
    # Live counters updated mid-stream by call_llm; folded into a CallRecord and reset on finalize.
    in_flight_prompt_tokens: int = 0
    in_flight_completion_tokens: int = 0

    @property
    def total_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls) + self.in_flight_prompt_tokens

    @property
    def total_completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.calls) + self.in_flight_completion_tokens

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
            "cost_tracked": self.track_cost,
        }


def _format_tokens(n: int) -> str:
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}k"
    return f"{n / 1_000_000:.2f}M"


def format_spend(
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    cost_tracked: bool,
) -> str:
    """Compact one-line spend summary. Uses dollars if tracked, tokens otherwise."""
    total_tok = prompt_tokens + completion_tokens
    tok_str = (
        f"{_format_tokens(total_tok)} tok "
        f"({_format_tokens(prompt_tokens)} in / {_format_tokens(completion_tokens)} out)"
    )
    if cost_tracked:
        return f"${cost_usd:.4f}  {tok_str}"
    return tok_str


_RETRYABLE_MARKERS = ("rate", "429", "overloaded", "529", "timeout", "connection")

# Markers that indicate a *budget/quota/credit* problem rather than a transient
# rate-limit. Hitting any of these means waiting won't help — only the user
# topping up credits (or a billing window resetting) resolves it. We pause
# instead of burning retry attempts.
#
# Curated from the wild — extend as new providers surface new wording.
_BUDGET_MARKERS = (
    # OpenRouter (402)
    "more credits",
    "fewer max_tokens",
    "afford",
    "create a key with a higher",
    "daily limit",
    # OpenAI
    "insufficient_quota",
    "exceeded your current quota",
    "billing_hard_limit_reached",
    "billing_not_active",
    # Anthropic
    "credit balance is too low",
    "credit balance",
    # Generic / shared
    "402",
    "payment required",
    "quota exceeded",
    "quota_exceeded",
    "out of credits",
)


def _is_budget_exhaustion(exc: BaseException) -> bool:
    """Heuristic: does this exception look like a billing/quota wall?

    Provider-agnostic — operates on the stringified error. The ``402`` marker
    is the most reliable cross-provider signal; the keyword list catches
    providers that surface 4xx/429 with billing-flavored messages instead.
    """
    msg = str(exc).lower()
    return any(m in msg for m in _BUDGET_MARKERS)


def _is_retryable(exc: BaseException) -> bool:
    # Budget exhaustion looks like 429/rate to some classifiers but is NOT
    # something exponential backoff helps with — exclude it explicitly so the
    # retry loop hands off to the pause handler instead of burning attempts.
    if _is_budget_exhaustion(exc):
        return False
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
    on_budget_exhausted: BudgetExhaustedHandler | None = None,
) -> str:
    """Invoke `model` with one system + one user message. Returns the text response.

    Retries with exponential backoff on rate-limit / overload / transient errors.
    Records token usage and dollar cost to `cost_tracker` if provided.

    If a budget/quota/credit-exhaustion error is detected (any provider), the
    optional `on_budget_exhausted` handler is awaited — it should block until
    the user has restored their budget — and then the call is retried in full.
    Without a handler, the original exception is re-raised so the caller can
    surface or persist it.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    while True:  # outer: re-enter after a budget pause; otherwise we return / raise
        last_exc: BaseException | None = None
        for attempt in range(max_retries):
            if cost_tracker is not None:
                cost_tracker.in_flight_prompt_tokens = 0
                cost_tracker.in_flight_completion_tokens = 0
            try:
                stream = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    stream_options={"include_usage": True},
                )
                text_parts: list[str] = []
                reasoning_parts: list[str] = []
                finish_reason: str = "unknown"
                chunks: list[Any] = []
                async for chunk in stream:
                    chunks.append(chunk)
                    usage = getattr(chunk, "usage", None)
                    if usage is not None and cost_tracker is not None:
                        cost_tracker.in_flight_prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue
                    ch0 = choices[0]
                    fr = getattr(ch0, "finish_reason", None)
                    if fr:
                        finish_reason = fr
                    delta = getattr(ch0, "delta", None)
                    if delta is None:
                        continue
                    dc = getattr(delta, "content", None)
                    if dc:
                        text_parts.append(dc)
                        if cost_tracker is not None:
                            cost_tracker.in_flight_completion_tokens += 1
                    rc = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                    if rc:
                        reasoning_parts.append(rc)
                        if cost_tracker is not None:
                            cost_tracker.in_flight_completion_tokens += 1

                text = "".join(text_parts) or "".join(reasoning_parts)

                if cost_tracker is not None:
                    final_response = _rebuild_response(chunks, messages)
                    if final_response is not None:
                        _record(cost_tracker, final_response, model)
                    else:
                        cost_tracker.record(
                            model=model,
                            prompt_tokens=cost_tracker.in_flight_prompt_tokens,
                            completion_tokens=cost_tracker.in_flight_completion_tokens,
                            cost_usd=0.0,
                        )
                    cost_tracker.in_flight_prompt_tokens = 0
                    cost_tracker.in_flight_completion_tokens = 0

                if not text:
                    raise RuntimeError(
                        f"LLM returned empty content (model={model}, finish_reason={finish_reason}). "
                        f"For reasoning models, this usually means max_tokens ({max_tokens}) "
                        f"was too low — reasoning tokens consumed the full budget. "
                        f"Try raising max_tokens or switching to a non-reasoning variant."
                    )
                return text
            except Exception as exc:  # noqa: BLE001 — we genuinely want broad retry
                last_exc = exc
                if cost_tracker is not None:
                    cost_tracker.in_flight_prompt_tokens = 0
                    cost_tracker.in_flight_completion_tokens = 0
                if _is_budget_exhaustion(exc):
                    # Stop the inner retry loop; the budget handler (if any)
                    # decides whether we restart the call or re-raise.
                    break
                if not _is_retryable(exc) or attempt == max_retries - 1:
                    raise
                wait = min((2**attempt) * 5, 120)
                await asyncio.sleep(wait)

        # Inner loop only falls through here on a budget-exhaustion break.
        if last_exc is not None and _is_budget_exhaustion(last_exc):
            if on_budget_exhausted is None:
                raise last_exc
            # Handler blocks until the user signals resume. If it raises
            # (e.g. KeyboardInterrupt during pause), let it propagate.
            await on_budget_exhausted(last_exc)
            # Retry the whole call. We do not increment any retry counter —
            # the failing attempt was due to billing, not unreliability.
            continue

        # Defensive fallback — every other branch above already returns or raises.
        raise RuntimeError(f"call_llm failed after {max_retries} retries") from last_exc


def _rebuild_response(chunks: list[Any], messages: list[dict[str, Any]]) -> Any | None:
    """Reassemble streamed chunks into a non-streaming-shaped response.

    Used so `_record` / `litellm.completion_cost` can operate unchanged. Returns
    None if the builder isn't available or fails — callers fall back to the
    in-flight counters.
    """
    builder = getattr(litellm, "stream_chunk_builder", None)
    if builder is None:
        return None
    try:
        return builder(chunks, messages=messages)
    except Exception:  # noqa: BLE001 — best-effort, fall back to raw counts
        return None


def _record(tracker: CostTracker, response: Any, model: str) -> None:
    """Best-effort token + cost extraction from a litellm response."""
    prompt_tokens = 0
    completion_tokens = 0
    usage = getattr(response, "usage", None)
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0

    cost_usd = 0.0
    if tracker.track_cost:
        try:
            cost_usd = float(litellm.completion_cost(completion_response=response) or 0.0)
        except Exception:  # noqa: BLE001 — missing pricing data shouldn't fail a run
            cost_usd = 0.0

    tracker.record(model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost_usd)
