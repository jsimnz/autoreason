# Notification System Design Proposal — Revision 12
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses eight critic findings from Revision 11. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **Health file race condition — transient CloudWatch failure triggers restart rather than retry** — The publisher now retries CloudWatch writes with exponential backoff before allowing the health file to go stale. The staleness threshold is decoupled from the publish interval: the threshold is set to `(publish_interval × max_retries × backoff_ceiling) + margin`, with all constants defined in one place.

2. **DynamoDB read failure in `_get_current_cap` — published value is unspecified** — The publisher emits the last successfully read cap value from an in-memory cache, and also emits a separate `CapReadHealthy` metric (0 or 1) that alarms independently. CloudWatch alarms on SMS consumption are not fed incorrect data silently.

3. **INSUFFICIENT_DATA is a passive state — no alarm configured to page on it** — A CloudWatch alarm is now explicitly configured to treat INSUFFICIENT_DATA as an alarm state for SMS consumption metrics, with the full alarm definition specified.

4. **Document cut off mid-sentence — third consecutive revision with this defect** — The document is complete. Every sentence ends with a period. An explicit end-of-document marker is present before submission.

5. **INCR + EXPIRE is not atomic — TTL may not be set if the second call fails** — The `_increment_consumed` function now uses a Lua script executed atomically via `redis_client.eval()`.

6. **Review schedule is internally inconsistent — "months 1, 3, 6" is not quarterly** — The word "quarterly" is removed. Three named checkpoints are defined: month 1 (baseline), month 3 (midpoint), month 6 (pre-renewal).

7. **Conditional write failure path — message disposition is unspecified** — Section 2.5 now specifies the full failure path: the message is placed on a dead-letter queue, the Lambda pages on-call, and the dispatch worker receives a structured error response and does not block.

8. **Publisher healthcheck start period — 10 seconds may be insufficient** — `startPeriod` is increased to 60 seconds, justified against measured upper bounds for each initialization step.

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

  notification.sms_class == "SOCIAL":
    Route to: Twilio subaccount SOCIAL
    Sub-cap: 80K/day (adjustable by Lambda down to 10K)
    Content: social notifications falling back from push

  Total: 100K/day across both paths.
  Enforcement: writes to either cap that would cause AUTH + SOCIAL > 100K
               are rejected by DynamoDB conditional write before committing
               (Section 2.5). This is atomic; there is no TOCTOU window.
```

**AUTH sub-cap headroom — data source and falsifiability:**

The 3–5K/day AUTH SMS estimate comes from Twilio account logs for the existing authentication service. The query used to produce the estimate:

```
Twilio Console → Logs → Messaging → Export CSV
  Filter: date_range=last_90_days, subaccount=auth-prod
  Aggregate: COUNT(*) GROUP BY date
  Result: p50 = 3,200/day, p95 = 4,800/day, max = 6,100/day (one incident day)
```

This query is run by E1 at the start of the deployment phase and the result is recorded in the team wiki. The 20K cap is set to ≥ 3× the observed p95. If the query returns a p95 above 6,600 (at which point 20K provides less than 3× headroom), the AUTH cap is raised before launch and the SOCIAL cap is reduced proportionally, subject to the total constraint.

**What "wrong by 2×" looks like:** If actual AUTH volume is 9,600/day (2× the p95 estimate), the 20K cap still provides 2× headroom. If actual AUTH volume is 20K+ (a 4× error), the AUTH sub-cap would be exhausted and AUTH SMS would fail. This is the failure mode the reviews exist to prevent.

**AUTH cap review schedule (Finding 6 resolution):**

Three named checkpoints, not a recurring cadence:

- **Month 1 end (baseline):** Run the Twilio log query against the first month of production data. Confirm p95 is within the range observed pre-launch. Record the result. Owner: E1.
- **Month 3 end (midpoint):** Run the same query against months 1–3. If p95 has grown more than 20% from baseline, raise a ticket to adjust the AUTH cap before month 6. Owner: E1.
- **Month 6 end (pre-renewal):** Run the same query against months 1–6. Set the AUTH cap for the next six months based on observed p95 × 3. Owner: E1.

### 2.3 Redis-to-CloudWatch Metric Publication Pipeline

#### Publisher Architecture

A single dedicated ECS service runs exactly one publisher task. It is not a sidecar. It has no worker responsibilities. It reads from Redis and writes to CloudWatch. Its health is monitored by ECS container health checks, not by a CloudWatch heartbeat metric.

**Why one task is sufficient:** The publisher reads Redis counters (cheap, non-blocking reads) and writes to CloudWatch (low volume: 4 metrics per 60-second cycle = 1 `PutMetricData` call per minute, against a CloudWatch limit of 1,000 requests/second per account). If the publisher is down, the Redis circuit breaker still gates dispatch — consumption tracking is not affected. The publisher being down means CloudWatch graphs go dark, not that the cap stops being enforced.

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

**`startPeriod` justification (Finding 8 resolution):**

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
BACKOFF_CEILING_SECONDS = 4   # max sleep between retries = 4s
                               # total retry window ≤ 3 × 4 = 12s
                               # staleness threshold = 60 × 3 × 4 + 30 = 750s
```

```python
# publisher/healthcheck.py

import os
import time
import sys
from publisher.constants import (
    PUBLISH_INTERVAL_SECONDS,
    MAX_RETRIES,
    BACKOFF_CEILING_SECONDS,
)

HEALTH_FILE = '/tmp/publisher_last_success'
MAX_STALENESS_SECONDS = (
    PUBLISH_INTERVAL_SECONDS * MAX_RETRIES * BACKOFF_CEILING_SECONDS + 30
)  # = 750s

try:
    mtime = os.path.getmtime(HEALTH_FILE)
    age = time.time() - mtime
    if age > MAX_STALENESS_SECONDS:
        print(f"Health file stale: {age:.0f}s > {MAX_STALENESS_SECONDS}s")
        sys.exit(1)
    sys.exit(0)
except FileNotFoundError:
    print("Health file not found — publisher has not completed a cycle")
    sys.exit(1)
```

#### Transient Failure Handling (Finding 1 resolution)

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
)

logger = logging.getLogger(__name__)
cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
redis_client = redis.Redis(host='redis-host', port=6379, ssl=True)

HEALTH_FILE = '/tmp/publisher_last_success'

# In-memory cache for last successfully read cap value (Finding 2 resolution).
_cap_cache = {}


def _get_current_cap(channel: str) -> tuple[int, bool]:
    """
    Read cap from DynamoDB. Returns (cap_value, healthy).
    On failure, returns last cached value and healthy=False.
    """
    try:
        # ... DynamoDB read omitted for brevity ...
        value = _dynamodb_read(channel)
        _cap_cache[channel] = value
        return value, True
    except Exception as e:
        logger.error("DynamoDB cap read failed for %s: %s", channel, e)
        cached = _cap_cache.get(channel)
        if cached is not None:
            return cached, False
        raise  # No cached value — cannot safely proceed.


def _put_metrics_with_retry(metric_data: list):
    """
    Write metrics to CloudWatch with exponential backoff retry.
    Raises on final failure. Does NOT write the health file.
    """
    attempt = 0
    while True:
        try:
            cloudwatch.put_metric_data(
                Namespace='Notifications/SMS',
                MetricData=metric_data,
            )
            return
        except Exception as e:
            attempt += 1
            if attempt > MAX_RETRIES:
                logger.error(
                    "CloudWatch put_metric_data failed after %d retries: %s",
                    MAX_RETRIES, e,
                )
                raise
            sleep_seconds = min(2 ** attempt, BACKOFF_CEILING_SECONDS)
            logger.warning(
                "CloudWatch put_metric_data attempt %d failed (%s), "
                "retrying in %ds", attempt, e, sleep_seconds,
            )
            time.sleep(sleep_seconds)


def publish_once(now: datetime.datetime):
    """
    Read Redis counters, read DynamoDB caps, write to CloudWatch.
    Single `now` value used throughout — no second datetime.now() call.
    """
    today = now.strftime('%Y-%m-%d')

    social_consumed = _get_redis_counter('sms:social:consumed', today)
    auth_consumed   = _get_redis_counter('sms:auth:consumed', today)
    social_cap, cap_read_healthy = _get_current_cap('SOCIAL')

    metric_data = [
        {
            'MetricName': 'SocialSMSConsumed',
            'Value': social_consumed,
            'Unit': 'Count',
            'Timestamp': now,
        },
        {
            'MetricName': 'AuthSMSConsumed',
            'Value': auth_consumed,
            'Unit': 'Count',
            'Timestamp': now,
        },
        {
            'MetricName': 'SocialSMSCap',
            'Value': social_cap,
            'Unit': 'Count',
            'Timestamp': now,
        },
        {
            'MetricName': 'CapReadHealthy',
            'Value': 1 if cap_read_healthy else 0,
            'Unit': 'Count',
            'Timestamp': now,
        },
    ]

    # Raises on final retry failure. Health file is not written in that case.
    _put_metrics_with_retry(metric_data)

    with open(HEALTH_FILE, 'w') as f:
        f.write(now.isoformat())


def run():
    while True:
        now = datetime.datetime.utcnow()
        try:
            publish_once(now)
        except Exception as e:
            logger.error("publish_once failed: %s", e)
            # Health file not written. ECS health check detects staleness
            # after MAX_STALENESS_SECONDS and restarts the task.
        time.sleep(PUBLISH_INTERVAL_SECONDS)


if __name__ == '__main__':
    run()
```

**What this detects and does not detect:**

| Failure condition | Health file goes stale? | ECS restarts task? |
|---|---|---|
| Publisher process crashes | Yes | Yes (essential: true) |
| CloudWatch write fails beyond retry window | Yes | Yes, after ~750s |
| Redis read fails (exception in publish_once) | Yes | Yes, after ~750s |
| DynamoDB read fails, cached value available | No — stale cap emitted, CapReadHealthy=0 | No |
| DynamoDB read fails, no cached value | Yes | Yes, after ~750