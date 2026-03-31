# Notification System Design Proposal — Revision 9
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses nine critic findings from Revision 8. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **Redis failure gap: the independent Redis alarm is asserted but never defined** — The Redis alarm is now fully specified: metric, threshold, evaluation period, and action. The partial-failure (elevated latency) case is addressed with a separate latency alarm. The gap between "publisher emits zero" and "Redis alarm fires" is quantified, and the residual risk is stated explicitly.

2. **Document ends mid-sentence again — Section 2.8 calculation is never completed** — Section 2.8 is completed. The 200-account attack calculation is carried through to a detection window estimate with a stated range and the assumptions behind it.

3. **22:00 UTC guard is arbitrary and not derived from actual usage patterns** — The 22:00 threshold is replaced with a data-driven threshold derived from the 3× peak multiplier defined in Section 1. The derivation is shown. The user base timezone assumption is stated explicitly and flagged as a required input from the product team before deployment.

4. **ConditionExpression only checks for the normal value; intermediate values are silently mishandled** — The Lambda now reads the current cap value before acting and logs it. The `ConditionalCheckFailedException` handler now distinguishes between "already at reduced value" and "at some other value," and pages on-call in the latter case.

5. **RB-07 requires manual console edits with no validation and references an undefined CloudWatch metric** — RB-07 is replaced with a script-based runbook that validates input, rejects out-of-range values, and prints the confirmed post-write value. The `SocialSMSCapCurrent` metric is defined in Section 2.3.

6. **AUTH fallback behavior for users without a verified email is unspecified** — The system behavior for each user state (has verified email, has unverified email, has no email) is now specified explicitly. No case is left undefined.

7. **No enforcement mechanism keeps AUTH + SOCIAL ≤ 100K when caps are adjusted independently** — A hard enforcement check is added at the DynamoDB write layer. Any adjustment that would cause AUTH + SOCIAL > 100K is rejected with an explicit error before the write occurs.

8. **Quarterly and monthly review processes are defined by reference only** — Both processes are now defined in full in Section 2.9: who conducts them, what data is reviewed, what triggers an adjustment, and what the adjustment procedure is.

9. **`essential: true` on the publisher sidecar creates a restart amplification problem during active attacks** — `essential: true` is removed. The publisher sidecar is set to `essential: false`. The tradeoff is stated: a publisher crash now allows the worker to continue processing, but the heartbeat alarm fires within 3 minutes, paging on-call. The silent-failure window is bounded and accepted.

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

The alarm structure depends on CloudWatch gauge metrics reflecting the current values of `sms:social:consumed:{date}` and `sms:auth:consumed:{date}`. This section specifies the publisher, its failure modes, its own monitoring, and the Redis alarms that the prior revision asserted but did not define.

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
      - name: PUBLISH_INTERVAL_SECONDS
        value: "60"
      - name: METRICS_NAMESPACE
        value: "NotificationSystem/SMS"
    essential: false   # See Section 2.3, Finding 9 resolution.
```

**Why `essential: false`:** Setting `essential: true` would restart the entire ECS task — including the worker — whenever the publisher crashes. During an active attack, repeated publisher crashes would repeatedly interrupt in-flight message processing, causing message loss or duplicate delivery at exactly the moment operational stability is most needed. `essential: false` allows the worker to continue processing when the publisher crashes. The cost is that a publisher crash is now a silent failure until the heartbeat alarm fires. That window is bounded at 3 minutes (3 missed heartbeats × 60 seconds). On-call is paged within 3 minutes. This is accepted as preferable to worker instability during attacks.

```python
# publisher/main.py

import boto3, redis, time, os
from datetime import datetime, timezone

cw = boto3.client('cloudwatch')
r = redis.Redis(
    host=os.environ['REDIS_HOST'],
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)
NAMESPACE = os.environ['METRICS_NAMESPACE']
INTERVAL = int(os.environ['PUBLISH_INTERVAL_SECONDS'])

def publish_once():
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    social_consumed = int(r.get(f'sms:social:consumed:{today}') or 0)
    auth_consumed   = int(r.get(f'sms:auth:consumed:{today}') or 0)
    now = datetime.now(timezone.utc)

    cw.put_metric_data(
        Namespace=NAMESPACE,
        MetricData=[
            {'MetricName': 'SocialSMSConsumed', 'Value': social_consumed,
             'Unit': 'Count', 'Timestamp': now},
            {'MetricName': 'AuthSMSConsumed', 'Value': auth_consumed,
             'Unit': 'Count', 'Timestamp': now},
            {'MetricName': 'SocialSMSCapCurrent',
             'Value': _get_current_cap('SOCIAL_DAILY_CAP'),
             'Unit': 'Count', 'Timestamp': now},
            {'MetricName': 'PublisherHeartbeat', 'Value': 1,
             'Unit': 'Count', 'Timestamp': now},
        ]
    )

def _get_current_cap(cap_name: str) -> int:
    """Read current cap value from DynamoDB for dashboard visibility."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('sms_cap_config')
    response = table.get_item(Key={'cap_name': cap_name})
    return response.get('Item', {}).get('cap_value', 0)

if __name__ == '__main__':
    while True:
        try:
            publish_once()
        except Exception as e:
            # Log but do not crash. A sustained failure causes
            # PublisherHeartbeat to stop arriving, triggering the alarm below.
            print(f"ERROR publishing metrics: {e}")
        time.sleep(INTERVAL)
```

**`SocialSMSCapCurrent` metric definition:** This metric is emitted by the publisher every 60 seconds. Its value is the current `cap_value` for `SOCIAL_DAILY_CAP` in DynamoDB. It is used in RB-07 (Section 2.7) to verify that a cap restoration write has taken effect. It is visible in the SMS Operations dashboard alongside `SocialSMSConsumed`.

**Publisher monitoring:**

```
Alarm: SMS_METRIC_PUBLISHER_DEAD
  Metric: NotificationSystem/SMS / PublisherHeartbeat
  Statistic: Sum
  Period: 60 seconds
  Evaluation periods: 3
  Threshold: < 1
  Missing data treatment: BREACHING
  Action: Page on-call immediately.
  Consequence: If this alarm fires, the consumption-based circuit breaker
               is blind. On-call must check Redis or Twilio dashboards
               directly until the publisher is restored.
```

**Redis alarms (previously asserted but not defined):**

The prior revision stated that Redis failure is "independently alarmed" without defining those alarms. They are defined here.

```
Alarm: REDIS_CONNECTION_FAILURE
  Metric: AWS/ElastiCache / CacheClusterStatus
           (or application-level metric: NotificationSystem/Redis /
            ConnectionErrors, emitted by the worker on each failed
            Redis operation)
  Statistic: Sum
  Period: 60 seconds
  Evaluation periods: 2
  Threshold: > 5 connection errors in 60 seconds
  Missing data treatment: NOT_BREACHING
  Action: Page on-call immediately.
  Consequence: If Redis is fully unavailable, SMS consumption counters
               stop incrementing. The circuit breaker is blind. Workers
               fall back to Twilio's own rate limits as the last line
               of defense.

Alarm: REDIS_LATENCY_HIGH
  Metric: AWS/ElastiCache / ReplicationLag
           (for replication lag as a latency proxy)
           AND application-level metric:
           NotificationSystem/Redis / CommandLatencyP99
  Statistic: p99
  Period: 60 seconds
  Evaluation periods: 3
  Threshold: > 50ms
  Missing data treatment: NOT_BREACHING
  Action: Page on-call. No automated action.
  Consequence: High latency means Redis reads in the publisher may
               time out (socket_timeout=2s in publisher code). The
               publisher will log an error and emit no metric for that
               interval. If this persists for 3 intervals,
               SMS_METRIC_PUBLISHER_DEAD fires.
```

**Residual gap — partial Redis failure:** If Redis is degraded but not fully failed (latency between 2ms and 2000ms, occasional timeouts), the publisher may emit 0 for consumed metrics on some intervals while the heartbeat still arrives. `SMS_METRIC_PUBLISHER_DEAD` does not fire. `REDIS_LATENCY_HIGH` fires at p99 > 50ms, which is well below the 2000ms timeout, so on-call is paged before the publisher begins timing out. The window between "Redis becomes slow" and "REDIS_LATENCY_HIGH fires" is at most 3 minutes (3 evaluation periods). During that window, the circuit breaker may undercount consumption. This gap is accepted. The alternative — making the publisher crash on any Redis error — reintroduces the worker-restart amplification problem described above.

**Failure mode summary:**

| Condition | SocialSMSConsumed | PublisherHeartbeat | Alarm state |
|---|---|---|---|
| Normal operation | Rising slowly | Present every 60s | No alarms |
| Active attack | Rising rapidly | Present every 60s | Consumption alarms fire |
| Publisher crashed | Flat (stale) | Absent | SMS_METRIC_PUBLISHER_DEAD fires ≤3 min |
| Redis fully failed | Flat (zero) | Absent after timeout | SMS_METRIC_PUBLISHER_DEAD fires; REDIS_CONNECTION_FAILURE fires |
| Redis slow (p99 >50ms) | May drop to 0 intermittently | Present | REDIS_LATENCY_HIGH fires ≤3 min |
| Redis slow (p99 <50ms, occasional drops) | Occasionally underreported | Present | No alarm — residual gap, accepted |

### 2.4 Pre-Depletion Circuit Breaker

```
Cap consumption tracking:
  Redis key: sms:social:consumed:{date}  (incremented at dispatch)
  Redis key: sms:auth:consumed:{date}    (incremented at dispatch)
  Both keys expire at midnight UTC.

Circuit breaker thresholds:

  SOCIAL sub-cap (80K/day):
    75% (60K consumed):
      Alarm: SMS_SOCIAL_75PCT_CONSUMED
      Action: Page on-call. No automated cap change.

    90% (72K consumed):
      Alarm: SMS_SOCIAL_90PCT_CONSUMED
      Action: Lambda fires. See time-of-day guard in Section 2.5.

  AUTH sub-cap (20K/day):
    80% (16K consumed):
      Alarm: SMS_AUTH_80PCT_CONSUMED
      Action: Page on-call. No automated cap change.

    90% (18K consumed):
      Alarm: SMS_AUTH_90PCT_CONSUMED
      Action: Automated AUTH fallback fires. See Section 2.6.
```

### 2.5 Time-of-Day Guard on SOCIAL Lambda (Findings 3 and 4)

**Prior revision's 22:00 UTC threshold retracted:** The prior revision used 22:00 UTC as a cutoff, justified by linear consumption math (80K × 22/24 ≈ 73K). This is inconsistent with the 3× peak multiplier defined in Section 1 and was not derived from actual usage patterns.

**Required input before deployment:** The threshold derived below depends on knowing when peak traffic occurs in UTC. This is a required input from the product team. The placeholder value used in this document is noted as a placeholder and must be replaced with measured data before the guard goes live. Deploying with an uncalibrated threshold is explicitly called out as a launch-blocking item in Section 4.

**Threshold derivation from Section 1 peak multiplier:**

Section 1 defines a 3× peak multiplier. If average consumption rate is R messages/hour (80K / 24 ≈ 3,333/hour), peak consumption rate is 3R ≈ 10,000/hour. Cumulative consumption at hour H depends on when peaks occur. For a social app with a primary user base in the Americas, typical peak periods are: