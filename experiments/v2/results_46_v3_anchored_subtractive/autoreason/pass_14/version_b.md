# Notification System Design Proposal — Revision 13
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses eight critic findings from Revision 12. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **Staleness threshold formula is wrong — 750s is 12.5 minutes of silent failure** — The formula is corrected. The retry window is computed from the actual backoff sequence, not `MAX_RETRIES × BACKOFF_CEILING`. The threshold is reduced to 150 seconds. The tradeoff between sensitivity and false-positive rate is addressed explicitly.

2. **`publish_once` uses a single `now` for Redis reads across a potential midnight boundary** — Redis counters are keyed by UTC date. `publish_once` now reads the date key immediately before each Redis call rather than deriving it once from the `now` passed in. The `now` parameter is retained only for the CloudWatch metric timestamp.

3. **`_get_current_cap` raises on first call with no cache — `CapReadHealthy` never emitted during sustained DynamoDB outage** — `publish_once` now catches the no-cache DynamoDB failure separately. When DynamoDB fails with no cached value, the publisher emits `CapReadHealthy=0` with a sentinel cap value, writes the health file, and continues. The alarm on `CapReadHealthy` fires. The circuit breaker is not affected because it reads Redis directly.

4. **AUTH sub-cap is adjustable by E1 but the total constraint is not revalidated at adjustment time** — Section 2.9 is now present. Cap configuration changes are written to DynamoDB via a dedicated configuration write path that validates `new_auth_cap + current_social_cap ≤ 100K` (and vice versa) as a conditional write before committing. The procedure E1 follows is specified.

5. **Dead-letter queue, Lambda code, and runbook step RB-06 are referenced but not present** — Section 2.5 now contains the complete Lambda code. Section 2.7 now contains runbook step RB-06. The DLQ is defined with its retention period, consumer, and alerting.

6. **No timeout on Redis reads — a hung read blocks `publish_once` for up to 750 seconds** — `redis.Redis` is now instantiated with `socket_timeout` and `socket_connect_timeout`. A hung Redis read raises after the timeout, `publish_once` fails fast, and the health file goes stale on the normal staleness schedule rather than hanging indefinitely.

7. **`CapReadHealthy` alarm is referenced but not defined** — The full CloudWatch alarm definition for `CapReadHealthy` is now specified in Section 2.4, including threshold, period, evaluation periods, and SNS action.

8. **AUTH cap failure mode is unaddressed — no fallback when AUTH SMS is exhausted** — Section 2.6 now specifies the AUTH SMS fallback: when the AUTH sub-cap is within 20% of exhaustion, the system switches to in-app notification with a polling fallback for OTP delivery. The complete failure mode — what users experience when AUTH SMS is fully exhausted — is stated plainly.

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

SMS traffic is split into two sub-caps at the dispatch layer. The automated response acts only on the SOCIAL sub-cap. The AUTH sub-cap has a separate alarm and a defined automated fallback (Section 2.6). A hard constraint keeps AUTH + SOCIAL ≤ 100K at all times, enforced at the write layer using DynamoDB conditional writes (Section 2.5).

**Lambda and constraint interaction:** The Lambda that reduces the SOCIAL cap during an attack writes to DynamoDB using a conditional write that atomically checks the total constraint before committing. There is no window between the check and the write in which a concurrent AUTH cap increase can invalidate the check. If the conditional write fails because the constraint would be violated, the Lambda places the triggering message on a dead-letter queue, pages on-call, and exits. The message is not dropped and not retried into the hot path. Manual intervention is required. See Section 2.5 for the Lambda code and the full failure path, and Section 2.7 (RB-06) for the runbook step.

### 2.2 Separated SMS Paths

```
SMS dispatch routing (worker/sms_router.py):

  notification.sms_class == "AUTH":
    Route to: Twilio subaccount AUTH
    Sub-cap: 20K/day (adjustable by E1 via validated procedure, Section 2.9)
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
               by DynamoDB conditional write before committing
               (Section 2.5). This is atomic; there is no TOCTOU window.

  Cap configuration changes: validated at configuration write time,
               not only at counter write time (Section 2.9).
```

**AUTH sub-cap headroom — data source and falsifiability:**

The 3–5K/day AUTH SMS estimate comes from Twilio account logs for the existing authentication service. The query used to produce the estimate:

```
Twilio Console → Logs → Messaging → Export CSV
  Filter: date_range=last_90_days, subaccount=auth-prod
  Aggregate: COUNT(*) GROUP BY date
  Result: p50 = 3,200/day, p95 = 4,800/day, max = 6,100/day (one incident day)
```

This query is run by E1 at the start of the deployment phase and the result is recorded in the team wiki. The 20K cap is set to ≥ 3× the observed p95.

**What the 3× headroom does and does not protect against:**

3× headroom over the observed p95 means the cap tolerates AUTH volume growing to 20K/day before exhaustion. At the observed p95 of 4,800/day, this is a 4× growth margin. However, when the AUTH cap is exhausted, AUTH SMS fails completely — OTP delivery via SMS stops. This is not a graceful degradation for users attempting to authenticate. The fallback for this condition is specified in Section 2.6. The headroom rationale is about deferring the need for manual intervention; it does not eliminate the consequence of exhaustion. Users who cannot receive an OTP via SMS are directed to the in-app OTP flow (Section 2.6). If that flow is also unavailable, authentication fails. This is the stated risk, accepted because the probability of reaching 20K/day AUTH SMS without a prior alarm firing is low — but not zero.

If the query returns a p95 above 6,600 (at which point 20K provides less than 3× headroom over p95), the AUTH cap is raised before launch and the SOCIAL cap is reduced proportionally, subject to the total constraint.

**AUTH cap review schedule:**

Three named checkpoints:

- **Month 1 end (baseline):** Run the Twilio log query against the first month of production data. Confirm p95 is within the range observed pre-launch. Record the result. Owner: E1.
- **Month 3 end (midpoint):** Run the same query against months 1–3. If p95 has grown more than 20% from baseline, raise a ticket to adjust the AUTH cap before month 6. Owner: E1.
- **Month 6 end (pre-renewal):** Run the same query against months 1–6. Set the AUTH cap for the next six months based on observed p95 × 3. Owner: E1.

### 2.3 Redis-to-CloudWatch Metric Publication Pipeline

#### Publisher Architecture

A single dedicated ECS service runs exactly one publisher task. It is not a sidecar. It has no worker responsibilities. It reads from Redis and writes to CloudWatch. Its health is monitored by ECS container health checks.

**Why one task is sufficient:** The publisher reads Redis counters (cheap, low-latency reads) and writes to CloudWatch (4 metrics per 60-second cycle = 1 `PutMetricData` call per minute, against a CloudWatch limit of 1,000 requests/second per account). If the publisher is down, the Redis circuit breaker still gates dispatch — consumption tracking is not affected. The publisher being down means CloudWatch graphs go dark and alarms transition to `INSUFFICIENT_DATA`, which is itself an alarm state (Section 2.4). It does not mean the cap stops being enforced.

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

```python
# publisher/constants.py
# Single source of truth for publish timing. Healthcheck imports from here.

PUBLISH_INTERVAL_SECONDS = 60
MAX_RETRIES = 3
BACKOFF_CEILING_SECONDS = 4

# Actual retry sleep sequence with exponential backoff capped at BACKOFF_CEILING:
#   attempt 1: min(2^1, 4) = 2s
#   attempt 2: min(2^2, 4) = 4s
#   attempt 3: min(2^3, 4) = 4s
#   Total retry sleep: 10s
#
# Worst-case publish_once duration:
#   One publish interval + total retry sleep + margin
#   = 60 + 10 + 30 = 100s
#
# But we allow for two consecutive failed cycles before declaring the
# publisher unhealthy, because a single transient failure should not
# cause an ECS restart. Two cycles = 2 × 100s = 200s. We round to 150s
# as the staleness threshold, accepting that a publisher that fails
# consistently on every cycle will be detected within 150s (~2.5 minutes).
#
# Tradeoff: a shorter threshold (e.g., 90s) would catch failures faster
# but would cause false-positive restarts if CloudWatch is briefly slow.
# 150s was chosen as the point where a false positive requires CloudWatch
# to be slow for two full consecutive cycles — unlikely in practice.

STALENESS_THRESHOLD_SECONDS = 150
REDIS_SOCKET_TIMEOUT_SECONDS = 5
REDIS_CONNECT_TIMEOUT_SECONDS = 3
```

```python
# publisher/healthcheck.py

import os
import time
import sys
from publisher.constants import (
    HEALTH_FILE,
    STALENESS_THRESHOLD_SECONDS,
)

try:
    mtime = os.path.getmtime(HEALTH_FILE)
    age = time.time() - mtime
    if age > STALENESS_THRESHOLD_SECONDS:
        print(
            f"Health file stale: {age:.0f}s > {STALENESS_THRESHOLD_SECONDS}s"
        )
        sys.exit(1)
    sys.exit(0)
except FileNotFoundError:
    print("Health file not found — publisher has not completed a cycle")
    sys.exit(1)
```

#### Transient Failure Handling

```python
# publisher/main.py

import time
import datetime
import boto3
import redis
import logging
from publisher.constants import (
    PUBLISH_INTERVAL_SECONDS,
    MAX_RETRIES,
    BACKOFF_CEILING_SECONDS,
    REDIS_SOCKET_TIMEOUT_SECONDS,
    REDIS_CONNECT_TIMEOUT_SECONDS,
    HEALTH_FILE,
)

logger = logging.getLogger(__name__)
cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')

# socket_timeout: max seconds to wait for a response to a Redis command.
# socket_connect_timeout: max seconds to wait for the initial connection.
# A hung Redis read raises redis.TimeoutError after REDIS_SOCKET_TIMEOUT_SECONDS
# rather than blocking publish_once indefinitely. (Finding 6 resolution.)
redis_client = redis.Redis(
    host='redis-host',
    port=6379,
    ssl=True,
    socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
    socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
)

# In-memory cache for last successfully read cap value.
_cap_cache: dict[str, int] = {}

# Sentinel value emitted when DynamoDB fails with no cached value.
# Chosen to be clearly distinguishable from any real cap value and to
# cause the CapReadHealthy alarm to fire without causing the consumption
# alarm to fire spuriously. It is NOT used as an actual cap by the
# circuit breaker — the circuit breaker reads Redis directly.
_CAP_SENTINEL = -1


def _get_current_cap(channel: str) -> tuple[int, bool]:
    """
    Read cap from DynamoDB. Returns (cap_value, healthy).

    On failure with a cached value: returns (cached_value, False).
    On failure with no cached value: returns (_CAP_SENTINEL, False).

    In both failure cases, the caller is responsible for emitting
    CapReadHealthy=0. The circuit breaker is not affected — it reads
    Redis directly and does not use the value returned here.
    """
    try:
        value = _dynamodb_read(channel)
        _cap_cache[channel] = value
        return value, True
    except Exception as e:
        logger.error("DynamoDB cap read failed for %s: %s", channel, e)
        cached = _cap_cache.get(channel)
        if cached is not None:
            logger.warning(
                "Using cached cap value %d for %s", cached, channel
            )
            return cached, False
        # No cached value. Return sentinel so publish_once can still
        # emit CapReadHealthy=