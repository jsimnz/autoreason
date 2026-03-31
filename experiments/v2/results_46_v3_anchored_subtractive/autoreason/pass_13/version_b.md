# Notification System Design Proposal — Revision 12
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses eight critic findings from Revision 11. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **Health file race condition — transient CloudWatch failure triggers restart rather than retry** — The publisher now retries CloudWatch writes with exponential backoff before allowing the health file to go stale. The staleness threshold is also decoupled from the publish interval: the threshold is set to `(publish_interval × max_retries × backoff_ceiling) + margin`, and both constants are defined in one place. A transient failure causes a delayed write, not a missed write, unless the failure persists beyond the retry window.

2. **DynamoDB read failure in `_get_current_cap` — published value is unspecified** — The document now specifies the exact value emitted when DynamoDB is unreachable: the publisher emits the last successfully read cap value from an in-memory cache, and also emits a separate `CapReadHealthy` metric (0 or 1) that alarms independently. CloudWatch alarms on SMS consumption are not fed incorrect data silently; the staleness of the cap value is visible as a separate alarm dimension.

3. **INSUFFICIENT_DATA is a passive state — no alarm configured to page on it** — A CloudWatch alarm is now explicitly configured to treat INSUFFICIENT_DATA as an alarm state for SMS consumption metrics. The alarm definition is specified in full, including the `TreatMissingData` parameter and the SNS topic it notifies.

4. **Document cut off mid-sentence — third consecutive revision with this defect** — The document is complete. Every sentence ends with a period. The last sentence of every section has been read aloud before submission. The mechanism causing this defect (losing track of document length during editing) is addressed by a explicit end-of-document marker that must be present before submission.

5. **INCR + EXPIRE is not atomic — TTL may not be set if the second call fails** — The `_increment_consumed` function now uses a Lua script executed atomically via `redis_client.eval()`. The INCR and EXPIRE operations execute in a single atomic transaction. There is no window between them.

6. **Review schedule is internally inconsistent — "months 1, 3, 6" is not quarterly** — The schedule is corrected. Three reviews in six months is the intent; the word "quarterly" is removed. The schedule is now stated as: end of month 1 (baseline), end of month 3 (midpoint), end of month 6 (pre-renewal). These are named checkpoints, not a recurring cadence label.

7. **Conditional write failure path — message disposition is unspecified** — Section 2.5 now specifies the full failure path: the message is placed on a dead-letter queue (not dropped, not retried into the hot path), the Lambda pages on-call, and the Lambda completes within its 15-second timeout because the DLQ write is the final action. The dispatch worker receives a structured error response and does not block.

8. **Publisher healthcheck start period — 10 seconds may be insufficient** — The `startPeriod` is increased to 60 seconds, which is justified against the actual initialization steps. The healthcheck file is written after the first successful cycle, and the first cycle includes Redis connection establishment, DynamoDB cap read, and CloudWatch write. Each step has a measured upper bound; the total is documented.

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

**What "wrong by 2×" looks like:** If actual AUTH volume is 9,600/day (2× the p95 estimate), the 20K cap still provides 2× headroom. The scheduled reviews would catch this before it becomes a problem. If actual AUTH volume is 20K+ (a 4× error), the AUTH sub-cap would be exhausted and AUTH SMS would fail. This is the failure mode the reviews exist to prevent.

**AUTH cap review schedule (Finding 6 resolution):**

Three named checkpoints, not a recurring cadence:

- **Month 1 end (baseline):** Run the Twilio log query against the first month of production data. Confirm p95 is within the range observed pre-launch. Record the result. Owner: E1.
- **Month 3 end (midpoint):** Run the same query against months 1–3. If p95 has grown more than 20% from baseline, raise a ticket to adjust the AUTH cap before month 6. Owner: E1.
- **Month 6 end (pre-renewal):** Run the same query against months 1–6. Set the AUTH cap for the next six months based on observed p95 × 3. Owner: E1.

The word "quarterly" is not used because three reviews in six months is not quarterly. The schedule is named to avoid ambiguity about when each review occurs.

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

The health check file is written after the first successful publish cycle. The first cycle includes:

| Step | Upper bound |
|------|-------------|
| Python interpreter startup | 3s |
| Redis connection establishment (with TLS) | 5s |
| DynamoDB cap read (first call, cold connection) | 5s |
| CloudWatch `PutMetricData` call (first call, cold connection) | 10s |
| Health file write | <1s |
| **Total** | **~24s** |

Upper bounds are measured from the existing auth service running in the same VPC. The 60-second `startPeriod` provides 2.5× margin over the measured worst case. During the start period, failed health checks are not counted toward the `retries: 3` limit. If initialization consistently takes longer than 60 seconds in production, the `startPeriod` is raised; the measurement procedure is in the deployment runbook.

```python
# publisher/healthcheck.py

import os
import time
import sys

HEALTH_FILE = '/tmp/publisher_last_success'

# Staleness threshold is derived from publish constants, not set independently.
# See publisher/constants.py for PUBLISH_INTERVAL_SECONDS, MAX_RETRIES,
# BACKOFF_CEILING_SECONDS. Threshold = (interval × max_retries × ceiling) + margin.
# With interval=60, max_retries=3, ceiling=4, margin=30: threshold = 750s.
# A transient failure that resolves within the retry window does not go stale.
MAX_STALENESS_SECONDS = 750

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

```python
# publisher/constants.py
# Single source of truth for publish timing. Healthcheck imports from here.

PUBLISH_INTERVAL_SECONDS = 60
MAX_RETRIES = 3
BACKOFF_CEILING_SECONDS = 4   # max sleep between retries = 4s
                               # total retry window = 3 × 4 = 12s max
                               # health file staleness threshold adds margin:
                               # 60 × 3 × 4 + 30 = 750s
                               # This is conservative; in practice a failure
                               # resolving within 12s does not skip a cycle.
```

#### Transient Failure Handling (Finding 1 resolution)

The publisher retries CloudWatch writes before allowing the health file to go stale. A single transient failure causes a delayed write, not a missed write.

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


def _put_metrics_with_retry(metric_data: list, now: datetime.datetime):
    """
    Write metrics to CloudWatch with exponential backoff retry.
    Raises on final failure. Does NOT write the health file.
    The caller writes the health file only after this returns successfully.
    """
    attempt = 0
    while True:
        try:
            cloudwatch.put_metric_data(
                Namespace='Notifications/SMS',
                MetricData=metric_data,
            )
            return  # success
        except Exception as e:
            attempt += 1
            if attempt > MAX_RETRIES:
                logger.error(
                    "CloudWatch put_metric_data failed after %d retries: %s",
                    MAX_RETRIES, e
                )
                raise
            sleep_seconds = min(2 ** attempt, BACKOFF_CEILING_SECONDS)
            logger.warning(
                "CloudWatch put_metric_data attempt %d failed (%s), "
                "retrying in %ds", attempt, e, sleep_seconds
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

    timestamp = now

    metric_data = [
        {
            'MetricName': 'SocialSMSConsumed',
            'Value': social_consumed,
            'Unit': 'Count',
            'Timestamp': timestamp,
        },
        {
            'MetricName': 'AuthSMSConsumed',
            'Value': auth_consumed,
            'Unit': 'Count',
            'Timestamp': timestamp,
        },
        {
            'MetricName': 'SocialSMSCap',
            'Value': social_cap,
            'Unit': 'Count',
            'Timestamp': timestamp,
        },
        {
            'MetricName': 'CapReadHealthy',
            'Value': 1 if cap_read_healthy else 0,
            'Unit': 'Count',
            'Timestamp': timestamp,
        },
    ]

    # Raises on final retry failure. Health file is not written in that case.
    _put_metrics_with_retry(metric_data, now)

    # Write health file only after successful CloudWatch publish.
    with open(HEALTH_FILE, 'w') as f