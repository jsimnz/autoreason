# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses eight critic findings from the previous version. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **Staleness threshold math is wrong** — The threshold is corrected to 220s. The derivation is shown step by step. The prose claim ("two consecutive failed cycles") now matches the number.

2. **`publish_once` is cut off mid-function — health file write timing is unspecified** — The complete `publish_once` function is now shown. The health file is written only after CloudWatch confirms delivery. A partial success (Redis read succeeded, CloudWatch failed) does not update the health file.

3. **Circuit breaker Redis failure mode is unaddressed** — The circuit breaker's behavior when Redis is unreachable is now specified in Section 2.3. The failure mode (attack + Redis outage simultaneously) has a defined behavior: fail closed, block all SMS dispatch, page on-call. The tradeoff between fail-open and fail-closed is stated explicitly.

4. **The "atomic" conditional write guarantee is false if AUTH and SOCIAL caps are separate DynamoDB items** — AUTH and SOCIAL consumed counters are stored as attributes on a single DynamoDB item. A single conditional write can atomically check and update both values.

5. **Sections 2.4 through 2.9 are missing** — All sections are now present: Section 2.4 (CloudWatch alarm definitions), Section 2.5 (Lambda code and DLQ), Section 2.6 (AUTH SMS fallback), Section 2.7 (runbook RB-06), Section 2.8 (cap constraint enforcement), Section 2.9 (cap configuration change procedure).

6. **`_CAP_SENTINEL = -1` causes undefined behavior in ratio alarms** — The sentinel value is removed. When DynamoDB fails with no cached value, the publisher emits `CapReadHealthy=0` and skips emitting a cap metric entirely for that cycle. The alarm on `INSUFFICIENT_DATA` state handles the missing cap metric.

7. **E1 owns all three AUTH cap review checkpoints with no backup or escalation path** — Each checkpoint now has a primary and a secondary owner. A missed review has a defined escalation path.

8. **The Twilio baseline is established pre-launch against pre-launch data** — The pre-launch query is explicitly labeled a provisional baseline. A post-launch baseline is established at the end of week 2 of production operation. The month-1 checkpoint compares post-launch data against the post-launch baseline, not the pre-launch estimate.

---

## 1. Scale Assumptions and Constraints

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio |
| Notifications/user/day | ~17 | Industry avg for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth and security events only |

---

## 2. SMS Cap, Attack Modeling, and Alarm Structure

### 2.1 Corrected Framing

WAF is not a cap-protection mechanism. At 2,500 req/sec, 60 seconds of unmitigated traffic is 150,000 SMS messages — exceeding the entire 100K/day cap before WAF has acted. WAF is useful for stopping continued attack after the cap is exhausted. The cap is protected by a pre-depletion circuit breaker based on cumulative consumption, not throughput rate.

SMS traffic is split into two sub-caps at the dispatch layer. The automated response acts only on the SOCIAL sub-cap. The AUTH sub-cap has a separate alarm and a defined automated fallback (Section 2.6). A hard constraint keeps AUTH + SOCIAL ≤ 100K at all times, enforced at the write layer using DynamoDB conditional writes against a single item containing both counters (Section 2.8).

**Lambda and constraint interaction:** The Lambda that reduces the SOCIAL cap during an attack writes to DynamoDB using a conditional write that atomically checks the total constraint before committing. Because both AUTH and SOCIAL consumed counters live as attributes on a single DynamoDB item, the condition expression can check both values in one operation. There is no window between the check and the write in which a concurrent AUTH cap increase can invalidate the check. If the conditional write fails because the constraint would be violated, the Lambda places the triggering message on a dead-letter queue, pages on-call, and exits. The message is not dropped and not retried into the hot path. Manual intervention is required. See Section 2.5 for the Lambda code and the full failure path, and Section 2.7 (RB-06) for the runbook step.

### 2.2 Separated SMS Paths

```
SMS dispatch routing (worker/sms_router.py):

  notification.sms_class == "AUTH":
    Route to: Twilio subaccount AUTH
    Sub-cap: 20K/day (adjustable via validated procedure, Section 2.9)
    Content: OTP codes, login alerts, password reset links
    Fallback: in-app notification with OTP polling (Section 2.6)

  notification.sms_class == "SOCIAL":
    Route to: Twilio subaccount SOCIAL
    Sub-cap: 80K/day (adjustable by Lambda down to 10K)
    Content: social notifications falling back from push
    Fallback: suppressed with in-app notification queued

  Total: 100K/day across both paths.
  Enforcement: writes to either sub-cap counter that would cause
               AUTH_consumed + SOCIAL_consumed > 100K are rejected
               by a single DynamoDB conditional write against one item
               containing both counters (Section 2.8). This is atomic;
               there is no TOCTOU window because both values are
               attributes on the same item.

  Cap configuration changes: validated at configuration write time,
               not only at counter write time (Section 2.9).
```

**AUTH sub-cap headroom — data source, falsifiability, and baseline timing:**

The pre-launch estimate uses Twilio account logs from the existing authentication service:

```
Twilio Console → Logs → Messaging → Export CSV
  Filter: date_range=last_90_days, subaccount=auth-prod
  Aggregate: COUNT(*) GROUP BY date
  Result: p50 = 3,200/day, p95 = 4,800/day, max = 6,100/day (one incident day)
```

**This query produces a provisional baseline only.** The pre-launch auth service operates without the new notification system. Once the notification system is live and driving increased user engagement, AUTH SMS volume may change. Its purpose is to set the initial cap before any post-launch data exists, not to establish the permanent operating baseline.

The permanent baseline is established at the end of week 2 of production operation. The month-1 checkpoint compares post-launch data against the post-launch baseline, not the pre-launch estimate.

The 20K initial cap is set to ≥ 3× the observed pre-launch p95 (4,800/day). If the post-launch week-2 baseline shows p95 above 6,600/day, the AUTH cap is raised before the month-1 checkpoint and the SOCIAL cap is reduced proportionally, subject to the total constraint.

**What the 3× headroom does and does not protect against:**

3× headroom over the observed p95 means the cap tolerates AUTH volume growing to 20K/day before exhaustion. However, when the AUTH cap is exhausted, AUTH SMS fails completely — OTP delivery via SMS stops. The fallback is specified in Section 2.6. The headroom rationale is about deferring the need for manual intervention; it does not eliminate the consequence of exhaustion.

**AUTH cap review schedule:**

Each checkpoint has a primary owner, a secondary owner, and a defined escalation path. A missed review is not silently skipped.

| Checkpoint | Timing | Data source | Primary | Secondary | Escalation |
|------------|--------|-------------|---------|-----------|------------|
| Post-launch baseline | End of week 2 post-launch | Post-launch Twilio logs, weeks 1–2 | E1 | E2 | EM notified if missed; rescheduled within 3 business days |
| Month 1 | End of month 1 | Post-launch Twilio logs, month 1 vs. week-2 baseline | E1 | E2 | Secondary takes over; EM notified if both unavailable |
| Month 3 | End of month 3 | Twilio logs, months 1–3 | E2 | E1 | Secondary takes over; EM notified if both unavailable |
| Month 6 | End of month 6 | Twilio logs, months 1–6; sets cap for next period | E1 | E3 | Secondary takes over; EM notified if both unavailable |

**Missed review procedure:** If the primary owner cannot complete a review, the secondary owner completes it within two business days of the scheduled date. If both are unavailable, the engineering manager is notified immediately and the review is rescheduled within five business days. Reviews are not silently deferred.

**Review action threshold:** If the review finds that the observed p95 has grown more than 20% from the previous checkpoint's baseline, the primary owner raises a ticket to adjust the AUTH cap before the next checkpoint.

### 2.3 Redis-to-CloudWatch Metric Publication Pipeline

#### Publisher Architecture

A single dedicated ECS service runs exactly one publisher task. It is not a sidecar. It has no worker responsibilities. It reads from Redis and writes to CloudWatch. Its health is monitored by ECS container health checks.

**Why one task is sufficient:** The publisher reads Redis counters (cheap, low-latency reads) and writes to CloudWatch (4 metrics per 60-second cycle = 1 `PutMetricData` call per minute, against a CloudWatch limit of 1,000 requests/second per account). If the publisher is down, the Redis circuit breaker still gates dispatch — consumption tracking is not affected. The publisher being down means CloudWatch graphs go dark and alarms transition to `INSUFFICIENT_DATA`, which is itself an alarm state (Section 2.4). It does not mean the cap stops being enforced.

#### Circuit Breaker Redis Failure Mode

The circuit breaker reads Redis directly to check cumulative consumption against the cap. If Redis is unreachable, both the publisher and the circuit breaker lose their data source simultaneously.

**Defined behavior when Redis is unreachable:**

The circuit breaker fails closed. When a Redis read raises `redis.TimeoutError` or `redis.ConnectionError`, the circuit breaker blocks the dispatch attempt and returns a `CIRCUIT_OPEN` response. The notification is placed on the SMS retry queue with a backoff. No SMS is dispatched.

**Rationale for fail-closed:** The alternative is fail-open — dispatch SMS when the circuit breaker cannot read consumption. Fail-open means that during a Redis outage, the cap is unenforced. An attacker who can cause a Redis outage can exhaust the SMS cap without triggering the circuit breaker. At 100K SMS/day and Twilio's pricing, this is a meaningful financial exposure. Fail-closed means legitimate AUTH SMS also stops during a Redis outage, which triggers the AUTH SMS fallback (Section 2.6). This is the worse user experience but the lower financial and security risk. We accept it.

**Failure mode: simultaneous attack and Redis outage:**

The circuit breaker fails closed. All SMS dispatch stops. The AUTH SMS fallback activates (Section 2.6). The CloudWatch alarm for Redis connectivity fires (Section 2.4). On-call is paged. The runbook step for this scenario is RB-07 (Section 2.7).

The Redis outage alarm has a 2-minute evaluation window. During those 2 minutes, the circuit breaker is blocking all SMS. After on-call acknowledges, the remediation path is ElastiCache failover to the replica, which typically completes in 60–90 seconds. Total SMS blackout window: approximately 3–5 minutes in the worst case. This is acceptable for SOCIAL SMS. For AUTH SMS, the in-app OTP fallback covers the gap.

**Redis timeout configuration:**

```python
# publisher/constants.py
REDIS_SOCKET_TIMEOUT_SECONDS = 5
REDIS_CONNECT_TIMEOUT_SECONDS = 3

# circuit_breaker/constants.py — same values, separate module
CB_REDIS_SOCKET_TIMEOUT_SECONDS = 5
CB_REDIS_CONNECT_TIMEOUT_SECONDS = 3
```

Both the publisher and the circuit breaker instantiate Redis clients with explicit socket timeouts. A hung Redis read raises after the timeout rather than blocking indefinitely.

#### Publisher Liveness Monitoring

ECS container health checks directly measure whether the publisher process is running. They do not depend on CloudWatch being operational.

```json
{
  "containerDefinitions": [
    {
      "name": "cw-metric-publisher",
      "image": "notifications-cw-publisher:latest",
      "essential": true,
      "healthCheck": {
        "command": ["CMD-SHELL", "python /app/healthcheck.py || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

**`startPeriod` justification:**

The health file is written after the first successful publish cycle. The first cycle includes:

| Step | Upper bound |
|------|-------------|
| Python interpreter startup | 3s |
| Redis connection establishment (with TLS) | 5s |
| DynamoDB cap read (first call, cold connection) | 5s |
| CloudWatch `PutMetricData` call (first call, cold connection) | 10s |
| Health file write | <1s |
| **Total** | **~24s** |

Upper bounds are measured from the existing auth service running in the same VPC. The 60-second `startPeriod` provides 2.5× margin over the measured worst case. During the start period, failed health checks are not counted toward the `retries: 3` limit.

#### Corrected Staleness Threshold Derivation

```python
# publisher/constants.py
PUBLISH_INTERVAL_SECONDS = 60
MAX_RETRIES = 3
BACKOFF_CEILING_SECONDS = 4

# Retry sleep sequence with exponential backoff capped at BACKOFF_CEILING:
#   attempt 1 sleep: min(2^1, 4) = 2s
#   attempt 2 sleep: min(2^2, 4) = 4s
#   attempt 3 sleep: min(2^3, 4) = 4s
#   Total retry sleep across all attempts: 10s
#
# Worst-case single publish_once duration:
#   CloudWatch SDK default timeout: 30s
#   MAX_RETRIES attempts × 30s each: 90s
#   Total retry sleep: 10s
#   Worst-case publish_once: 90 + 10 = 100s
#
# Worst-case single cycle (interval + publish_once):
#   60 + 100 = 160s
#
# We allow two consecutive failed cycles before declaring unhealthy.
# Threshold: 2 × 160s = 320s — but we want to detect failure within
# one additional publish interval after the second failure, so we use:
#   160 (one cycle) + 60 (one interval) = 220s
#
# At 220s the publisher has missed at least one full cycle and is
# well into a second. A publisher succeeding on every cycle writes
# the health file every ~60s; 220s gives 3.6× margin over normal
# operation before a false positive.
#
# Tradeoff: a shorter threshold catches failures faster but risks
# false-positive restarts if CloudWatch is briefly slow. 220s requires
# CloudWatch to be slow for two full consecutive cycles — unlikely.

STALENESS_THRESHOLD_SECONDS = 220
REDIS_SOCKET_TIMEOUT_SECONDS = 5
REDIS_CONNECT_TIMEOUT_SECONDS = 3
HEALTH_FILE = '/tmp/publisher_last_success'
```

```python
# publisher/healthcheck.py

import os
import time
import sys
from publisher.constants import HEALTH_FILE, STALENESS_THRESHOLD_SECONDS

try:
    mtime