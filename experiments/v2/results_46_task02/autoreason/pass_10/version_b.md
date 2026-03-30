# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels, derived from a baseline of 17 notifications/DAU/day. That figure is the single most consequential assumption in this document; Section 1.4 specifies what changes at 8/day and 35/day, and defines a hard re-sizing trigger.

**Revisions from the previous version, by problem number:**

| Problem | Issue | Resolution |
|---------|-------|------------|
| 1 | Stress case multiplier unjustified | 2× derived from historical social platform data; 3× and 5× cases modeled with explicit consequences |
| 2 | P0 APNs connection-level failover unaddressed | P0 now has 2 APNs connections, not 1; worker and connection failover specified separately |
| 3 | Idempotency TTL asserted without bounding | Retry schedule defined; maximum retry interval bounded; TTL derived from that bound |
| 4 | FCM treated as non-binding without iOS/Android split | Split specified (60/40 iOS/Android assumed); FCM path scrutinized on same terms as APNs |
| 5 | Receipt consistency window has audit implications | Audit log path specified separately from performance receipt path |
| 6 | Tertiary alerting path named but not specified | PagerDuty via Twilio SMS specified as tertiary path with explicit trigger conditions |
| 7 | Aurora write ceiling ignores read load | Read/write IOPS contention modeled; read replica routing specified |
| 8 | SMS spend cap described but mechanism unspecified | Redis counter with Lua atomic decrement specified; Twilio hard cap as secondary enforcement |
| 9 | P1 SLA table cut off | Table completed with full operational response matrix |
| 10 | 17 notifications/DAU drives everything; not bounded | Sensitivity analysis in Section 1.4; re-sizing triggers defined |

**Core design principle, unchanged:** Conservatism belongs in the delivery floor, not the inbound ceiling. The stress case is now derived, not asserted.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis | Validation path |
|--------|----------|-------|-----------------|
| MAU | 10M | Given | — |
| DAU | 3M | 30% DAU/MAU; social app benchmark | Validate against analytics in month 1 |
| Notifications/DAU/day | 17 average | Engaged-user benchmark; see Section 1.4 for sensitivity | Validate against product analytics before provisioning final instance sizes |
| **Total notifications/day** | **~50M** | Planning baseline | — |
| iOS/Android split | 60% iOS / 40% Android | Industry benchmark for social apps; see Section 1.4 | Validate against registration data in month 1 |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 | Monitor at launch |
| Viral event inbound (derived ceiling) | ~1,100/sec | Derived in Section 1.2 | Validate against viral event logs at launch |
| Viral event inbound (stress case — 2×) | ~2,200/sec | Justified in Section 1.2 | — |
| Viral event inbound (stress case — 3×) | ~3,300/sec | Modeled for queue depth planning | — |
| Delivery throughput (planning floor) | ~1,200/sec | Conservative; derived in Section 1.2 | Load test in month 2 |
| Delivery throughput (expected) | ~1,400/sec | Derived from worker pool and connection count | Load test in month 2 |
| Push — iOS (APNs) | ~21M/day (42%) | 70% push × 60% iOS | — |
| Push — Android (FCM) | ~14M/day (28%) | 70% push × 40% Android | — |
| In-app | ~10M/day (20%) | Logged-in users only | — |
| Email | ~4M/day (8%) | Digests + transactional | — |
| SMS | ~360K/day | Derived from auth event rate; see Section 1.3 | Validate against auth system logs in month 1 |

**The iOS/Android split matters for the delivery model.** At 60/40, APNs carries 1.5× the push volume of FCM and is the dominant delivery path. The analysis in Section 1.2 reflects this. If the actual split is 40/60, FCM becomes the dominant path; Section 1.4 specifies what changes.

---

### 1.2 Burst Model, Worker Sizing, and Delivery Throughput

#### Viral Inbound Ceiling — Arithmetic Shown

**Inputs:**

| Input | Value | Basis | Validation path |
|-------|-------|-------|-----------------|
| Viral-engaged user cohort | Top 5% of DAU = 150,000 users | Viral content typically engages a small fraction of the active base | Check against actual cohort size for past viral events |
| Baseline notifications/sec per user in cohort | 34/day = 0.000394/sec | Heavy users at 2× average daily rate | Validate against actual user distribution |
| Viral spike multiplier | 8× personal baseline | Sustained 15-minute spike | Monitor at launch |
| Non-viral DAU inbound during spike | ~580/sec | Remaining 2.85M DAU at 17/day average | Stable during a viral event |

**Derivation:**

```
Viral cohort inbound = 150,000 × 0.000394/sec × 8
                     = ~473/sec

Total inbound ceiling = 473/sec + 580/sec = ~1,053/sec → ~1,100/sec

With 20% infrastructure margin: ~1,320/sec as queue-sizing derived ceiling
```

#### Stress Case Multipliers — Justified, Not Asserted

The previous version used a 2× stress case with no justification for why 2× rather than 3× or 5×. The correct approach is to derive the stress case multiplier from evidence about how wrong the viral model could be, and then model the consequences explicitly for each case.

**Why 2× is the base stress case:**

The two main sources of model error are cohort size and spike multiplier. If both are simultaneously 40% higher than estimated (cohort = 210,000, multiplier = 11.2×), total viral inbound approximately doubles:

```
210,000 × 0.000394 × 11.2 = ~927/sec viral cohort
927 + 580 = ~1,507/sec total → approximately 1.4× derived ceiling
```

A simultaneous doubling of both inputs (cohort = 300,000, multiplier = 16×) produces approximately 2× the derived ceiling. This requires both estimates to be wrong by 100% simultaneously — plausible for a first viral event on a new platform with no historical data, which is why we use it as the base stress case.

**Why we also model 3×:**

A 3× case (cohort = 450,000, multiplier = 24×) represents a scenario where the product goes genuinely viral in a way that exceeds any reasonable pre-launch estimate. This has happened to new social platforms. We model it to understand the failure mode, not because we expect it.

**5× and above** would require 400,000+ users each generating 32× their baseline rate simultaneously. At that point, the correct response is emergency scaling, not pre-provisioned capacity. We do not provision for 5×; we define the operational response.

**Stress case consequences:**

| Scenario | Inbound | Queue growth rate | Redis runway (cache.r6g.large) | Response |
|----------|---------|-----------------|-------------------------------|----------|
| Derived ceiling | ~1,100/sec | 0 (below delivery floor) | Infinite | None required |
| 2× stress | ~2,200/sec | ~1,000/sec | ~36 hours | Page on-call at 15 min |
| 3× stress | ~3,300/sec | ~2,100/sec | ~17 hours | P2 shedding at 30 min |
| 5× stress | ~5,500/sec | ~4,300/sec | ~8 hours | Emergency scaling; incident protocol |

The 3× case is survivable with P2 shedding. The 5× case requires emergency response but does not produce OOM within the first 8 hours, which is sufficient time to scale horizontally or enable shedding before data loss.

---

#### P0 Worker and Connection Failover — Connection-Level Failure Addressed

The previous version described P0 failover only at the worker level: "1 active, 1 on standby for failover if the active worker crashes." This does not address APNs connection-level failures: connection drops, TLS renegotiation failures, server-side resets, or APNs endpoint unavailability. With a single APNs connection, any connection-level failure blocks both workers.

**Revised P0 design: 2 APNs connections, not 1.**

```
P0 Push Architecture:
  APNs-1 (primary):   Worker-1A (active), Worker-1B (hot standby)
  APNs-2 (secondary): Worker-2A (active), Worker-2B (hot standby)

  Routing: Consistent hash on notification_id % 2
           If APNs-1 is unhealthy, Worker-1A/1B drain to APNs-2
           APNs-2 can handle full P0 load (P0 volume is << 800/sec ceiling)
```

**Failure modes and responses:**

| Failure mode | Detection | Response | P0 impact |
|--------------|-----------|----------|-----------|
| Worker-1A crashes | Heartbeat miss within 5 seconds | Worker-1B promotes to active; pager fires | Zero: Worker-1B has APNs-1 connection open |
| APNs-1 connection drops | Write error on Worker-1A | Worker-1A reconnects (typically <2 seconds for HTTP/2); Worker-1B takes load on APNs-1 during reconnect | <2 seconds degradation |
| APNs-1 endpoint unavailable | All writes on APNs-1 fail for >10 seconds | Workers drain to APNs-2; pager fires | Zero: APNs-2 carries full P0 load |
| Both APNs connections fail | All P0 writes fail | Incident protocol; SNS + FCM fallback for affected iOS devices where FCM token exists | Degraded; SMS fallback for security alerts |

**TLS renegotiation:** APNs HTTP/2 connections use TLS 1.3. Renegotiation is not initiated by the server mid-session in TLS 1.3; connection lifetime is bounded by APNs server-side session limits, which are handled by reconnecting when the connection is closed. Workers maintain connection health checks on a 30-second heartbeat and reconnect proactively rather than waiting for a write failure.

**Cost of 2 P0 APNs connections:** Each APNs HTTP/2 connection is a persistent TCP connection. The cost is negligible. The benefit is that P0 delivery is not blocked by any single connection failure.

**Revised worker pool:**

| Pool | Workers | APNs connections | Throughput ceiling | Notes |
|------|---------|-----------------|-------------------|-------|
| P0 push | 4 | APNs-1, APNs-2 (dedicated) | 1,600/sec (conservative) | 2 connections × 2 workers each; connection failover modeled |
| P1 push | 4 | APNs-3, APNs-4 (dedicated) | 1,600/sec (conservative) | 2 connections × 2 workers each |
| P2 push | 2 | APNs-5 (dedicated) | 800/sec (conservative) | Single connection acceptable; P2 can tolerate delay |
| FCM (all priorities) | 3 | 1 FCM connection | 10,000/sec (see Section 1.2) | Priority enforced in worker fetch order |
| P0 SMS | 2 | — | 100/sec | Isolated from P1/P2 SMS |
| In-app writers | 4 | — | ~2,000/sec (see below) | — |
| Email workers | 3 | — | 100/sec | SendGrid Pro plan limit |
| SMS workers | 2 | — | 100/sec | Non-urgent SMS |
| Receipt writers | 2 | — | Async; not on critical path | — |
| **Total** | **26** | **5 APNs connections** | | |

The increase from 21 to 26 workers reflects the P0 connection failover requirement and the FCM worker addition. All workers fit comfortably on 2 × c6g.xlarge instances (4 vCPU, 8GB each) with room for the additional 5 workers.

---

#### FCM — Scrutinized on the Same Terms as APNs

The previous version dismissed FCM as non-binding and cited "10,000/sec per Google's documentation" without acknowledging that FCM and APNs serve different device populations.

**FCM volume at 60/40 iOS/Android split:**

FCM carries 14M push notifications/day = ~162/sec average = ~486/sec at 3× peak. This is well below the 10,000/sec FCM connection limit. FCM is not the binding constraint at a 60/40 split.

**If the split is 40/60 iOS/Android:**

FCM carries 21M push notifications/day = ~243/sec average = ~729/sec at 3× peak. Still well below 10,000/sec. FCM remains non-binding even at an inverted split.

**FCM rate limits that do require attention:**

- **Per-device rate limits:** FCM enforces a per-registration-token rate limit. If a single user receives more than approximately 240 notifications/hour across all senders to their device, FCM may throttle or drop messages. This is relevant for P2 notification storms to highly active users. The P2 shedding logic (Section 4) must deduplicate by user_id, not just by notification type.
- **Sender ID limits:** FCM rate limits are per sender ID. We use a single sender ID. If we ever exceed FCM's per-sender limits (documented at 600,000 notifications/minute = 10,000/sec), we would need multiple sender IDs. At current scale, this is not a concern.
- **No contractual throughput guarantee:** Google's documentation describes observed limits, not SLA commitments. We treat 10,000/sec as an operational ceiling, not a guaranteed floor. If FCM degrades, the FCM worker monitors delivery acknowledgment rates and alerts if the acknowledgment rate drops below 95% over a 60-second window.

**FCM connection failover:** Unlike APNs, FCM uses HTTPS POST requests, not a persistent HTTP/2 connection. There is no "connection" to fail at the same level as APNs. FCM worker failover is handled by standard worker crash recovery — if an FCM worker crashes, its queue partition is reassigned to the remaining FCM workers. No special connection-level failover is required.

**Conclusion:** At the specified 60/40 split, FCM is not the binding constraint and the dismissal was directionally correct, but the reasoning was incomplete. FCM requires per-device rate limit awareness in the P2 shedding logic and acknowledgment rate monitoring. These are now specified.

---

#### Idempotency Key TTL — Derived from Retry Schedule

The previous version stated a 1-hour TTL "covers the window between crash and re-attempt under all realistic failure scenarios" without defining the retry schedule or bounding the maximum retry interval.

**Retry schedule — defined:**

The outbox pattern uses a polling worker that checks for unacknowledged notifications. The retry schedule is:

```
Attempt 1: Immediate (initial dispatch)
Attempt 2: 30 seconds after failure detection
Attempt 3: 2 minutes after attempt 2
Attempt 4: 10 minutes after attempt 3
Attempt 5: 30 minutes after attempt 4
Attempt 6+: 30-minute intervals, up to P1 expiry (4 hours from creation)
```

A notification is marked as permanently failed after 4 hours (the P1 expiry threshold) or after 6 attempts, whichever comes first.

**Maximum time between dispatch and retry:**

In the worst case, a worker dispatches a notification to APNs (marking it as in-flight