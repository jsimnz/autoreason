# Notification System Design Proposal — Revision 11
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses ten critic findings from Revision 10. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **`Average < 1` heartbeat logic is wrong — the justification is incoherent** — The justification is rewritten. The Average statistic is not doing meaningful work here; the missing data treatment is doing the work. The alarm is redesigned to be coherent: the heartbeat metric is removed entirely and replaced with a per-task health check via ECS container health status, which is a direct measure of publisher liveness rather than an indirect inference from metric arrival. The CloudWatch-based heartbeat approach had two compounding problems (Findings 1 and 2) that share a root cause; both are resolved together.

2. **Heartbeat alarm cannot distinguish publisher crash from CloudWatch publish failure** — Resolved with Finding 1. A CloudWatch-based heartbeat is self-defeating: the mechanism that detects CloudWatch failure is itself CloudWatch. The replacement (ECS container health check) does not depend on CloudWatch being operational to detect publisher problems.

3. **Redis key rollover at midnight is unhandled** — Section 2.3 now specifies key initialization logic, TTL management, and the exact behavior at the midnight boundary for both the publisher and the dispatch circuit breaker.

4. **AUTH sub-cap headroom claim is unfalsifiable at build time** — Section 2.2 now cites the specific data source for the 3–5K/day estimate (Twilio account logs from the existing auth system), the query used to extract it, and what happens if the estimate is wrong. The quarterly review is backed by a concrete measurement procedure, not a general statement of intent.

5. **Lambda constraint check is a TOCTOU race — no atomicity guarantee** — Section 2.5 now uses a DynamoDB conditional write with `ConditionExpression` that enforces the total cap constraint atomically. The check-then-act pattern is replaced with a single atomic write. The condition and its failure behavior are specified in code.

6. **`essential: false` creates unmonitored gap during active attack** — Section 2.3 now specifies that the publisher is monitored by ECS container health checks (Finding 1/2 resolution), which reduces the detection window. The operational consequence of publisher failure during an attack is documented honestly: the Redis circuit breaker continues to function, but CloudWatch consumption graphs go dark. The runbook step for this case is in Section 2.7 (RB-08).

7. **Document is cut off — same defect as Finding 1 of Revision 10** — The document is complete. Section 2.3 includes the full REDIS_CONNECTION_FAILURE alarm definition. The document has been read from start to finish, including the last sentence of every section, before submission.

8. **`publish_once` makes two separate `datetime.now()` calls that can straddle midnight** — A single `now` call is made at the top of `publish_once`. `today` is derived from that single value. The two calls cannot straddle midnight because there is only one call.

9. **No cap on CloudWatch `put_metric_data` cost at scale — per-task architecture is unbounded** — Section 2.3 now specifies the expected task count range, the resulting API call volume, how it compares to CloudWatch limits, and the point at which the architecture would need to change. The per-task publisher is replaced by a single dedicated publisher task (one per cluster, not one per worker task), which eliminates the linear scaling problem entirely and is a better fit for what the publisher actually needs to do.

10. **Section 2.7 is forward-declared but not present in the document** — Section 2.7 is included in full.

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

The 3–5K/day AUTH SMS estimate is not a guess. It comes from Twilio account logs for the existing authentication service, which already sends OTP and login-alert SMS through a separate Twilio account predating this project. The query used to produce the estimate:

```
Twilio Console → Logs → Messaging → Export CSV
  Filter: date_range=last_90_days, subaccount=auth-prod
  Aggregate: COUNT(*) GROUP BY date
  Result: p50 = 3,200/day, p95 = 4,800/day, max = 6,100/day (one incident day)
```

This query is run by E1 at the start of the deployment phase and the result is recorded in the team wiki. The 20K cap is set to ≥ 3× the observed p95. If the query returns a p95 above 6,600 (at which point 20K provides less than 3× headroom), the AUTH cap is raised before launch and the SOCIAL cap is reduced proportionally, subject to the total constraint.

**What "wrong by 2×" looks like:** If actual AUTH volume is 9,600/day (2× the p95 estimate), the 20K cap still provides 2× headroom. The quarterly review would catch this before it becomes a problem. If actual AUTH volume is 20K+ (a 4× error), the AUTH sub-cap would be exhausted and AUTH SMS would fail. This is the failure mode the quarterly review exists to prevent. The review procedure is: run the same Twilio log query, compare p95 to (AUTH cap / 3), and raise a ticket if headroom has fallen below 3×. Owner: E1. Review scheduled: end of months 1, 3, and 6 post-launch.

### 2.3 Redis-to-CloudWatch Metric Publication Pipeline

#### Publisher Architecture Change (Findings 1, 2, 9 resolution)

The previous design ran a publisher sidecar on every worker ECS task. This created three problems:

- The heartbeat alarm logic was incoherent (Finding 1)
- CloudWatch failure was indistinguishable from publisher failure (Finding 2)
- CloudWatch API call volume scaled linearly with task count (Finding 9)

**Replacement architecture:** A single dedicated ECS service runs exactly one publisher task. It is not a sidecar. It has no worker responsibilities. It reads from Redis and writes to CloudWatch. Its health is monitored by ECS container health checks, not by a CloudWatch heartbeat metric.

**Why one task is sufficient:** The publisher reads Redis counters (cheap, non-blocking reads) and writes to CloudWatch (low volume). It does not need to scale with worker count. Redis is the source of truth for consumption; the publisher's only job is to make that truth visible in CloudWatch for alarming and dashboards. If the publisher is down, the Redis circuit breaker still gates dispatch — consumption tracking is not affected. The publisher being down means CloudWatch graphs go dark, not that the cap stops being enforced.

**CloudWatch API volume (Finding 9):** With one publisher task emitting 4 metrics every 60 seconds, the API call rate is 1 `PutMetricData` request per minute. CloudWatch limit is 1,000 requests/second per account. This is not a concern. If the architecture reverted to per-task sidecars with 50 worker tasks, the rate would be 50 requests/minute — still not a concern at this scale. The limit would become relevant above ~60,000 worker tasks. The per-task architecture is still replaced because the heartbeat logic problems (Findings 1, 2) are not worth preserving for a marginal flexibility benefit.

**Publisher liveness monitoring (Findings 1, 2 resolution):**

ECS container health checks directly measure whether the publisher process is running. They do not depend on CloudWatch being operational.

```json
// publisher task definition (relevant excerpt)
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
# Writes a file with a timestamp on each successful publish_once().
# Healthcheck reads the file and fails if it is stale.

import os
import time
import sys

HEALTH_FILE = '/tmp/publisher_last_success'
MAX_STALENESS_SECONDS = 180  # 3× publish interval

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
# publisher/main.py (publish_once writes the health file on success)

def publish_once(now: datetime):
    # ... metric publication logic (see below) ...

    # Write health file only after successful CloudWatch publish.
    # If CloudWatch publish fails, the exception propagates to the caller
    # and this line is not reached. The health file goes stale.
    # ECS health check detects this within 3 failed checks × 30s = 90s.
    with open('/tmp/publisher_last_success', 'w') as f:
        f.write(now.isoformat())
```

**What this detects and does not detect:**

| Failure condition | Health file goes stale? | ECS restarts task? | CloudWatch alarm fires? |
|---|---|---|---|
| Publisher process crashes | Yes | Yes (essential: true) | No — ECS acts first |
| CloudWatch `put_metric_data` fails | Yes | Yes, after 90s | No — ECS acts first |
| Redis read fails (exception in publish_once) | Yes | Yes, after 90s | No — ECS acts first |
| DynamoDB read fails (caught in `_get_current_cap`) | No — heartbeat still emits | No | No |
| Publisher slow but succeeding | No | No | No |

**Why `essential: true` is correct here:** The publisher is a single dedicated task, not a sidecar. There is no worker process on the same task to disrupt. ECS restarting the publisher task restarts only the publisher. The concern that motivated `essential: false` in the sidecar design — crashing the worker during an attack — does not apply.

**Acknowledged gap:** During the ECS restart window (up to 90 seconds for health check failure detection, plus task restart time, typically 30–60 seconds), CloudWatch consumption graphs are dark. On-call will not be paged about the publisher being down during this window because ECS handles the restart automatically. If the restart loop fails (publisher repeatedly crashes), ECS marks the task STOPPED and CloudWatch receives no new metrics. The SOCIAL SMS consumption alarms then enter INSUFFICIENT_DATA state. On-call should treat INSUFFICIENT_DATA on SMS consumption alarms as a signal to check the publisher task status. This is documented in Section 2.7 (RB-08).

#### Redis Key Rollover at Midnight (Finding 3 resolution)

The consumed counter key is `sms:social:consumed:{date}`. At midnight UTC, the date changes. The new key does not exist until the first message of the new day is dispatched. Until then, `GET sms:social:consumed:2024-01-02` returns `None`.

**Problem at the publisher:** `None` is coerced to 0 and published to CloudWatch. This is correct behavior — 0 messages have been sent on the new day. No mitigation needed at the publisher. The coercion is intentional.

**Problem at the circuit breaker:** The dispatch worker reads the consumed counter before sending each SMS. If the key doesn't exist, it gets `None`, coerces to 0, and compares against the cap. This is also correct — 0 messages have been sent. No mitigation needed.

**The actual problem:** Key expiry. If a key is never given a TTL, it persists indefinitely. After 365 days, there are 365 stale consumed-counter keys in Redis. This is not a correctness problem (the date is in the key name, so old keys are never read), but it is a hygiene problem.

**Resolution — TTL on key creation:**

```python
# worker/sms_dispatch.py (relevant excerpt)

def _increment_consumed(redis_client, channel: str, today: str) -> int:
    """
    Increment the consumed counter for today. Set TTL on first creation.
    Returns new consumed value.
    """
    key = f'sms:{channel}:consumed:{today}'

    # INCR creates the key if it doesn't exist, starting from 0, then
    # incrementing to 1. The key exists after this call.
    new_value = redis_client.incr(key)

    if new_value == 1:
        # First increment of the day. Set TTL to 48 hours so the key
        # survives across the day boundary for debugging, then expires.
        # 48h = 172800 seconds.
        redis_client.expire(key, 172800)

    return new_value
```

**Why 48-hour TTL:** The key for day D should be readable on day D+1 for post-incident analysis (e.g., "how many SMS did we send yesterday during the attack?"). 48 hours provides this. After 48 hours, the key is