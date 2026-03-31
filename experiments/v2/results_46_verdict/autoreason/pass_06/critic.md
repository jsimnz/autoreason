Here are the real problems I found:

## Structural / Architectural Problems

**The "single priority queue with channel fanout" is undersized for the actual problem.** Push, email, SMS, and in-app have fundamentally different delivery semantics, retry behaviors, rate limits, and failure modes. A single queue means a FCM backpressure event (which the document explicitly worries about) can delay email digests and in-app notifications. The document acknowledges per-channel queues as an alternative but dismisses them without actually analyzing this failure mode.

**The P0 SMS fallback for push (Section 5.3) is referenced but never defined in the visible document.** The document references "P0 notifications route to SMS fallback" as a success criterion in Test 2, but Section 5.3 isn't shown. This is either incomplete or the fallback logic is being relied upon without being specified. Given the SMS cost controls described earlier, routing push failures to SMS could silently violate the allowlist governance model.

**Redis Sentinel is the wrong HA choice at this scale.** At 51M notifications/day with a 3× peak multiplier, a Sentinel failover takes 15–30 seconds during which the primary queue is unavailable. The document treats this as an operational footnote rather than a design problem. For a system where P0 SLA is 10 seconds, a 30-second queue outage is a direct SLA violation with no mitigation described.

**The preference cache TTL of 5 minutes creates a correctness window the document ignores.** A user who disables push notifications could receive up to 5 minutes of notifications after opting out. For a system with explicit opt-out protection as a stated priority, this is a direct contradiction that goes unaddressed.

## Scale and Math Problems

**The peak throughput calculation is wrong.** 51M × 3 / 86,400 = 1,770/sec is average-times-peak-multiplier, not actual peak. If traffic is concentrated in morning/evening windows (stated assumption), the 3× multiplier applies to the peak window, not the daily average distributed evenly. The actual peak could be significantly higher depending on window duration.

**The 3× safety margin on Redis memory is applied inconsistently.** The document estimates 4.3GB and applies a 3× safety margin to get 12.9GB. But the preference cache entry (2GB) already represents all 10M MAU — there's no growth scenario for that number. Applying a uniform 3× multiplier to a fixed-size cache conflates different uncertainty types and overstates confidence in the headroom calculation.

**The WebSocket pub/sub memory estimate (1.5GB) has no derivation shown.** Section 2.1b is referenced but the document is cut off. This is the second-largest line item in the Redis budget and it's entirely unsubstantiated in the visible document.

## Process and Governance Problems

**The two-engineer sign-off for SMS allowlist changes has no defined escalation SLA.** The document acknowledges "urgent additions" require governance but defers the escalation path to Section 3.3. For a security-critical channel (auth, 2FA), an undefined escalation path during an incident is a real operational risk, not a documentation gap.

**Gate 3 "solo on-call for the first week" conflicts with E4's month 1 workload description.** E4 is doing solo on-call for queue/in-app while simultaneously doing "design and scaffolding" for email/SMS. The document tries to scope E4's on-call narrowly, but a solo on-call engineer responding to incidents cannot simultaneously be doing focused design work. The time conflict is papered over, not resolved.

**The runbook maintenance process has no enforcement mechanism for the monthly review.** "Skipped reviews are flagged in the weekly team sync" is social pressure, not a process control. The incident-closure gate is enforceable; the monthly review is not. With 4 engineers under delivery pressure, the monthly review will be the first thing skipped.

**Coverage partner verification (Gates 1–3) for month 2 is ambiguous.** The milestone table says "E2 Gates 1–3 for email; E4 extends push coverage through Gates 1–3." E4 is already the coverage partner for E2 (push). It's unclear whether E2 is now becoming E4's coverage partner for email, creating a circular dependency, or whether a third engineer is involved. The table doesn't resolve this.

## Testing Problems

**Test 2's success criteria are internally contradictory.** The document says Test 2 "does not pass or fail on delivery speed" but lists "P0 notifications route to SMS fallback" as a success criterion. Routing to SMS fallback is a binary correctness requirement, not a characterization. The document can't simultaneously claim the test has no pass/fail criteria and list specific required behaviors.

**The 8-week baseline requirement for statistical alerting means the system operates without drift detection for two months.** The document frames absolute limits as sufficient protection during this period, but the absolute limits are per-user caps, not anomaly detection. A gradual increase in opt-outs across many users that stays below per-user limits but indicates content quality problems would be invisible for 8 weeks.

**The FCM staging quota constraint in Test 2 is self-defeating.** The document criticizes mocking FCM in stress tests as invalidating the test's purpose, then immediately constrains FCM to 60% quota in a staging project — which is also not production FCM behavior. The difference between a mock and an artificially constrained staging project is smaller than the document implies.