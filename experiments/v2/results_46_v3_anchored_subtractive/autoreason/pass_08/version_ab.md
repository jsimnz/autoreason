# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses nine critic findings from Revision 5. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **WAF "step function" model does not prevent cap exhaustion before WAF fires** — Framing corrected. A pre-depletion circuit breaker at the SMS dispatch layer is added. Alarm structure rewritten around rate-of-consumption, not rate-of-arrival.

2. **Authenticated-account attack path has no automated response for legitimate users** — SMS traffic split into AUTH and SOCIAL sub-caps at the dispatch layer. Lambda only adjusts SOCIAL sub-cap. AUTH sub-cap is not configurable by the Lambda.

3. **Document ends mid-sentence — hung-call watchdog and retry deduplication incomplete** — Both sections completed in full.

4. **E3/E4 backup gaps asserted as "None identified" without demonstration** — Both backup relationships enumerated to the same standard applied to E1/E2.

5. **E4 read-only portal access described as mitigation** — Corrected. E4's access is redescribed accurately as earlier failure detection. The actual mitigation (30-day pre-staging with calendar alert) is stated as the mitigation.

6. **Lambda pass criterion 3 has boundary condition ambiguity** — Evaluation window, metric type, and resolution specified explicitly. Test redesigned to match actual CloudWatch evaluation behavior.

7. **Scenario B "slow" is undefined** — Three distinct slow-message types defined. Each produces different watchdog and redelivery behavior. Pass criteria specified per variant.

8. **Lambda idempotency criterion describes desired behavior without establishing implementation** — Implementation stated: DynamoDB conditional write. The conditional expression is shown. Pass criterion now tests the implementation.

9. **One-message-per-worker throughput cost is unquantified** — Worker count, ECS scaling configuration, cost, and staging validation specified.

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

The prior revision treated WAF as the primary protection mechanism and derived alarm thresholds from WAF response time. This was wrong in two ways.

First, WAF fires at the network layer after up to 60 seconds. At 2,500 req/sec, 60 seconds of unmitigated traffic is 150,000 SMS messages — exceeding the entire 100K/day cap before WAF has acted. An alarm that gives "visibility before WAF takes over" does not prevent cap exhaustion. WAF is useful for stopping continued attack after the cap is exhausted, but it is not a cap-protection mechanism.

Second, the cap is a single number. The prior design lowered it from 100K to 10K in response to any spike above 800/sec, including spikes caused by authenticated attackers. Legitimate SMS traffic — OTP codes, security event alerts — shares the same cap. During an account-compromise attack, the users most likely to need SMS OTP are users being targeted. Throttling them at that moment is the worst possible outcome.

### 2.2 Separated SMS Paths

SMS traffic is split into two sub-caps at the dispatch layer:

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

The Lambda automated response only adjusts the SOCIAL sub-cap. The AUTH sub-cap is a hard limit in the dispatch layer. An attacker generating SMS volume through the social notification path cannot exhaust AUTH capacity, and the Lambda cannot accidentally throttle AUTH traffic.

**Why 20K for AUTH:** Normal AUTH SMS volume is estimated at 3–5K/day. 20K provides 4–6× headroom for legitimate spikes. If AUTH volume exceeds 20K, that is itself anomalous and warrants a separate alarm.

### 2.3 Pre-Depletion Circuit Breaker

The alarm structure is rewritten around rate-of-consumption of the daily cap, not rate-of-arrival of requests.

```
Cap consumption tracking:
  Redis key: sms:social:consumed:{date}  (incremented at dispatch)
  Redis key: sms:auth:consumed:{date}    (incremented at dispatch)
  Both keys expire at midnight UTC.

Circuit breaker (evaluated every 60 seconds via CloudWatch metric filter):

  SOCIAL sub-cap:
    If consumed > 60K (75% of 80K):
      Alarm: SMS_SOCIAL_75PCT_CONSUMED
      Action: Page on-call. No automated cap change.

    If consumed > 72K (90% of 80K):
      Alarm: SMS_SOCIAL_90PCT_CONSUMED
      Action: Lambda lowers SOCIAL sub-cap to 10K for remainder
              of day. Remaining SOCIAL SMS falls back to email.
      Rationale: At 90% consumption, remaining 8K messages will be
                 exhausted within minutes at attack volume. Human
                 response is not fast enough.

  AUTH sub-cap:
    If consumed > 16K (80% of 20K):
      Alarm: SMS_AUTH_80PCT_CONSUMED
      Action: Page on-call. No automated cap change. AUTH cap is
              never automatically reduced.
```

**What this changes:** The prior alarm fired on throughput rate. This alarm fires on cumulative consumption. A slow, sustained attack staying below the rate threshold but steadily consuming the cap is now detectable. A fast burst that would exhaust the cap before WAF fires still triggers the 90% alarm with 8K messages of response time remaining.

**Residual risk:** An attacker who consumes exactly 71,999 SOCIAL messages and stops bypasses both thresholds. At normal volume, legitimate consumption never approaches 72K before end of day. If it does, the 75% alarm fires first. This residual risk is accepted.

### 2.4 Authenticated-Account Attack Path

If an attacker uses 80 compromised accounts at 10 req/sec each (800 req/sec total), the IP-based WAF does not fire. At that rate:

- 75% alarm (60K consumed) fires after 75 seconds
- 90% alarm (72K consumed) fires after 90 seconds
- Lambda lowers SOCIAL cap to 10K

Legitimate SOCIAL SMS falls back to email for the remainder of the day. AUTH SMS is unaffected. This is the correct outcome. This design does not depend on account anomaly detection acting first — if it does, the attack stops earlier; if it does not, the consumption-based circuit breaker still fires.

### 2.5 Lambda Pass Criteria

The Lambda trigger is a CloudWatch alarm on the `sms:social:consumed` Redis metric, published every 60 seconds as a gauge (current value, not a sum or rate). Evaluation period is 1 data point. There is no aggregation ambiguity.

```
All four criteria must pass:

1. Propagation latency:
   Trigger: Set sms:social:consumed:{today} to 72,001 in staging Redis.
            Wait for next CloudWatch metric publication (≤ 60s).
   Pass: Lambda fires within 120 seconds of Redis value being set.
         SOCIAL sub-cap in rate limiter config store shows 10K within
         60 seconds of Lambda firing.
   Fail: Lambda does not fire within 120 seconds, or cap not updated
         within 60 seconds of Lambda firing.

2. Idempotency:
   Trigger: Fire Lambda 5 times within 10 seconds directly via
            AWS Lambda console (bypassing CloudWatch alarm).
   Pass: DynamoDB table sms_cap_config shows exactly one write event.
         Subsequent invocations log "cap already at reduced value,
         skipping write" and return 200. CloudWatch Logs shows
         5 invocations, 1 write, 4 skips.
   Fail: More than one write, any invocation errors, or any
         invocation does not log its outcome.

3. False-positive boundary test (two sub-tests):
   Sub-test A: Set sms:social:consumed:{today} to 59,999 and hold
               for 10 minutes.
   Pass: Neither Lambda nor SMS_SOCIAL_75PCT_CONSUMED fires.

   Sub-test B: Set value to 60,001.
   Pass: SMS_SOCIAL_75PCT_CONSUMED fires. Lambda does not fire
         (Lambda threshold is 72K).
   Fail (either): Lambda fires below 72K threshold, or
                  75PCT alarm fires below 60K threshold.

4. Rollback verification:
   Trigger: After criterion 1 or 2 has fired the Lambda, execute
            runbook RB-07.
   Pass: sms_cap_config shows SOCIAL cap restored to 80K within
         5 minutes. No deployment required. E4 must be able to
         execute RB-07 alone.
   Fail: Restoration requires a deployment, takes > 5 minutes,
         or requires E1 present.

Environment: Staging. Responsible: E4 (primary), E3 (witness).
Frequency: Quarterly, and after any change to the Lambda, rate
limiter config store, or Redis metric publication pipeline.
```

### 2.6 Lambda Idempotency Implementation

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

The `ConditionExpression` ensures the write only succeeds if the current value is `NORMAL_SOCIAL_CAP`. Concurrent invocations racing on the same item will have at most one succeed; all others catch `ConditionalCheckFailedException` and log "skipping write." This is standard DynamoDB optimistic locking. The idempotency pass criterion in Section 2.5 tests this code path directly.

---

## 3. Team Allocation

### 3.1 E2 Backup Scope

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

### 3.2 E1 APNs/FCM Backup Coverage

```
APNs/FCM failures E1 must handle without E2:

1. APNs certificate expiry
   Location: AWS Secrets Manager, /notifications/apns/cert
   Check: openssl x509 -noout -dates -in <cert>
   Rotation: Runbook RB-04. Requires next certificate pre-staged
             in Secrets Manager by E2 before rotation. If not
             pre-staged, E1 cannot complete rotation alone.
   Alert: CloudWatch alarm on APNs 403 rate > 1% over 5 minutes.

2. FCM token invalidation wave
   Symptoms: FCM returns 404 (NotRegistered) for a large percentage
             of tokens, typically after an app update.
   Response: FCM 404s trigger async token deletion (Redis key:
             device_tokens:{user_id}). Lag between 404 receipt and
             deletion is bounded by the worker's ack cycle. Duplicate
             404s during the lag are expected and not a pipeline failure.
   E1 must know: deletion is in worker/token_lifecycle.py,
                 function handle_fcm_not_registered. E1 reads
                 metrics; no code change required.

3. FCM HTTP/2 connection pool exhaustion
   Symptoms: FCM dispatch latency spikes; watchdog fires repeatedly.
   Response: Restart workers to reset connections (ECS console —
             E2 can do this while E1 is paged). If recurs, reduce
             FCM_POOL_SIZE env var (requires deployment — E1 scope).
   E1 must know: FCM_POOL_SIZE defaults to 50 in worker/fcm_client.py.
                 Reducing to 20 is safe.

4. APNs HTTP/2 stream hang
   Response: Watchdog handles automatically. E1 reads the
             WATCHDOG_FIRED alarm, confirms it is APNs-related via
             the notification_id in the log, monitors whether rate
             is increasing.
   If WATCHDOG_FIRED rate > 10/minute: APNs endpoint is degraded.
   Check Apple system status page. If degraded, reduce
   APNS_DISPATCH_BUDGET from 8s to 4s to fail faster.
   This requires a deployment — E1 scope.
```

**Honest gap:** APNs certificate rotation requires E2 to have pre-staged the next certificate. If E2 is unavailable and the certificate has expired, E1 cannot complete rotation without access to Apple's developer portal.

**Mitigation:** E2 stages the next certificate 30 days before expiry. A calendar alert fires at 30 days and again at 14 days. E4 has read-only access to the developer portal to verify whether a certificate has been pre-staged — this is earlier failure detection, not a mitigation. If E4 confirms at 30 days that staging has not occurred, E2 is contacted before the gap becomes critical.

### 3.3 E3/E4 Backup Coverage

```
E4 backup for E3 (Preference management, user-facing API,
suppression logic):

1. Suppression list corruption or runaway suppression
   Symptoms: Large cohort of users stops receiving notifications
             despite no preference change.
   Response: Runbook RB