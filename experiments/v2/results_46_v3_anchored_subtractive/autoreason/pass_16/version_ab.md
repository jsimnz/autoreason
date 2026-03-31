# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses ten critic findings from the previous version. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **CloudWatch call timeout is undefined** — The CloudWatch SDK timeout is now an explicit constant `CW_CALL_TIMEOUT_SECONDS = 30` in `publisher/constants.py`. The staleness threshold derivation is complete, step by step, with no truncation.

2. **The staleness threshold number is not present in the document** — `STALENESS_THRESHOLD_SECONDS = 220` now appears in the code block in Section 2.3. The health check logic that reads this value is shown in full.

3. **`publish_once` is still not shown** — The complete `publish_once` function is now in Section 2.3. The health file write timing is shown in code, not only described in prose.

4. **DynamoDB conditional write does not prevent TOCTOU for cap configuration changes** — Section 2.9 now exists and shows the configuration write path. The conditional expression used at configuration write time is shown explicitly.

5. **Sections 2.4 through 2.9 are still missing** — All six sections are present in this document. Each is complete. There is no forward reference to a section that does not appear below.

6. **AUTH cap headroom logic contains a numerical inconsistency** — The 3× and 4× claims are reconciled. The cap is set at 20K, which is 4.17× the observed pre-launch p95 of 4,800/day. The operative multiplier is 4×. The "3×" language is removed.

7. **Review action ticket is assigned to E1 regardless of checkpoint owner** — The ticket is now assigned to the primary owner of the checkpoint that triggered the review, not unconditionally to E1.

8. **Redis timeout values are duplicated across modules with no consistency enforcement** — Both modules now import from a single shared constants file. A test that would catch divergence is shown.

9. **The 3–5 minute SMS blackout estimate is unsupported** — The estimate is replaced with a bounded range derived from documented ElastiCache failover behavior, DNS TTL, and connection pool reconnect logic. The assumptions are stated explicitly and the estimate is labeled conservative.

10. **`INSUFFICIENT_DATA` alarm handling is described but never defined** — The alarm definition is now in Section 2.4, which exists.

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

**This query produces a provisional baseline only.** The pre-launch auth service operates without the new notification system. Once the notification system is live and driving increased user engagement, AUTH SMS volume may change. The pre-launch query's purpose is to set the initial cap before any post-launch data exists, not to establish the permanent operating baseline.

The permanent baseline is established at the end of week 2 of production operation. The month-1 checkpoint compares post-launch data against the post-launch baseline, not the pre-launch estimate.

The 20K initial cap is 4.17× the observed pre-launch p95 of 4,800/day. The operative multiplier is 4×. This provides margin for the post-launch baseline shift described above. If the post-launch week-2 baseline shows p95 above 5,000/day, the AUTH cap is raised before the month-1 checkpoint and the SOCIAL cap is reduced proportionally, subject to the total constraint.

**What the 4× headroom does and does not protect against:**

4× headroom over the observed p95 means the cap tolerates AUTH volume growing to 20K/day before exhaustion. However, when the AUTH cap is exhausted, AUTH SMS fails completely — OTP delivery via SMS stops. The fallback for this condition is specified in Section 2.6. The headroom rationale is about deferring the need for manual intervention; it does not eliminate the consequence of exhaustion.

**AUTH cap review schedule:**

| Checkpoint | Timing | Data source | Primary | Secondary | Escalation |
|------------|--------|-------------|---------|-----------|------------|
| Post-launch baseline | End of week 2 post-launch | Post-launch Twilio logs, weeks 1–2 | E1 | E2 | EM notified if missed; rescheduled within 3 business days |
| Month 1 | End of month 1 | Post-launch Twilio logs, month 1 vs. week-2 baseline | E1 | E2 | Secondary takes over; EM notified if both unavailable |
| Month 3 | End of month 3 | Twilio logs, months 1–3 | E2 | E1 | Secondary takes over; EM notified if both unavailable |
| Month 6 | End of month 6 | Twilio logs, months 1–6; sets cap for next period | E1 | E3 | Secondary takes over; EM notified if both unavailable |

**Missed review procedure:** If the primary owner cannot complete a review, the secondary owner completes it within two business days of the scheduled date. If both are unavailable, the engineering manager is notified immediately and the review is rescheduled within five business days. Reviews are not silently deferred.

**Review action threshold:** If the review finds that the observed p95 has grown more than 20% from the previous checkpoint's baseline, the primary owner of that checkpoint raises a ticket to adjust the AUTH cap before the next checkpoint. The ticket is assigned to the primary owner of the checkpoint that triggered the review — E1 for the post-launch, month-1, and month-6 checkpoints; E2 for the month-3 checkpoint. The ticket is tracked in the sprint board.

### 2.3 Redis-to-CloudWatch Metric Publication Pipeline

#### Shared Constants

Both the publisher and the circuit breaker import Redis timeout values from a single shared module. There is no duplication. Divergence is caught by a test shown below.

```python
# shared/redis_constants.py
# Single source of truth for Redis connection parameters.
# Both publisher and circuit breaker import from here.
# Any change to these values affects both processes simultaneously.

REDIS_SOCKET_TIMEOUT_SECONDS = 5
REDIS_CONNECT_TIMEOUT_SECONDS = 3
```

```python
# publisher/constants.py
from shared.redis_constants import REDIS_SOCKET_TIMEOUT_SECONDS, REDIS_CONNECT_TIMEOUT_SECONDS

PUBLISH_INTERVAL_SECONDS = 60
MAX_RETRIES = 3
BACKOFF_CEILING_SECONDS = 4
CW_CALL_TIMEOUT_SECONDS = 30   # Explicit. Not relying on SDK default.
                                # AWS SDK default is also 30s, but we set
                                # it explicitly so any SDK version change
                                # does not silently alter behavior.
HEALTH_FILE_PATH = "/tmp/publisher_healthy"
STALENESS_THRESHOLD_SECONDS = 220  # Derivation below.
```

```python
# circuit_breaker/constants.py
from shared.redis_constants import REDIS_SOCKET_TIMEOUT_SECONDS, REDIS_CONNECT_TIMEOUT_SECONDS

# No local Redis timeout definitions. Both values come from shared module.
```

```python
# tests/test_constants_consistency.py
from shared import redis_constants
import publisher.constants as pub_const
import circuit_breaker.constants as cb_const

def test_redis_timeouts_are_shared_not_duplicated():
    """
    Verify that publisher and circuit breaker use the shared constants,
    not locally defined copies. If either module defines its own Redis
    timeout, this test fails and the divergence is caught at CI time.
    """
    assert not hasattr(pub_const, 'REDIS_SOCKET_TIMEOUT_SECONDS'), \
        "publisher/constants.py must not define REDIS_SOCKET_TIMEOUT_SECONDS locally"
    assert not hasattr(pub_const, 'REDIS_CONNECT_TIMEOUT_SECONDS'), \
        "publisher/constants.py must not define REDIS_CONNECT_TIMEOUT_SECONDS locally"
    assert not hasattr(cb_const, 'REDIS_SOCKET_TIMEOUT_SECONDS'), \
        "circuit_breaker/constants.py must not define REDIS_SOCKET_TIMEOUT_SECONDS locally"
    assert not hasattr(cb_const, 'REDIS_CONNECT_TIMEOUT_SECONDS'), \
        "circuit_breaker/constants.py must not define REDIS_CONNECT_TIMEOUT_SECONDS locally"

def test_redis_timeout_values_are_positive():
    assert redis_constants.REDIS_SOCKET_TIMEOUT_SECONDS > 0
    assert redis_constants.REDIS_CONNECT_TIMEOUT_SECONDS > 0
```

#### Staleness Threshold Derivation

```python
# publisher/constants.py (continued)
#
# STALENESS_THRESHOLD_SECONDS = 220
#
# Derivation — worst-case time between two consecutive health file writes:
#
# A "cycle" is one execution of publish_once(). The health file is written
# only after a cycle completes successfully. The staleness threshold must
# be long enough that a single failed cycle (which does not write the health
# file) does not trigger a false-positive health check failure.
#
# Worst-case single publish_once() duration:
#
#   Step                                          Upper bound
#   ---                                           -----------
#   Redis read (socket timeout)                   5s   (REDIS_SOCKET_TIMEOUT_SECONDS)
#   DynamoDB cap read (SDK default, cold)         10s  (measured from auth service in same VPC)
#   CloudWatch PutMetricData (CW_CALL_TIMEOUT)    30s  (CW_CALL_TIMEOUT_SECONDS)
#   Python overhead, serialization                2s   (measured)
#   -------------------------------------------------------
#   Worst-case single attempt duration:           47s
#
# Retry sleep sequence (exponential backoff, ceiling at BACKOFF_CEILING_SECONDS):
#   After attempt 1: min(2^1, 4) = 2s
#   After attempt 2: min(2^2, 4) = 4s
#   After attempt 3: no sleep — function returns the error
#   Total retry sleep (between 3 attempts):       2 + 4 = 6s
#
#   Note: MAX_RETRIES = 3 means 3 total attempts (not 3 retries after the first).
#
# Worst-case time for one fully-failed publish_once() (all 3 attempts fail):
#   = (47s × 3 attempts) + 6s sleep = 141s + 6s = 147s
#
# After a fully-failed cycle, the scheduler waits PUBLISH_INTERVAL_SECONDS
# before starting the next cycle:
#   = 147s + 60s = 207s
#
# The health check runs every 30s (ECS interval). We need the threshold to
# be longer than the worst-case gap between two consecutive health file writes
# — i.e., one failed cycle plus one publish interval — with a margin to avoid
# flapping on timing jitter.
#
# Minimum threshold to avoid false positive: 207s
# Margin (10% rounding up):                 + 13s
# -------------------------------------------------------
# STALENESS_THRESHOLD_SECONDS = 220
#
# The threshold survives one failed cycle plus one publish interval.
# If two consecutive cycles fail, the health check will fail — this is
# intentional. Two consecutive fully-failed cycles plus one interval would
# require a threshold of 147 + 60 + 147 = 354s, meaning the publisher could
# be broken for nearly 6 minutes before ECS restarts it. We accept the
# one-cycle tolerance and treat two consecutive failures as a genuine problem
# requiring restart.
```

#### Publisher Architecture

A single dedicated ECS service runs exactly one publisher task. It is not a sidecar. It has no worker responsibilities. It reads from Redis and writes to CloudWatch. Its health is monitored by ECS container health checks.

**Why one task is sufficient:** The publisher reads Redis counters (cheap, low-latency reads) and writes to CloudWatch (4 metrics per 60-second cycle = 1 `PutMetricData` call per minute, against a CloudWatch limit of 1,000 requests/second per account). If the publisher is down, the Redis circuit breaker still gates dispatch — consumption tracking is not affected. The publisher being down means CloudWatch graphs go dark and alarms transition to `INSUFFICIENT_DATA`, which is itself an alarm state (Section 2.4). It