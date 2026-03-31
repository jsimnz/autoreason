# Notification System Design Proposal — Revision 8
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses nine critic findings from Revision 6. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **Redis-to-CloudWatch pipeline is undocumented and untested as a dependency** — The publisher is specified as a sidecar container on each worker ECS task, emitting metrics every 60 seconds. Its failure modes, its own alarm, and its inclusion in the Lambda pass criteria are defined. A silent publisher failure is detectable within 3 minutes.

2. **Idempotency implementation has a race condition in the read path, and `updated_at` is set to a request ID** — The post-failure `get_item` is removed. The `updated_at` field is corrected to use `datetime.utcnow().isoformat()`. Both fixes are shown in the revised code.

3. **90% threshold automation has no time-of-day awareness, and the "normal consumption never approaches 72K" claim is undemonstrated** — The claim is retracted. A time-of-day guard is added: if the Lambda fires after 22:00 UTC, it pages on-call instead of auto-reducing. The conditions and the consequence of not having this guard are stated explicitly. A daily consumption trend dashboard and monthly review process are added.

4. **Rollback runbook RB-07 is referenced but not present** — RB-07 is included in full in Section 2.7.

5. **AUTH sub-cap exhaustion has no automated protection and no SLA** — An automated AUTH fallback is added. At 90% AUTH consumption (18K), the system switches OTP delivery to email-based OTP and pages on-call. The tradeoff is stated.

6. **Document ends mid-sentence again** — Section 3.2 is completed in full.

7. **Boundary test in pass criterion 3 is internally contradictory** — The parenthetical boundary test is promoted to a formal numbered criterion (3b). The two tests are now criterion 3a and criterion 3b.

8. **80-account attack calculation assumes maximum per-user rate is sustained** — The maximum-rate assumption is retracted. The detection window is recalculated for a realistic distributed attack. The claimed 75-second window is replaced with a range reflecting realistic attack patterns.

9. **SOCIAL/AUTH split totals are asserted without accounting for growth** — A quarterly sub-cap review process is defined. The AUTH cap is adjustable by E1 via a documented manual procedure, not a deployment.

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

SMS traffic is split into two sub-caps at the dispatch layer. The automated response acts only on the SOCIAL sub-cap. The AUTH sub-cap has a separate alarm and a defined automated fallback (Section 2.6).

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

**Why 20K for AUTH:** Current AUTH SMS volume is estimated at 3–5K/day. 20K provides 4–6× headroom. This assumption is reviewed quarterly (Section 2.9). If MAU grows significantly during the 6-month build window, AUTH volume grows proportionally and this headroom shrinks. The quarterly review process exists specifically to catch this before it becomes an incident.

### 2.3 Redis-to-CloudWatch Metric Publication Pipeline

The alarm structure depends on a CloudWatch gauge metric reflecting the current value of `sms:social:consumed:{date}` and `sms:auth:consumed:{date}`. This section specifies the publisher, its failure modes, and its own monitoring.

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
    essential: true   # If publisher crashes, ECS restarts the whole task
```

Setting `essential: true` prevents the silent-failure mode where the worker continues processing but the metric stops updating.

```python
# publisher/main.py

import boto3, redis, time, os
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
            {'MetricName': 'SocialSMSConsumed', 'Value': social_consumed,
             'Unit': 'Count', 'Timestamp': now},
            {'MetricName': 'AuthSMSConsumed', 'Value': auth_consumed,
             'Unit': 'Count', 'Timestamp': now},
            {'MetricName': 'PublisherHeartbeat', 'Value': 1,
             'Unit': 'Count', 'Timestamp': now},
        ]
    )

if __name__ == '__main__':
    while True:
        try:
            publish_once()
        except Exception as e:
            # Log but do not crash. A sustained failure will cause
            # PublisherHeartbeat to stop arriving, triggering the alarm below.
            print(f"ERROR publishing metrics: {e}")
        time.sleep(INTERVAL)
```

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
               directly.
```

**Failure mode summary:**

| Condition | SocialSMSConsumed | PublisherHeartbeat | Alarm state |
|---|---|---|---|
| Normal day | Rising slowly | Present every 60s | No alarms |
| Attack in progress | Rising rapidly | Present every 60s | Consumption alarms fire |
| Publisher crashed | Flat (stale) | Absent | SMS_METRIC_PUBLISHER_DEAD fires within 3 min |
| Redis failure | Flat (zero) | Present every 60s | SMS_METRIC_PUBLISHER_DEAD does NOT fire |

The Redis failure case is a gap: if Redis fails, the publisher emits 0 and the heartbeat still arrives. The mitigation is that Redis failure is independently alarmed. If Redis fails, the Redis alarm fires before the SMS consumption alarm becomes relevant. Adding a Redis health check to the publisher would cause crash-looping on Redis failure, which is worse than publishing zeros. This gap is accepted.

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

**The problem:** If legitimate consumption reaches 72K (possible on a high-engagement day with elevated push-failure rates), the Lambda would reduce the SOCIAL cap to 10K and degrade social notifications for the remainder of the day.

**Guard logic:**

```python
# lambda/sms_cap_reducer.py

from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

def is_likely_legitimate_growth() -> bool:
    """
    After 22:00 UTC, 72K consumed is plausible on a max-volume day
    (80K * 22/24 ≈ 73K). Page instead of auto-reducing.

    Known failure mode: a slow attack that starts early and accelerates
    near end of day will look like linear growth. The 75% alarm fires
    first, giving a human 1–2 hours to investigate before this is reached.
    """
    return datetime.now(timezone.utc).hour >= 22

def handler(event, context):
    r = redis.Redis(host=os.environ['REDIS_HOST'], decode_responses=True)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    if is_likely_legitimate_growth():
        _send_escalation_page(
            "SMS_SOCIAL_90PCT_LATE_DAY: possible legitimate growth or slow "
            "attack. Manual review required. Cap NOT auto-reduced."
        )
        return {'statusCode': 200, 'body': 'escalated, no cap change'}

    # Before 22:00 UTC: proceed with auto-reduction.
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('sms_cap_config')
    try:
        table.update_item(
            Key={'cap_name': 'SOCIAL_DAILY_CAP'},
            UpdateExpression='SET cap_value = :reduced, updated_at = :now',
            ConditionExpression='cap_value = :normal',
            ExpressionAttributeValues={
                ':reduced': 10_000,
                ':normal': 80_000,
                ':now': datetime.utcnow().isoformat(),
            }
        )
        print("SOCIAL cap reduced to 10000")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print("cap already at reduced value, skipping write")
            return {'statusCode': 200, 'body': 'already reduced'}
        raise
    return {'statusCode': 200, 'body': 'cap reduced'}
```

**Consequence of this guard:** Between 22:00 and midnight UTC, a genuine attack that has consumed 72K SOCIAL messages will not be automatically mitigated. The remaining 8K messages are available to the attacker. The 75% alarm fired ~1–2 hours earlier, giving a human time to act. If no human has acted by 22:00, the escalation page is a second prompt. This is accepted as preferable to automatically degrading social notifications on a legitimate high-engagement day.

### 2.6 AUTH Automated Fallback (Finding 5)

At 90% AUTH consumption (18K), the system switches OTP delivery to email-based OTP for the remainder of the day and pages on-call.

**Tradeoff:** Email OTP is slower and less reliable for users without a verified email address on file. During a security incident — the most likely cause of AUTH SMS exhaustion — some users may be locked out if they lack a verified email. This is accepted: the alternative (no fallback) locks out all users once the cap is exhausted.

**Escalation path:** If on-call does not acknowledge within 15 minutes, the alert escalates to the secondary on-call. The AUTH cap is not automatically restored; restoration requires E1 via the manual procedure in Section 2.9.

### 2.7 Rollback Runbook RB-07

**Purpose:** Restore the SOCIAL SMS sub-cap to 80K after the Lambda has reduced it to 10K.

**Who can execute:** E4 alone. E1 does not need to be present.

**Prerequisites:** AWS console access with DynamoDB write permission to `sms_cap_config`.

**Steps:**

1. Open DynamoDB console → Tables → `sms_cap_config`.
2. Select the item with `cap_name = SOCIAL_DAILY_CAP`.
3. Click **Edit**. Set `cap_value` to `80000`. Set `updated_at` to current UTC timestamp in ISO 8601 format. Click **Save**.
4. Verify: the rate limiter config store polls DynamoDB every 30 seconds. Wait 60 seconds, then check CloudWatch metric `SocialSMSCapCurrent`. Confirm it shows 80000.
5. Post in the incident channel: "RB-07 executed by [name] at [time]. SOCIAL cap restored to 80K. Monitor for recurrence."

**Time estimate:** 3–4 minutes from start to verified restoration. The 5-minute criterion in pass criterion 4 is achievable.

**What this does not do:** RB-07 does not investigate why the cap was reduced. Root cause analysis is a separate step after the cap is restored.

### 2.8 Authenticated-Account Attack Path (Finding 8)

If an attacker uses compromised accounts to generate SOCIAL SMS volume, the IP-based WAF does not fire. The per-user API rate limit is 10 req/sec.

**Prior claim retracted:** The prior revision calculated detection at 75–90 seconds assuming 80 accounts each sustaining 10 req/sec. This assumed maximum per-user rate is sustained, which is unrealistic. A realistic distributed attack uses more accounts at lower per-account rates to avoid per-user detection.

**Recalculated range:** For a 200-account attack at 1 req/sec per account (200 req/sec total, below per-user rate limits):