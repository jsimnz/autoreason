"""Provider-agnostic budget-exhaustion detection + pause/resume in call_llm."""

from __future__ import annotations

from typing import Any

import pytest

from autoreason import llm as llm_mod
from autoreason.llm import _is_budget_exhaustion, call_llm


class TestIsBudgetExhaustion:
    """Heuristic must catch the wording each major provider uses."""

    def test_openrouter_402_payload(self):
        msg = (
            'OpenrouterException - {"error":{"message":"This request requires '
            'more credits, or fewer max_tokens. You requested up to 50000 tokens, '
            'but can only afford 494. To increase, visit ...","code":402}}'
        )
        assert _is_budget_exhaustion(Exception(msg))

    def test_openai_insufficient_quota(self):
        msg = "Error code: 429 - {'error': {'code': 'insufficient_quota', 'message': 'You exceeded your current quota...'}}"
        assert _is_budget_exhaustion(Exception(msg))

    def test_openai_billing_hard_limit(self):
        assert _is_budget_exhaustion(Exception("billing_hard_limit_reached"))

    def test_anthropic_credit_balance(self):
        msg = "Error: Your credit balance is too low to access the API. Please go to Plans & Billing to upgrade or purchase credits."
        assert _is_budget_exhaustion(Exception(msg))

    def test_generic_402(self):
        assert _is_budget_exhaustion(Exception("HTTP 402 Payment Required"))

    def test_quota_exceeded(self):
        assert _is_budget_exhaustion(Exception("quota exceeded"))

    def test_rate_limit_is_not_budget(self):
        # Plain rate-limit text should NOT be treated as budget exhaustion —
        # backoff still helps. (This is the load-bearing distinction.)
        assert not _is_budget_exhaustion(Exception("rate limit reached, retry"))
        assert not _is_budget_exhaustion(Exception("HTTP 429 Too Many Requests"))
        assert not _is_budget_exhaustion(Exception("overloaded_error"))

    def test_unrelated_error_is_not_budget(self):
        assert not _is_budget_exhaustion(Exception("connection reset by peer"))
        assert not _is_budget_exhaustion(Exception("internal server error"))

    def test_case_insensitive(self):
        assert _is_budget_exhaustion(Exception("PAYMENT REQUIRED"))
        assert _is_budget_exhaustion(Exception("Insufficient_Quota"))


# ── pause/resume cycle ───────────────────────────────────────────────────


class _FakeStream:
    """Minimal async iterator standing in for litellm's streaming response.

    Yields one chunk with content and a usage record, so call_llm produces a
    valid return value when the underlying transport "succeeds".
    """

    def __init__(self, text: str = "ok") -> None:
        self._text = text
        self._yielded = False

    def __aiter__(self) -> "_FakeStream":
        return self

    async def __anext__(self) -> Any:
        if self._yielded:
            raise StopAsyncIteration
        self._yielded = True

        class _Delta:
            content = self._text
            reasoning = None
            reasoning_content = None

        class _Choice:
            delta = _Delta()
            finish_reason = "stop"

        class _Usage:
            prompt_tokens = 1
            completion_tokens = 1

        class _Chunk:
            choices = [_Choice()]
            usage = _Usage()

        return _Chunk()


async def test_call_llm_pauses_then_retries(monkeypatch):
    """First call hits a budget error → handler runs → second call succeeds."""
    calls = {"n": 0}

    async def fake_acompletion(**kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise Exception(
                'OpenrouterException - 402 Payment Required: requires more credits'
            )
        return _FakeStream("recovered")

    monkeypatch.setattr(llm_mod.litellm, "acompletion", fake_acompletion)

    handled: list[BaseException] = []

    async def handler(exc: BaseException) -> None:
        handled.append(exc)
        # Simulate "user restored credits, signal received" — return immediately.

    text = await call_llm(
        "sys",
        "user",
        "fake/model",
        temperature=0.0,
        max_tokens=10,
        max_retries=2,
        on_budget_exhausted=handler,
    )

    assert text == "recovered"
    assert calls["n"] == 2  # first call hit budget wall, second succeeded
    assert len(handled) == 1
    assert "402" in str(handled[0]) or "credits" in str(handled[0]).lower()


async def test_call_llm_budget_without_handler_raises(monkeypatch):
    """No handler → original budget error propagates (no silent swallow)."""

    async def fake_acompletion(**kwargs: Any) -> Any:
        raise Exception("Your credit balance is too low")

    monkeypatch.setattr(llm_mod.litellm, "acompletion", fake_acompletion)

    with pytest.raises(Exception) as ei:
        await call_llm(
            "sys", "user", "fake/model", temperature=0.0, max_tokens=10, max_retries=2,
        )
    assert "credit balance" in str(ei.value).lower()


async def test_call_llm_budget_does_not_burn_retries(monkeypatch):
    """Budget errors should NOT consume the exponential-backoff retry budget."""
    calls = {"n": 0}

    async def fake_acompletion(**kwargs: Any) -> Any:
        calls["n"] += 1
        # Always budget-exhausted — handler will keep being called.
        raise Exception("HTTP 402 Payment Required")

    monkeypatch.setattr(llm_mod.litellm, "acompletion", fake_acompletion)

    pauses = {"n": 0}

    async def handler(exc: BaseException) -> None:
        pauses["n"] += 1
        if pauses["n"] >= 3:
            # After 3 simulated pauses, abort by raising.
            raise RuntimeError("user gave up")
        # Otherwise: pretend resume happened, call_llm will retry.

    with pytest.raises(RuntimeError, match="user gave up"):
        await call_llm(
            "sys", "user", "fake/model", temperature=0.0, max_tokens=10, max_retries=2,
            on_budget_exhausted=handler,
        )

    # Each pause pairs with one upstream call attempt → 3 in total.
    # If budget errors had been counted against max_retries, we'd see only 2.
    assert calls["n"] == 3
    assert pauses["n"] == 3


async def test_rate_limit_still_retries_normally(monkeypatch):
    """Rate-limit (non-budget) keeps the existing exponential-backoff path."""
    calls = {"n": 0}

    async def fake_acompletion(**kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] < 2:
            raise Exception("rate limit reached")
        return _FakeStream("ok")

    monkeypatch.setattr(llm_mod.litellm, "acompletion", fake_acompletion)
    # Skip the real backoff sleep so the test is fast.
    monkeypatch.setattr(llm_mod.asyncio, "sleep", _instant_sleep)

    handler_called = {"n": 0}

    async def handler(exc: BaseException) -> None:
        handler_called["n"] += 1

    text = await call_llm(
        "sys", "user", "fake/model", temperature=0.0, max_tokens=10, max_retries=3,
        on_budget_exhausted=handler,
    )
    assert text == "ok"
    assert calls["n"] == 2
    # Budget handler must NOT fire on a rate-limit error.
    assert handler_called["n"] == 0


async def _instant_sleep(_seconds: float) -> None:
    # Patched in place of asyncio.sleep — avoid recursing into the real one.
    return None
