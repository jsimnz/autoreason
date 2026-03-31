## Real Problems with This Proposal

### 1. The 8-Week Baseline Period Is Structurally Dangerous

The document acknowledges that 140,000 opt-outs in a week represents "permanent damage" but then accepts this as the interim backstop. Eight weeks at 5 push notifications/day/user means users receive 280 push notifications before the statistical alerting system is even armed. If the notification types or frequencies are wrong, the system will have already destroyed a significant portion of the push-addressable audience before the sophisticated alerting kicks in. The "leading indicator by type" mitigation requires knowing which types are problematic — but you don't have that baseline either. Both the aggregate and per-type thresholds are blind during the same window.

### 2. The 3× Per-Type Opt-Out Rule Is Undefined and Unworkable at Launch

"If any notification type drives opt-outs at more than 3× the rate of other types" — the rate of *what other types*? If you launch with three notification types and one of them is rare, you have no stable denominator. If all types have similar opt-out rates, no alert fires even if all rates are catastrophically high. This metric requires a distribution of notification types with sufficient volume per type to be statistically meaningful, but that condition isn't specified or verified anywhere.

### 3. The Coverage Verification Schedule Has a Hidden Dependency Loop

E4 must complete solo on-call in month 1 to verify coverage for the in-app channel. But E4's solo on-call competence depends on runbooks that E1 and E3 write. The document states runbooks must be complete enough that the partner can execute every step without asking — but runbook completeness isn't verified until the solo on-call simulation, which is itself the coverage gate for launch. If the runbooks are inadequate, the month 1 milestone slips, which cascades into push launch slipping in month 2. There's no earlier checkpoint on runbook quality.

### 4. The 5M Queue Entry "Buffer" Number Is Invented

The document says 5M entries is a "47× buffer over normal in-flight volume" — but it derives normal in-flight volume (106K entries) from a 60-second P1 SLA at peak throughput. That calculation assumes workers are keeping pace. In the backlog scenario the buffer is meant to address, workers are *not* keeping pace, so the in-flight volume grows indefinitely until workers catch up or load drops. The 5M figure has no derivation from actual failure scenarios — it's an arbitrary large number dressed up with a multiplier.

### 5. The PostgreSQL Partitioning Scheme Is Fixed but the Access Patterns Aren't Analyzed

The delivery log and in-app store are both partitioned by `user_id % 64`. The document doesn't analyze whether the primary query patterns (fetch notifications for a user, mark as read, preference lookups by user) benefit from this scheme or whether 64 partitions is appropriate for the write volume. At 51M notifications/day, the delivery log alone is ~590 writes/second sustained, ~1,770/second at peak. Whether 64 partitions handles this without hot spots depends on the user_id distribution and query patterns — neither is examined.

### 6. The WebSocket Pub/Sub Memory Estimate Is Wrong

The document allocates 100 bytes per active WebSocket session for Redis pub/sub channels, totaling 300MB for 3M sessions. Redis pub/sub channels don't work this way — the memory cost is in the subscriber list and message buffer per channel, not a flat per-channel overhead. If each of 3M connected users has their own channel (the natural design for per-user delivery), and messages are in flight, the memory profile is dominated by message buffering behavior, not channel metadata. The 100 bytes/session figure has no basis in Redis's actual pub/sub memory model.

### 7. The 4× Stress Test Uses a Mocked FCM Endpoint, But the Stated Risk Is FCM Quota

Section 1.3 says FCM quota analysis shows "minimal headroom at 3× during FCM degradation scenarios" — and the proposed mitigation for this risk is a stress test that mocks FCM out entirely. The mock test characterizes *your* system's backpressure behavior, not the interaction between your system and FCM under quota pressure. The actual risk (FCM quota exhaustion during a peak) is untested by design.

### 8. The SMS Allowlist Governance Process Creates a Bottleneck with No Escalation Path

Two-engineer sign-off to modify the SMS allowlist is described as a control, but there's no escalation path if the two engineers with authority are unavailable and an urgent SMS type needs to be added (e.g., a new auth flow required by an external dependency). With 4 engineers total, "two-engineer sign-off" means 50% of the team must be available and aligned. The governance section is referenced but the document is cut off before it's shown — it's unclear if this problem is addressed.

### 9. The Architectural Review Trigger for P1 SLA Misses Is Set at 1%, Which Is Already a Failure

A 1% P1 SLA miss rate means roughly 350,000 notifications/day missing their 60-second delivery window at peak volume. Framing this as a "review trigger" rather than an incident threshold normalizes a significant user-facing failure. The document elsewhere treats SLA misses as something to prevent, but the trigger is set at a level where the failure is already occurring at scale.

### 10. Bus Factor Mitigation Doesn't Account for Knowledge Accumulation Over Time

The document acknowledges that if two engineers are simultaneously unavailable there's a coverage gap, and says runbooks are written for "a competent backend engineer unfamiliar with the system." But over 6 months, the system accumulates undocumented operational knowledge — quirks, learned behaviors, non-obvious failure modes — faster than runbooks are updated. The runbook completeness standard is defined at channel launch but there's no mechanism to keep runbooks current as the system evolves. By month 6, the month 1 runbooks may be materially incomplete.