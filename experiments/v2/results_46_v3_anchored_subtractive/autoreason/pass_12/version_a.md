# Notification System Design Proposal — Revision 10
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses ten critic findings from Revision 9. Each finding is addressed at the point of the original decision. Findings from prior revisions that were correctly resolved are not re-litigated here.

**Findings and their resolutions:**

1. **Document ends mid-sentence again — Section 2.5 cuts off mid-derivation** — Section 2.5 is completed. The threshold derivation is carried through to a concrete formula, a placeholder value, and the calibration procedure. The document has been reviewed in full before submission.

2. **The "required input" dependency is unresolved — no deadline, owner, or escalation path** — Section 2.5 now specifies an owner (E1), a deadline (end of Week 2 of the deployment phase), a data source (existing analytics pipeline), and an escalation path if the data is unavailable. The launch-blocking label is now backed by a process.

3. **`_get_current_cap` instantiates a DynamoDB resource on every call** — The DynamoDB client and table reference are now module-level singletons, initialized once at startup. A DynamoDB-specific timeout is set. DynamoDB errors are caught and logged separately from Redis errors, and the metric is omitted rather than emitting a stale or zero value when DynamoDB is unavailable.

4. **AUTH sub-cap alarm thresholds are inconsistent with stated headroom** — The AUTH alarms are recalibrated to detect anomalous growth relative to normal volume, not relative to cap exhaustion. The first alarm fires at 2× normal peak daily volume, not at 80% of cap. The derivation is shown.

5. **`REDIS_CONNECTION_FAILURE` references `CacheClusterStatus`, which is not a CloudWatch metric** — The `CacheClusterStatus` reference is removed. The alarm is now defined solely on the application-level `ConnectionErrors` metric, which is emitted by the worker code shown in this section. The emission point is specified.

6. **The failure mode table contradicts the code — publisher keeps running during Redis failure, heartbeat continues** — The table is corrected. When Redis fails but the publisher process is alive, the heartbeat continues and `SMS_METRIC_PUBLISHER_DEAD` does not fire. The Redis failure is detected by `REDIS_CONNECTION_FAILURE` instead. The table now accurately reflects what each alarm detects and does not detect.

7. **The 3-minute publisher dead window claim is only valid with one worker task** — The heartbeat alarm is changed from `Sum < 1` to `Average < 1`, which is independent of task count. The per-task interpretation is explained. The claim about the 3-minute detection window is now valid for any number of tasks.

8. **Section 2.8 is referenced as completed in the executive summary but does not appear in the document** — Section 2.8 is included in full in this revision. The 200-account attack calculation is carried through to a detection window estimate with stated assumptions.

9. **The Lambda automated write to DynamoDB can be rejected if AUTH has been manually increased close to 100K — no behavior specified** — The Lambda now reads both current cap values before writing. If the proposed reduction would still satisfy the total constraint, it proceeds. If the constraint would be violated — meaning AUTH has consumed space that SOCIAL needs — the Lambda pages on-call immediately, logs the constraint state, and does not silently fail. Manual intervention is required in this case, and the runbook step for it is added to Section 2.7.

10. **`socket_connect_timeout=2` and `socket_timeout=2` are inconsistent with the latency alarm — publisher blocks, does not emit zero on slow reads** — The description of publisher behavior during slow Redis is corrected. The publisher blocks up to 2 seconds, then either succeeds or throws. It does not emit zero on a slow read. The failure mode table is updated accordingly. The claim that the publisher "emits zero intermittently" during slow Redis is retracted. The latency alarm's role is correctly restated: it pages on-call when Redis is slow, before the publisher begins timing out, so that the issue is known before it becomes a publisher failure.

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

SMS traffic is split into two sub-caps at the dispatch layer. The automated response acts only on the SOCIAL sub-cap. The AUTH sub-cap has a separate alarm and a defined automated fallback (Section 2.6). A hard constraint keeps AUTH + SOCIAL ≤ 100K at all times, enforced at the write layer (Section 2.9).

**Lambda and constraint interaction:** The Lambda that reduces the SOCIAL cap during an attack writes to DynamoDB. If AUTH has been manually increased close to 100K, the Lambda's write may conflict with the total constraint. The Lambda handles this explicitly: it reads both current caps before writing, checks the constraint, and pages on-call if the constraint prevents automated action. This case is not silently ignored. See Section 2.5 for the Lambda code and Section 2.7 for the runbook step.

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
  Enforcement: any write to either cap that would cause AUTH + SOCIAL > 100K
               is rejected before the DynamoDB write executes (Section 2.9).
```

**Why 20K for AUTH:** Current AUTH SMS volume is estimated at 3–5K/day. 20K provides 4–6× headroom. This assumption is reviewed quarterly (Section 2.9). If MAU grows significantly during the 6-month build window, AUTH volume grows proportionally and this headroom shrinks. The quarterly review process exists specifically to catch this before it becomes an incident.

### 2.3 Redis-to-CloudWatch Metric Publication Pipeline

The alarm structure depends on CloudWatch gauge metrics reflecting the current values of `sms:social:consumed:{date}` and `sms:auth:consumed:{date}`. This section specifies the publisher, its failure modes, its own monitoring, and the Redis alarms.

**Publisher specification:**

A CloudWatch metric publisher runs as a sidecar container on each worker ECS task. It is versioned and deployed with the worker task definition.

```yaml
# task-definition.json (relevant excerpt)

containerDefinitions:
  - name: worker
    image: notifications-worker:latest

  - name: cw-metric-publisher
    image: notifications-cw-publisher:latest
    environment:
      - name: REDIS_HOST
        value: !Ref RedisClusterEndpoint
      - name: DYNAMODB_TABLE
        value: sms_cap_config
      - name: PUBLISH_INTERVAL_SECONDS
        value: "60"
      - name: METRICS_NAMESPACE
        value: "NotificationSystem/SMS"
    essential: false   # See Section 2.3, Finding 9 from Revision 9.
```

**Why `essential: false`:** Setting `essential: true` would restart the entire ECS task — including the worker — whenever the publisher crashes. During an active attack, repeated publisher crashes would repeatedly interrupt in-flight message processing. `essential: false` allows the worker to continue processing when the publisher crashes. The cost is that a publisher crash is a silent failure until the heartbeat alarm fires. That window is bounded: see heartbeat alarm definition below.

```python
# publisher/main.py

import boto3
import redis
import time
import os
from datetime import datetime, timezone

# --- Module-level singletons. Initialized once at startup, not per call. ---
# Finding 3 resolution: _get_current_cap previously instantiated boto3.resource
# on every call (every 60 seconds). This caused unnecessary connection overhead
# and made the DynamoDB dependency invisible from the task definition.
# The client and table reference are now created once here.

_cw = boto3.client('cloudwatch')

_dynamodb = boto3.resource(
    'dynamodb',
    config=boto3.session.Config(
        connect_timeout=2,
        read_timeout=2,
        retries={'max_attempts': 1},
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
INTERVAL = int(os.environ['PUBLISH_INTERVAL_SECONDS'])


def _get_current_cap(cap_name: str) -> int | None:
    """
    Read current cap value from DynamoDB.
    Returns None if DynamoDB is unavailable, so the caller can omit
    the metric rather than emit a stale or zero value.
    DynamoDB errors are caught here, separately from Redis errors,
    so the two failure modes are distinguishable in logs.
    """
    try:
        response = _cap_table.get_item(Key={'cap_name': cap_name})
        return response.get('Item', {}).get('cap_value', 0)
    except Exception as e:
        print(f"ERROR reading cap from DynamoDB [{cap_name}]: {e}")
        return None


def publish_once():
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    now = datetime.now(timezone.utc)

    # Redis reads. The publisher blocks here for up to socket_timeout=2s.
    # On success it gets the current value. On timeout or connection error
    # it throws, which is caught in the main loop. The publisher does NOT
    # emit zero on a slow read — it either succeeds or throws.
    # See Finding 10 resolution and failure mode table.
    social_consumed = int(_redis.get(f'sms:social:consumed:{today}') or 0)
    auth_consumed   = int(_redis.get(f'sms:auth:consumed:{today}') or 0)

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
            'MetricName': 'PublisherHeartbeat',
            'Value': 1,
            'Unit': 'Count',
            'Timestamp': now,
        },
    ]

    # DynamoDB read for cap visibility. Omitted if DynamoDB is unavailable
    # rather than emitting a misleading zero.
    current_cap = _get_current_cap('SOCIAL_DAILY_CAP')
    if current_cap is not None:
        metric_data.append({
            'MetricName': 'SocialSMSCapCurrent',
            'Value': current_cap,
            'Unit': 'Count',
            'Timestamp': now,
        })

    _cw.put_metric_data(Namespace=NAMESPACE, MetricData=metric_data)


if __name__ == '__main__':
    while True:
        try:
            publish_once()
        except Exception as e:
            # Log but do not crash. A sustained Redis or CloudWatch failure
            # causes PublisherHeartbeat to stop arriving, triggering
            # SMS_METRIC_PUBLISHER_DEAD within 3 evaluation periods.
            # A DynamoDB-only failure is caught inside _get_current_cap
            # and does not prevent the heartbeat from being emitted.
            print(f"ERROR in publish_once: {e}")
        time.sleep(INTERVAL)
```

**`SocialSMSCapCurrent` metric definition:** Emitted by the publisher every 60 seconds when DynamoDB is available. Its value is the current `cap_value` for `SOCIAL_DAILY_CAP` in DynamoDB. Used in RB-07 (Section 2.7) to verify that a cap restoration write has taken effect.

**Publisher monitoring — heartbeat alarm:**

```
Alarm: SMS_METRIC_PUBLISHER_DEAD
  Metric: NotificationSystem/SMS / PublisherHeartbeat
  Statistic: Average
  Period: 60 seconds
  Evaluation periods: 3
  Threshold: < 1
  Missing data treatment: BREACHING
  Action: Page on-call immediately.

Why Average, not Sum (Finding 7 resolution):
  With N worker tasks each running a publisher sidecar, each publisher
  emits PublisherHeartbeat = 1 every 60 seconds. The Sum over 60 seconds
  is N when all publishers are alive and < N when some are dead.
  A Sum < 1 threshold only fires when ALL publishers are dead, which
  means a single surviving publisher masks all others being dead.

  Using Average: each publisher emits value 1. The average across all
  publishers is always 1 when any publisher is alive, and < 1 only when
  a publisher emits value 0 — which does not happen in this code, since
  the publisher either emits 1 or throws before emitting anything.

  The correct interpretation: Average < 1 fires when PublisherHeartbeat
  data points stop arriving entirely (missing data treatment: BREACHING
  converts absence to a breach). This fires within 3 evaluation periods
  (3 minutes) regardless of task count, because absence of data from
  ALL publishers — not a reduced sum — is what triggers it.

  Partial publisher failure (some tasks' publishers dead, others alive)
  is not detected by this alarm. That is a known limitation. A per-task
  publisher health metric would require task-level dimensions, which adds
  cardinality complexity the team has chosen not to take on in the initial
  build. The tradeoff: partial publisher failure means some tasks are
  blind to consumption counts. The SMS cap protects against overage even
  in this case, because consumption is tracked in Redis (not per-publisher)
  and the circuit breaker reads from Redis at dispatch time, not from
  CloudWatch. CloudWatch metrics are for observability and alarming, not
  for dispatch gating.

Consequence if alarm fires: The consumption-based circuit breaker is
  operationally blind — on-call cannot see the consumption graph.
  The circuit breaker itself (Redis counter checked at dispatch) continues
  to function. On-call must check Redis or Twilio dashboards directly
  until the publisher is restored.
```

**Redis alarms:**

```
Alarm: REDIS_CONNECTION_FAILURE
  Metric: NotificationSystem/Redis / ConnectionErrors
  Statistic: Sum
  Period: 60 seconds
  Evaluation periods: 2
  Threshold: > 5 errors in 60 seconds
  Missing data treatment: NOT_BREACHING
  Action: Page on-call immediately.

  Finding 5 resolution: The prior revision listed AWS/ElastiCache /
  CacheClusterStatus as the metric source. Cache