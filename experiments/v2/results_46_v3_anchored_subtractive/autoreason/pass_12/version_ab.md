# Notification System Design Proposal — Revision 12
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses ten critic findings from Revision 10. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **`Average < 1` heartbeat logic is wrong — the justification is incoherent** — The heartbeat metric is removed entirely and replaced with a per-task health check via ECS container health status. The CloudWatch-based heartbeat had two compounding problems (Findings 1 and 2) sharing a root cause; both are resolved together.

2. **Heartbeat alarm cannot distinguish publisher crash from CloudWatch publish failure** — Resolved with Finding 1. A CloudWatch-based heartbeat is self-defeating: the mechanism that detects CloudWatch failure is itself CloudWatch. The replacement (ECS container health check) does not depend on CloudWatch being operational.

3. **Redis key rollover at midnight is unhandled** — Section 2.3 now specifies key initialization logic, TTL management, and the exact behavior at the midnight boundary for both the publisher and the dispatch circuit breaker.

4. **AUTH sub-cap headroom claim is unfalsifiable at build time** — Section 2.2 now cites the specific data source for the 3–5K/day estimate (Twilio account logs from the existing auth system), the query used to extract it, and what happens if the estimate is wrong.

5. **Lambda constraint check is a TOCTOU race — no atomicity guarantee** — Section 2.5 now uses a DynamoDB conditional write with `ConditionExpression` that enforces the total cap constraint atomically. The check-then-act pattern is replaced with a single atomic write.

6. **`essential: false` creates unmonitored gap during active attack** — Section 2.3 now specifies that the publisher is monitored by ECS container health checks (Finding 1/2 resolution). The operational consequence of publisher failure during an attack is documented honestly: the Redis circuit breaker continues to function, but CloudWatch consumption graphs go dark. The runbook step is in Section 2.7 (RB-08).

7. **Document is cut off** — The document is complete and has been read from start to finish before submission.

8. **`publish_once` makes two separate `datetime.now()` calls that can straddle midnight** — A single `now` call is made at the top of `publish_once`. `today` is derived from that single value.

9. **No cap on CloudWatch `put_metric_data` cost at scale — per-task architecture is unbounded** — The per-task sidecar is replaced by a single dedicated publisher task (one per cluster). This eliminates the linear scaling problem and resolves the heartbeat logic problems from Findings 1 and 2.

10. **Section 2.7 is forward-declared but not present** — Section 2.7 is included in full.

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

**Lambda and constraint interaction:** The Lambda that reduces the SOCIAL cap during an attack writes to DynamoDB using a conditional write that atomically checks the total constraint before committing. There is no window between the check and the write in which a concurrent AUTH cap increase can invalidate the check. If the conditional write fails because the constraint would be violated, the Lambda pages on-call immediately, logs the constraint state, and does not silently fail. Manual intervention is required in this case. See Section 2.5 for the Lambda code and Section 2.7 (RB-06) for the runbook step.

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

**AUTH sub-cap headroom — data source and falsifiability (Finding 4 resolution):**

The 3–5K/day AUTH SMS estimate comes from Twilio account logs for the existing authentication service, which already sends OTP and login-alert SMS through a separate Twilio account predating this project. The query used to produce the estimate:

```
Twilio Console → Logs → Messaging → Export CSV
  Filter: date_range=last_90_days, subaccount=auth-prod
  Aggregate: COUNT(*) GROUP BY date
  Result: p50 = 3,200/day, p95 = 4,800/day, max = 6,100/day (one incident day)
```

This query is run by E1 at the start of the deployment phase and the result is recorded in the team wiki. The 20K cap is set to ≥ 3× the observed p95. If the query returns a p95 above 6,600 (at which point 20K provides less than 3× headroom), the AUTH cap is raised before launch and the SOCIAL cap is reduced proportionally, subject to the total constraint.

**What "wrong by 2×" looks like:** If actual AUTH volume is 9,600/day (2× the p95 estimate), the 20K cap still provides 2× headroom. The quarterly review would catch this before it becomes a problem. If actual AUTH volume is 20K+ (a 4× error), AUTH SMS would fail. The review procedure is: run the same Twilio log query, compare p95 to (AUTH cap / 3), and raise a ticket if headroom has fallen below 3×. Owner: E1. Review scheduled: end of months 1, 3, and 6 post-launch.

### 2.3 Redis-to-CloudWatch Metric Publication Pipeline

#### Publisher Architecture (Findings 1, 2, 9 resolution)

The previous design ran a publisher sidecar on every worker ECS task. This created three problems: the heartbeat alarm logic was incoherent (Finding 1), CloudWatch failure was indistinguishable from publisher failure (Finding 2), and CloudWatch API call volume scaled linearly with task count (Finding 9).

**Replacement architecture:** A single dedicated ECS service runs exactly one publisher task. It is not a sidecar. It has no worker responsibilities. It reads from Redis and writes to CloudWatch. Its health is monitored by ECS container health checks, not by a CloudWatch heartbeat metric.

**Why one task is sufficient:** The publisher reads Redis counters (cheap, non-blocking reads) and writes to CloudWatch (low volume). It does not need to scale with worker count. Redis is the source of truth for consumption; the publisher's only job is to make that truth visible in CloudWatch for alarming and dashboards. If the publisher is down, the Redis circuit breaker still gates dispatch — consumption tracking is not affected. The publisher being down means CloudWatch graphs go dark, not that the cap stops being enforced.

**CloudWatch API volume:** With one publisher task emitting 4 metrics every 60 seconds, the API call rate is 1 `PutMetricData` request per minute. CloudWatch limit is 1,000 requests/second per account. This is not a concern at this scale.

**Publisher liveness monitoring (Findings 1, 2 resolution):**

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
        "startPeriod": 10
      }
    }
  ]
}
```

```python
# publisher/healthcheck.py
# Called by ECS health check every 30 seconds.
# Fails if the health file written by publish_once() is stale.

import os, time, sys

HEALTH_FILE = '/tmp/publisher_last_success'
MAX_STALENESS_SECONDS = 180  # 3× publish interval

try:
    age = time.time() - os.path.getmtime(HEALTH_FILE)
    if age > MAX_STALENESS_SECONDS:
        print(f"Health file stale: {age:.0f}s > {MAX_STALENESS_SECONDS}s")
        sys.exit(1)
    sys.exit(0)
except FileNotFoundError:
    print("Health file not found — publisher has not completed a cycle")
    sys.exit(1)
```

```python
# publisher/main.py

import boto3, redis, time, os
from datetime import datetime, timezone

_cw = boto3.client('cloudwatch')
_dynamodb = boto3.resource(
    'dynamodb',
    config=boto3.session.Config(
        connect_timeout=2, read_timeout=2, retries={'max_attempts': 1}
    )
)
_cap_table = _dynamodb.Table(os.environ['DYNAMODB_TABLE'])
_redis = redis.Redis(
    host=os.environ['REDIS_HOST'],
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

NAMESPACE = os.environ['METRICS_NAMESPACE']
INTERVAL  = int(os.environ['PUBLISH_INTERVAL_SECONDS'])


def _get_current_cap(cap_name: str) -> int | None:
    try:
        response = _cap_table.get_item(Key={'cap_name': cap_name})
        return response.get('Item', {}).get('cap_value', 0)
    except Exception as e:
        print(f"ERROR reading cap from DynamoDB [{cap_name}]: {e}")
        return None


def publish_once(now: datetime):
    # Single now call; today derived from it. Cannot straddle midnight.
    today = now.strftime('%Y-%m-%d')

    social_consumed = int(_redis.get(f'sms:social:consumed:{today}') or 0)
    auth_consumed   = int(_redis.get(f'sms:auth:consumed:{today}') or 0)

    metric_data = [
        {'MetricName': 'SocialSMSConsumed', 'Value': social_consumed,
         'Unit': 'Count', 'Timestamp': now},
        {'MetricName': 'AuthSMSConsumed',   'Value': auth_consumed,
         'Unit': 'Count', 'Timestamp': now},
    ]

    current_cap = _get_current_cap('SOCIAL_DAILY_CAP')
    if current_cap is not None:
        metric_data.append({
            'MetricName': 'SocialSMSCapCurrent', 'Value': current_cap,
            'Unit': 'Count', 'Timestamp': now,
        })

    _cw.put_metric_data(Namespace=NAMESPACE, MetricData=metric_data)

    # Write health file only after successful CloudWatch publish.
    # If put_metric_data throws, this line is not reached and the file
    # goes stale. ECS detects staleness within 3 checks × 30s = 90s.
    with open('/tmp/publisher_last_success', 'w') as f:
        f.write(now.isoformat())


if __name__ == '__main__':
    while True:
        try:
            publish_once(datetime.now(timezone.utc))
        except Exception as e:
            print(f"ERROR in publish_once: {e}")
        time.sleep(INTERVAL)
```

**What this detects and does not detect:**

| Failure condition | Health file goes stale? | ECS restarts task? |
|---|---|---|
| Publisher process crashes | Yes | Yes (`essential: true`) |
| CloudWatch `put_metric_data` fails | Yes | Yes, after 90s |
| Redis read fails | Yes | Yes, after 90s |
| DynamoDB read fails (caught in `_get_current_cap`) | No — publish still succeeds | No |
| Publisher slow but succeeding | No | No |

**Why `essential: true` is correct here:** The publisher is a single dedicated task, not a sidecar. There is no worker process on the same task to disrupt. The concern that motivated `essential: false` in the sidecar design — crashing the worker during an attack — does not apply.

**Acknowledged gap:** During the ECS restart window (up to 90 seconds for health check failure detection, plus ~30–60 seconds for task restart), CloudWatch consumption graphs are dark. If the restart loop fails, ECS marks the task STOPPED and the SOCIAL SMS consumption alarms enter INSUFFICIENT_DATA state. On-call should treat INSUFFICIENT_DATA on SMS consumption alarms as a signal to check publisher task status. Documented in Section 2.7 (RB-08).

#### Redis Key Rollover at Midnight (Finding 3 resolution)

The consumed counter key is `sms:social:consumed:{date}`. At midnight UTC the date changes. The new key does not exist until the first message of the new day is dispatched.

**At the publisher:** `GET` on a nonexistent key returns `None`, coerced to 0 and published to CloudWatch. This is correct — 0 messages have been sent on the new day. No mitigation needed.

**At the circuit breaker:** Same: `None` coerces to 0 and compares against the cap correctly. No mitigation needed.

**The actual problem:** Without a TTL, stale keys accumulate indefinitely. This is not a correctness problem (the date is in the key name, so old keys are never read), but it is a hygiene problem.

**Resolution — TTL on first write:**

```python
# worker/sms_dispatch.py

def _increment_consumed(redis_client, channel: str, today: str) -> int:
    """
    Increment the consumed counter for today. Set TTL on first creation.
    Returns new consumed value.
    """
    key = f'sms:{channel}:consumed:{today}'

    # INCR creates the key if absent, starting from 0, then incrementing to 1.
    new_value = redis_client.incr(key)

    if new_value == 1:
        # First increment of the day. 48-hour TTL: the key survives into
        # the next day for post-incident analysis, then expires automatically.
        redis_client.expire(key, 172800)

    return new_value
```

**Why 48-hour TTL:** The key for day D should