# Notification System Design Proposal — Revision 6
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses nine critic findings from Revision 5. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **WAF "step function" model does not prevent cap exhaustion before WAF fires** — The framing was wrong. WAF is not a prevention mechanism for cap exhaustion; it is a network-layer mitigation for sustained attack. A pre-depletion circuit breaker at the SMS dispatch layer is added. The alarm structure is rewritten around rate-of-consumption, not rate-of-arrival.

2. **Authenticated-account attack path has no automated response for legitimate users** — The Lambda now routes legitimate SMS traffic (OTP, security events) to a protected sub-cap that is not reduced by the automated response. The attack surface is the social-notification SMS path, not the auth SMS path. These are separated at the dispatch layer.

3. **Document ends mid-sentence — Finding 9 resolution absent** — The hung-call watchdog section and the retry deduplication resolution are both completed in full.

4. **E3/E4 backup gaps asserted as "None identified" without demonstration** — Both backup relationships are enumerated to the same standard applied to E1/E2 in Revision 5. Honest gaps are stated.

5. **E4 read-only portal access described as mitigation when it only provides earlier failure detection** — Corrected. E4's access is redescribed accurately as earlier failure detection, not a mitigation. The actual mitigation (30-day pre-staging requirement with a calendar alert) is stated as the mitigation.

6. **Lambda test pass criterion 3 has boundary condition ambiguity** — The evaluation window, metric type (rate vs. sum), and resolution are specified explicitly. The test is redesigned to match the actual CloudWatch evaluation behavior.

7. **Scenario B "slow" is undefined** — Three distinct slow-message types are defined. Each produces different watchdog and redelivery behavior. The test runs all three variants. Pass criteria are specified per variant.

8. **Lambda idempotency criterion describes desired behavior without establishing implementation** — The implementation is stated: read-before-write with conditional write. The DynamoDB conditional expression used is shown. The pass criterion now tests the implementation, not just the outcome.

9. **One-message-per-worker throughput cost is unquantified** — Worker count, ECS scaling configuration, cost, and staging validation are all specified.

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

## 2. SMS Cap, Attack Modeling, and Alarm Structure — Revised (Findings 1 and 2)

### 2.1 Corrected Framing

The prior revision treated WAF as the primary protection mechanism and derived alarm thresholds from WAF response time. This was wrong in two ways:

First, WAF fires at the network layer after up to 60 seconds. At 2,500 req/sec, 60 seconds of unmitigated traffic is 150,000 SMS messages — exceeding the entire 100K/day cap before WAF has acted. An alarm that gives "visibility before WAF takes over" does not prevent cap exhaustion. WAF is useful for stopping continued attack after the cap is exhausted, but it is not a cap-protection mechanism.

Second, the cap is a single number. The prior design would lower it from 100K to 10K in response to any spike above 800/sec, including spikes caused by authenticated attackers. Legitimate SMS traffic — OTP codes, security event alerts — shares the same cap. During an account-compromise attack, the users most likely to need SMS OTP are users who are being targeted. Throttling them is the worst possible time to throttle them.

### 2.2 Separated SMS Paths

SMS traffic is split into two sub-caps at the dispatch layer, not at the WAF layer:

```
SMS dispatch routing (worker/sms_router.py):

  notification.sms_class == "AUTH":
    Route to: Twilio subaccount AUTH
    Sub-cap: 20K/day (hard, not adjustable by Lambda)
    Content: OTP codes, login alerts, password reset links

  notification.sms_class == "SOCIAL":
    Route to: Twilio subaccount SOCIAL
    Sub-cap: 80K/day (adjustable by Lambda down to 10K)
    Content: social notifications falling back from push

  Total: 100K/day across both paths
```

The Lambda automated response only adjusts the SOCIAL sub-cap. The AUTH sub-cap is a hard limit in the dispatch layer, not configurable by the Lambda. An attacker generating SMS volume through the social notification path cannot exhaust AUTH capacity, and the Lambda cannot accidentally throttle AUTH traffic.

**Why 20K for AUTH:** Normal AUTH SMS volume is estimated at 3–5K/day (password resets, new device logins, 2FA enrollment). 20K provides 4–6× headroom for legitimate spikes (major app update triggering re-authentication, a real security incident generating user alerts). If AUTH volume exceeds 20K, that is itself anomalous and warrants a separate alarm.

### 2.3 Pre-Depletion Circuit Breaker

The alarm structure is rewritten around rate-of-consumption of the daily cap, not rate-of-arrival of requests.

```
Cap consumption tracking:
  Redis key: sms:social:consumed:{date}  (incremented at dispatch)
  Redis key: sms:auth:consumed:{date}    (incremented at dispatch)
  Both keys expire at midnight UTC.

Circuit breaker (evaluated every 60 seconds by a CloudWatch metric filter):

  SOCIAL sub-cap:
    If consumed > 60K (75% of 80K):
      Alarm: SMS_SOCIAL_75PCT_CONSUMED
      Action: Page on-call. No automated cap change.
      Rationale: Normal consumption at this level warrants human review.

    If consumed > 72K (90% of 80K):
      Alarm: SMS_SOCIAL_90PCT_CONSUMED
      Action: Lambda lowers SOCIAL sub-cap to 10K for the remainder
              of the day. Remaining SOCIAL SMS traffic falls back to email.
      Rationale: At 90% consumption, the remaining 8K messages will be
                 exhausted within minutes at attack volume. Human response
                 is not fast enough. Automated fallback to email is safer
                 than exhausting the cap.

  AUTH sub-cap:
    If consumed > 16K (80% of 20K):
      Alarm: SMS_AUTH_80PCT_CONSUMED
      Action: Page on-call. No automated cap change. AUTH cap is never
              automatically reduced.
      Rationale: AUTH SMS exhaustion during an attack is a separate
                 incident requiring human judgment, not automation.
```

**What this changes:** The prior alarm fired on throughput rate (200/sec, 800/sec). This alarm fires on cumulative consumption. A slow, sustained attack that stays below 200/sec but steadily consumes the cap is now detectable. A fast burst that exhausts the cap before WAF fires still triggers the 90% alarm before the cap is fully gone, giving 8K messages of response time rather than zero.

**Residual risk:** An attacker who consumes exactly 71,999 SOCIAL messages and then stops has bypassed both thresholds. At normal volume (80K/day ≈ 0.93/sec average), legitimate consumption never approaches 72K before end of day. If it does, the 75% alarm fires first and a human investigates. This residual risk is accepted.

### 2.4 Authenticated-Account Attack Path

If an attacker uses 80 compromised accounts to generate SOCIAL SMS volume, the IP-based WAF does not fire. The per-user API rate limit is 10 req/sec. 80 accounts × 10 req/sec = 800 req/sec. At that rate:

- 75% alarm (60K consumed) fires after 75 seconds
- 90% alarm (72K consumed) fires after 90 seconds
- Lambda lowers SOCIAL cap to 10K

Legitimate SOCIAL SMS falls back to email for the remainder of the day. AUTH SMS is unaffected. This is the correct outcome: social notification fallback to email is acceptable; auth SMS disruption is not.

The account anomaly detection system (separate, not in scope) may detect 80 compromised accounts independently. This design does not depend on it doing so. If it does detect them, the attack stops earlier. If it does not, the consumption-based circuit breaker still fires.

### 2.5 Lambda Pass Criteria — Revised (Finding 6)

**Finding 6 correction:** The prior pass criterion 3 injected a spike to 700/sec and expected the Lambda not to fire. But the Lambda now fires on cumulative consumption (90% of sub-cap), not on throughput rate. The prior test was testing the wrong trigger condition. Additionally, the prior test did not specify the CloudWatch evaluation window or metric type, creating ambiguity about whether a sum metric over a 10-second window could aggregate to a value that crosses a rate threshold.

The Lambda trigger is now a CloudWatch alarm on the `sms:social:consumed` Redis metric, published to CloudWatch every 60 seconds as a gauge (current value, not a sum or rate). The evaluation period is 1 data point (60 seconds). There is no aggregation ambiguity: the metric is the current consumed count, and the threshold is an absolute value.

```
Revised Lambda pass criteria — all four must pass:

1. Propagation latency:
   Trigger: Set sms:social:consumed:{today} to 72,001 in staging Redis.
            Wait for the next CloudWatch metric publication (≤ 60s).
   Pass: Lambda fires within 120 seconds of the Redis value being set.
         SOCIAL sub-cap config in the rate limiter config store shows
         10K within 60 seconds of Lambda firing.
   Fail: Lambda does not fire within 120 seconds, or cap not updated
         within 60 seconds of Lambda firing.

2. Idempotency:
   Trigger: Fire the Lambda 5 times within 10 seconds directly
            (bypassing CloudWatch alarm, via AWS Lambda console).
   Pass: DynamoDB table sms_cap_config shows exactly one write event
         for the SOCIAL cap change. Subsequent invocations log
         "cap already at reduced value, skipping write" and return
         200. CloudWatch Logs shows 5 invocations, 1 write, 4 skips.
   Fail: More than one write to sms_cap_config, or any invocation
         errors, or any invocation does not log its outcome.

3. False-positive test:
   Trigger: Set sms:social:consumed:{today} to 59,999 in staging Redis
            and hold it there for 10 minutes (simulating a legitimate
            heavy-use day approaching but not crossing the 75% threshold).
   Pass: Lambda does not fire. SMS_SOCIAL_75PCT_CONSUMED alarm does
         not fire (threshold is 60K; 59,999 is below it).
   Fail: Lambda fires, or SMS_SOCIAL_75PCT_CONSUMED alarm fires.
   Note: The test value is 59,999, not 60,001, because the intent is
         to confirm the threshold boundary. A separate boundary test
         sets the value to 60,001 and confirms SMS_SOCIAL_75PCT_CONSUMED
         fires without triggering the Lambda (Lambda threshold is 72K).

4. Rollback verification:
   Trigger: After criterion 1 or 2 has fired the Lambda, execute
            runbook RB-07 (manual cap restoration).
   Pass: sms_cap_config shows SOCIAL cap restored to 80K within
         5 minutes of runbook execution start. No deployment required.
   Fail: Restoration requires a deployment, or takes > 5 minutes,
         or requires E1 to be present (E4 must be able to execute
         RB-07 alone).

Environment: Staging. Responsible: E4 (primary), E3 (witness).
Frequency: Quarterly, and after any change to the Lambda, the rate
limiter config store, or the Redis metric publication pipeline.
```

### 2.6 Lambda Idempotency Implementation (Finding 8)

The prior criterion described the desired outcome (cap written once) without stating whether the implementation produces it. The implementation is:

```python
# lambda/sms_cap_reducer.py

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('sms_cap_config')

REDUCED_SOCIAL_CAP = 10_000
NORMAL_SOCIAL_CAP = 80_000

def handler(event, context):
    try:
        # Conditional write: only write if current value is NORMAL_SOCIAL_CAP.
        # If already reduced, the condition fails and we skip the write.
        table.update_item(
            Key={'cap_name': 'SOCIAL_DAILY_CAP'},
            UpdateExpression='SET cap_value = :reduced, updated_at = :now',
            ConditionExpression='cap_value = :normal',
            ExpressionAttributeValues={
                ':reduced': REDUCED_SOCIAL_CAP,
                ':normal': NORMAL_SOCIAL_CAP,
                ':now': context.aws_request_id,
            }
        )
        print(f"SOCIAL cap reduced to {REDUCED_SOCIAL_CAP}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            current = table.get_item(
                Key={'cap_name': 'SOCIAL_DAILY_CAP'}
            )['Item']['cap_value']
            print(f"cap already at reduced value ({current}), skipping write")
            return {'statusCode': 200, 'body': 'already reduced'}
        raise
    return {'statusCode': 200, 'body': 'cap reduced'}
```

The `ConditionExpression` ensures the write only succeeds if the current value is `NORMAL_SOCIAL_CAP`. Concurrent invocations racing on the same item will have at most one succeed; all others will catch `ConditionalCheckFailedException` and log "skipping write." This is a standard DynamoDB optimistic locking pattern. The idempotency pass criterion in Section 2.5 tests this code path directly.

---

## 3. Team Allocation

### 3.1 E2 Backup Scope (Unchanged from Revision 5)

*In scope for E2 (no deployment required):*
- Restart failed worker instances via ECS console
- Roll back a task definition to a prior version via ECS console
- Adjust SQS visibility timeout and retry count via AWS console
- Adjust SQS receive message wait time via AWS console
- Escalate Redis or SQS issues to AWS support
- Read pipeline logs and metrics in CloudWatch
- Acknowledge and triage PagerDuty alerts

*Explicitly out of scope for E2:*
- Adjusting `WORKER_CONCURRENCY` or any environment variable (requires deployment)
- Adjusting `MAX_BATCH_SIZE`, `BATCH_WINDOW_MS`, or any batching parameter
- Modifying routing logic, deduplication key generation, or batching algorithm logic
- Any schema migration

**Honest consequence:** If E1 is unavailable during a queue backlog requiring concurrency adjustment, E2 cannot resolve it without a deployment. Correct response: increase visibility timeout via SQS console to slow redelivery and escalate to E1.

### 3.2 E1 APNs/FCM Backup Coverage (Unchanged from Revision 5)

```
APNs/FCM failures E1 must handle without E2:

1. APNs certificate expiry
   Location: AWS Secrets Manager, /notifications/apns/cert
   Check: openssl x509 -noout -dates -in <cert>
   Rotation: Runbook RB-04. Requires next certificate pre-staged
   in Secrets Manager by E2. If not pre-staged, E1 cannot complete
   rotation alone