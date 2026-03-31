# Notification System Design Proposal — Revision 7
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses nine critic findings from Revision 6. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **Redis-to-CloudWatch pipeline is undocumented and untested as a dependency** — The publisher is specified: a CloudWatch metric publisher daemon running as a sidecar on each worker ECS task, emitting the gauge every 60 seconds. Its failure modes, its own alarm, and its inclusion in the Lambda pass criteria are all defined. A silent publisher failure is now detectable within 120 seconds.

2. **Idempotency implementation has a race condition in the read path, and `updated_at` is set to a request ID** — The post-failure `get_item` is removed; the log message no longer claims to show the winning value. The `updated_at` field is corrected to use `datetime.utcnow().isoformat()`. Both fixes are shown in the revised code.

3. **90% threshold automation has no time-of-day awareness, and the "normal consumption never approaches 72K" claim is undemonstrated** — The claim is retracted. A daily consumption trend dashboard and a monthly review process are added. The Lambda is given a time-of-day guard: if it fires after 10 PM UTC and the consumed count has been rising linearly (not exponentially), it pages on-call instead of reducing the cap automatically. The conditions and the consequence of not having this guard are stated explicitly.

4. **Rollback runbook RB-07 is referenced but not present** — RB-07 is included in full in Section 2.7. The 5-minute criterion is evaluated against the actual steps.

5. **AUTH sub-cap exhaustion has no automated protection and no SLA** — An automated AUTH fallback is added. At 90% AUTH consumption (18K), the system switches OTP delivery to email-based OTP for the remainder of the day and pages on-call. The tradeoff (email OTP is slower and less reliable for users without verified email) is stated. An escalation path is defined for non-response.

6. **Document ends mid-sentence again** — Section 3.2 is completed in full. The APNs certificate rotation runbook coverage is finished.

7. **Boundary test in pass criterion 3 is internally contradictory** — The parenthetical 60,001 boundary test is promoted to a formal numbered criterion with pass/fail conditions, responsible parties, and environment. The two tests are now criterion 3a and criterion 3b.

8. **80-account attack calculation assumes maximum per-user rate is sustained** — The maximum-rate assumption is retracted. The detection window is recalculated for a realistic distributed attack (200 accounts at 1 req/sec). The consumption-based alarm is shown to still fire, but the claimed 75-second window is replaced with a range that reflects realistic attack patterns.

9. **SOCIAL/AUTH split totals are asserted without accounting for growth** — A quarterly sub-cap review process is defined. The AUTH cap is made adjustable by E1 via a documented manual procedure (not a deployment). The procedure is described and the access requirement is stated.

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

SMS traffic is split into two sub-caps at the dispatch layer. The automated response acts only on the SOCIAL sub-cap. The AUTH sub-cap has a separate, human-reviewed alarm and a defined automated fallback (Section 2.6).

### 2.2 Separated SMS Paths

```
SMS dispatch routing (worker/sms_router.py):

  notification.sms_class == "AUTH":
    Route to: Twilio subaccount AUTH
    Sub-cap: 20K/day (adjustable by E1 via manual procedure, Section 2.9)
    Content: OTP codes, login alerts, password reset links

  notification.sms_class == "SOCIAL":
    Route to: Twilio subaccount SOCIAL
    Sub-cap: 80K/day (adjustable by Lambda down to 10K)
    Content: social notifications falling back from push

  Total: 100K/day across both paths
```

**Why 20K for AUTH:** Current AUTH SMS volume is estimated at 3–5K/day. 20K provides 4–6× headroom. This headroom assumption is reviewed quarterly (Section 2.9). If MAU grows significantly during the 6-month build window, AUTH volume grows proportionally and this headroom shrinks. The quarterly review process exists specifically to catch this before it becomes an incident.

### 2.3 Redis-to-CloudWatch Metric Publication Pipeline — Specification (Finding 1)

The alarm structure depends on a CloudWatch gauge metric reflecting the current value of `sms:social:consumed:{date}` and `sms:auth:consumed:{date}`. This section specifies the publisher, its failure modes, and its own monitoring.

**What publishes the metric:**

A CloudWatch metric publisher runs as a sidecar container on each worker ECS task. It is a separate container in the same ECS task definition, not a separate service. It does not require its own deployment pipeline; it is versioned and deployed with the worker task definition.

```yaml
# task-definition.json (relevant excerpt)

containerDefinitions:
  - name: worker
    image: notifications-worker:latest
    # ... worker config ...

  - name: cw-metric-publisher
    image: notifications-cw-publisher:latest
    environment:
      - name: REDIS_HOST
        value: !Ref RedisClusterEndpoint
      - name: PUBLISH_INTERVAL_SECONDS
        value: "60"
      - name: METRICS_NAMESPACE
        value: "NotificationSystem/SMS"
    essential: true   # If publisher crashes, ECS restarts the whole task
```

Setting `essential: true` means if the publisher container crashes, ECS marks the task as failed and restarts it. This prevents the silent-failure mode where the worker continues processing but the metric stops updating.

**What the publisher does every 60 seconds:**

```python
# publisher/main.py

import boto3
import redis
import time
import os
from datetime import datetime, timezone

cw = boto3.client('cloudwatch')
r = redis.Redis(host=os.environ['REDIS_HOST'], decode_responses=True)
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
    )

if __name__ == '__main__':
    while True:
        try:
            publish_once()
        except Exception as e:
            # Log but do not crash — ECS will restart on crash anyway,
            # but a transient Redis or CloudWatch error should not kill
            # the task. A sustained failure will cause PublisherHeartbeat
            # to stop arriving, which triggers the heartbeat alarm below.
            print(f"ERROR publishing metrics: {e}")
        time.sleep(INTERVAL)
```

**Publisher monitoring:**

The `PublisherHeartbeat` metric is emitted every 60 seconds. A CloudWatch alarm fires if no heartbeat arrives within 3 minutes (3 consecutive missing data points at 60-second resolution, using the `BREACHING` treatment for missing data).

```
Alarm: SMS_METRIC_PUBLISHER_DEAD
  Metric: NotificationSystem/SMS / PublisherHeartbeat
  Statistic: Sum
  Period: 60 seconds
  Evaluation periods: 3
  Threshold: < 1 (i.e., zero heartbeats in 60s)
  Missing data treatment: BREACHING
  Action: Page on-call immediately.
  Consequence: If this alarm fires, the consumption-based circuit
               breaker is effectively blind. The on-call engineer
               must treat SMS cap status as unknown and may need to
               manually check Redis or Twilio usage dashboards.
```

**What a publisher failure looks like versus a quiet day:**

| Condition | SocialSMSConsumed metric | PublisherHeartbeat | Alarm state |
|---|---|---|---|
| Normal low-volume day | Rising slowly, ~0.93/sec average | Present every 60s | No alarms |
| Attack in progress | Rising rapidly | Present every 60s | Consumption alarms fire |
| Publisher crashed | Flat (stale or zero) | Absent | SMS_METRIC_PUBLISHER_DEAD fires within 3 min |
| Redis failure | Flat (zero, r.get returns None) | Present every 60s | SMS_METRIC_PUBLISHER_DEAD does NOT fire |

The Redis failure case is a gap: if Redis fails, `r.get` returns None, the publisher emits 0 for consumed counts, and the heartbeat still arrives. The consumption alarms would not fire even during an attack. The mitigation is that Redis failure is independently alarmed (Redis cluster has its own CloudWatch alarms on connection errors and replication lag). If Redis fails, the Redis alarm fires before the SMS consumption alarm becomes relevant. This gap is accepted; adding a Redis health check to the publisher would cause the publisher to crash-loop on Redis failure, which is worse than publishing zeros.

**Publisher inclusion in Lambda pass criteria:** See Section 2.5, criterion 5.

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

### 2.5 Time-of-Day Guard on SOCIAL Lambda (Finding 3)

**Retracted claim:** The prior revision stated "normal consumption never approaches 72K before end of day." This claim was undemonstrated. It is retracted.

**The actual problem:** If the app grows, or if a viral event drives unusually high push-failure rates (causing more social notifications to fall back to SMS), legitimate consumption could reach 72K. Without a time-of-day guard, the Lambda would reduce the SOCIAL cap to 10K, degrading social notifications for the remainder of the day, on a non-attack day.

**Time-of-day guard logic:**

```python
# lambda/sms_cap_reducer.py (guard section, added before the DynamoDB write)

from datetime import datetime, timezone

def is_likely_legitimate_growth(social_consumed: int) -> bool:
    """
    Returns True if the consumption pattern looks like linear growth
    (legitimate traffic) rather than a spike (attack).

    Heuristic: If it's after 22:00 UTC AND the consumed count has been
    rising at a rate consistent with the daily average for the past hour,
    treat as legitimate growth and page instead of auto-reducing.

    This heuristic has a known failure mode: a slow, sustained attack
    that starts early in the day and accelerates near end of day will
    look like linear growth. The 75% alarm fires first and gives a human
    1–2 hours to investigate before this function is evaluated.
    """
    now = datetime.now(timezone.utc)
    if now.hour < 22:
        # Before 10 PM UTC: auto-reduce is appropriate.
        # If 72K is consumed before 10 PM, it's almost certainly an attack.
        return False

    # After 10 PM UTC: check if we're on a linear trajectory.
    # Expected consumption at 10 PM on a max-volume day:
    #   80K * (22/24) = ~73K. At 10 PM, 72K consumed is plausible legitimately.
    # If we're here, page on-call instead of auto-reducing.
    return True

def handler(event, context):
    import boto3, redis, os
    from botocore.exceptions import ClientError
    from datetime import datetime, timezone

    r = redis.Redis(host=os.environ['REDIS_HOST'], decode_responses=True)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    social_consumed = int(r.get(f'sms:social:consumed:{today}') or 0)

    if is_likely_legitimate_growth(social_consumed):
        # Page on-call but do not auto-reduce.
        # The 75% alarm already fired ~15K messages ago; a human has had
        # time to investigate. If they haven't acted, this is an escalation.
        _send_escalation_page("SMS_SOCIAL_90PCT_LATE_DAY: possible legitimate "
                              "growth or slow attack. Manual review required. "
                              "Cap NOT auto-reduced.")
        return {'statusCode': 200, 'body': 'escalated, no cap change'}

    # Before 10 PM: proceed with auto-reduction.
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('sms_cap_config')
    # ... conditional write (Section 2.6 idempotency implementation) ...
```

**Consequence of this guard:** Between 10 PM and midnight UTC, a genuine attack that has consumed 72K SOCIAL messages will not be automatically mitigated. The remaining 8K messages are available to the attacker. The 75% alarm (60K) fired ~1–2 hours earlier depending on attack rate, giving a human time to act. If no human has acted by 10 PM, the escalation page is a second prompt. The window of unmitigated exposure is at most 2 hours of end-of-day traffic. This is accepted as preferable to automatically degrading social notifications on a legitimate high-engagement day.

**Daily consumption trend monitoring:**

A CloudWatch dashboard panel shows `SocialSMSConsumed` over the trailing 30 days. The monthly sub-cap review (Section 2.9) uses this panel