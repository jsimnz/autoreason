Here are the real problems I found:

---

**1. The staleness threshold math is still wrong for its stated purpose.**

The proposal says: "We allow for two consecutive failed cycles before declaring the publisher unhealthy. Two cycles = 2 × 100s = 200s. We use 150s as the staleness threshold."

150 seconds is less than one worst-case cycle (100s) plus one full publish interval (60s) = 160s. A single slow-but-succeeding cycle can produce a false positive. The prose says "two consecutive failed cycles" but the number doesn't support that claim. The original finding was about the formula being wrong; the formula is still wrong, just differently.

---

**2. The health file is written by `publish_once`, but `publish_once` is cut off mid-function.**

The document ends mid-code block inside `_put_metrics_with_retry`. The health file write is never shown. The healthcheck reads the health file. Whether the health file is written before or after metrics are confirmed delivered — and whether a partial success (Redis read succeeded, CloudWatch write failed) updates the health file — is unspecified. This is a real operational ambiguity, not a documentation gap: the healthcheck behavior depends on it.

---

**3. The circuit breaker's Redis dependency is treated as a fallback strength, but its failure mode is unaddressed.**

The proposal repeatedly states "the circuit breaker reads Redis directly" as a reason the publisher being unhealthy doesn't affect cap enforcement. But if Redis is unavailable — which is exactly when `socket_timeout` fires and `publish_once` fails — the circuit breaker's ability to read Redis is also compromised. The document never states what the circuit breaker does when Redis is unreachable. This is the highest-stakes failure mode (attack + Redis outage simultaneously) and it has no specified behavior.

---

**4. The conditional write protecting the total constraint is described as atomic, but the Lambda failure path breaks that guarantee in practice.**

Section 2.1 states: "There is no window between the check and the write in which a concurrent AUTH cap increase can invalidate the check." This is true for a single DynamoDB conditional write. But the Lambda reads the current AUTH and SOCIAL values, computes the new total, then issues the conditional write. The condition expression must encode the total constraint — but DynamoDB conditional writes can only condition on the item being written, not on a value in a different item. If AUTH and SOCIAL caps are stored as separate DynamoDB items (which the routing table implies), the "atomic" guarantee does not exist. No table schema is shown, so this cannot be verified, but the claim of atomicity is almost certainly false as described.

---

**5. The AUTH SMS fallback (Section 2.6) is referenced eight times but never shown.**

The executive summary says finding 8 is resolved in Section 2.6. Section 2.6 is referenced throughout the document. Section 2.6 does not appear in the document. This is not a truncation artifact — the document ends inside Section 2.3. Sections 2.4, 2.5, 2.6, 2.7, 2.8, and 2.9 are all missing. Five of the eight claimed findings are resolved in sections that don't exist.

---

**6. The `_CAP_SENTINEL = -1` value does not accomplish what the comment claims.**

The comment states the sentinel is "chosen to be clearly distinguishable from any real cap value and to cause the CapReadHealthy alarm to fire without causing the consumption alarm to fire spuriously." But the sentinel is emitted as a CloudWatch metric value. A metric value of -1 for cap will cause consumption-vs-cap ratio alarms to produce undefined or negative results depending on how those alarms are expressed. The document does not show the consumption alarm's threshold expression, so whether -1 causes spurious firing is unverifiable — but the claim in the comment is not supported by any analysis.

---

**7. One engineer (E1) owns all three AUTH cap review checkpoints with no backup or escalation path.**

The review schedule names E1 as sole owner at month 1, month 3, and month 6. No alternate owner, no escalation if E1 is unavailable, no indication of what happens if the review is missed. For a 6-month engagement with 4 engineers, single-person ownership of a manual safety review with no fallback is a real process risk, not a staffing preference.

---

**8. The Twilio log query used to establish the AUTH baseline is run once, pre-launch, against pre-launch data.**

The proposal treats pre-launch Twilio data as the baseline for a post-launch system. The pre-launch system presumably has different traffic — the notification system being designed doesn't exist yet. The query measures the existing auth service in isolation. Once the new notification system is live and driving more user engagement, AUTH SMS volume may behave differently. The baseline is established before the system that changes the baseline is deployed.