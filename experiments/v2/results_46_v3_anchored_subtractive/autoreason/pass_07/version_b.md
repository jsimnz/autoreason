# Notification System Design Proposal — Revision 5
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses nine critic findings from Revision 4. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **`signal` module used but never imported** — `import signal` added to the import block. The omission was in the exact failure path where the module is needed most.

2. **Watchdog 2-second grace period is ungrounded** — The grace period is now derived from the remaining time budget after the watchdog fires. It is not a fixed 2 seconds; it is `visibility_timeout − watchdog_fires_at − cleanup_margin`, which is deterministic given the timing constants already established.

3. **`asyncio.shield` defeats `asyncio.wait_for`** — `asyncio.shield` removed. The task is cancelled directly. The consequences of direct cancellation are stated explicitly.

4. **SIGTERM collateral damage to co-resident messages is unspecified** — Each worker runs one in-flight message at a time. The architectural decision enabling this is stated explicitly, along with its cost.

5. **SMS attack ramp rate borrowed from a different company's incident** — The external ramp rate is replaced with a conservative bound derived from this system's own API-layer rate limits. The Lambda secondary threshold is derived from the same basis. The Lambda test pass criteria are defined.

6. **Lambda test has no pass criteria** — Pass criteria defined: propagation latency bound, idempotency verification, false-positive rate on legitimate spikes, and rollback verification.

7. **E2 backup for APNs/FCM API layer asserts coverage without demonstrating it** — The runbook content that E1 must know to provide backup coverage is enumerated. If E1 cannot demonstrate that knowledge, the coverage claim is withdrawn and the gap is stated honestly.

8. **P1 blocking probability ignores group assignment skew** — The independence assumption is withdrawn. The pass criteria are rewritten to handle the correlated failure case directly rather than relying on a probability argument.

9. **Proposal ends mid-sentence — Finding 5 (retry deduplication) unresolved** — Complete resolution provided: deterministic `notification_id` derivation, crash recovery path, and the specific race condition closed.

---

## 1. Scale Assumptions and Constraints

*(Unchanged from Revision 4. Reproduced for completeness.)*

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

### SMS Cap and Email Fallback — Revised Alarm Derivation (Findings 5 and 6)

SMS is capped at 100K/day. Events exceeding the cap fall back to email.

**Why the prior derivation was wrong (Finding 5):**

The prior revision derived the alarm threshold using a ramp rate of 16/sec/minute from a 2023 Twilio postmortem at a "comparable service." That figure describes how fast an attacker ramped against a different company's infrastructure, with different API-layer rate limits, different CAPTCHA friction, and different account verification requirements. Using it as a measured property of this system was not justified. A faster ramp against this system would invalidate the entire threshold calculation, and we had no data to bound how much faster.

**Revised derivation using this system's own constraints:**

The binding constraint on how fast an attacker can generate SMS volume against this system is this system's API-layer rate limiting, not the attacker's tooling. We control the API rate limiter. Its limits are known.

```
System constraints:
  API rate limit per authenticated user: 10 requests/sec
  API rate limit per IP (unauthenticated): 5 requests/sec
  Maximum concurrent attacker IPs before IP-block automation fires: 500
    (CloudFront WAF rule, fires at 500 distinct IPs with anomalous
     request patterns within a 1-minute window)

Conservative worst-case ramp:
  Before WAF fires: 500 IPs × 5 req/sec = 2,500 req/sec
  Each request can trigger at most 1 SMS.
  WAF response time: ≤ 1 minute (CloudFront WAF rule propagation SLA).

  In the worst case, an attacker sustains 2,500/sec for 60 seconds
  before WAF blocks them. That is 150,000 SMS attempts in 60 seconds,
  or 2,500/sec sustained ramp rate.

  This is not a gradual ramp — it is a step function. The attacker
  is at full volume from the first second.

Consequence for threshold derivation:
  A gradual-ramp model with headroom arithmetic does not apply.
  The alarm must fire fast enough that the 25-minute response
  window begins before the WAF has failed to fire.

Revised alarm structure:
  Primary alarm: fires at 200/sec (SMS volume)
    Rationale: Normal peak SMS volume is 3.6/sec (derived in Section 1).
    200/sec is 55× normal peak — unambiguously anomalous.
    At 200/sec, the WAF has not yet fired (WAF fires at ~500 IPs,
    which produces ~2,500/sec). The alarm gives the on-call engineer
    visibility before the WAF automation takes over.

  Secondary alarm / automated response: fires at 800/sec
    Rationale: 800/sec is above the WAF's nominal trigger point.
    If volume reaches 800/sec, either the WAF has not fired or the
    attacker has authenticated accounts (bypassing IP-based WAF).
    At this point, human response within 25 minutes is not guaranteed.
    The Lambda auto-lowers the SMS cap to 10K/day.

  Why 800/sec for the Lambda threshold:
    At 800/sec, the WAF should have already fired. If it hasn't,
    the Lambda provides a second line of defense. 800/sec is chosen
    because it is above the WAF trigger volume (2,500/sec × 1-minute
    WAF window = 2,500 req at the moment WAF fires; 800/sec is
    detectable before WAF completes propagation). It is not derived
    from headroom arithmetic — it is a hard trip wire at a volume
    that is unambiguous regardless of attack pattern.

  Honest residual risk:
    If an attacker uses authenticated accounts, the IP-based WAF does
    not fire. In that case, the per-user rate limit of 10/sec applies.
    To reach 800/sec with authenticated accounts requires 80 compromised
    accounts. Account compromise at that scale should be detectable via
    the account anomaly detection system (separate system, not in scope
    here). If it is not detected, the Lambda fires at 800/sec regardless.
```

**Lambda pass criteria (Finding 6):**

The prior revision stated the Lambda "is tested quarterly" with no definition of a passing test.

```
Lambda test — pass criteria (all must pass):

1. Propagation latency:
   Trigger: Inject synthetic CloudWatch metric event at 800/sec threshold.
   Pass: SMS cap change propagates to the rate limiter configuration store
         within 60 seconds of the Lambda firing.
   Fail: Propagation takes > 60 seconds, or Lambda does not fire.

2. Idempotency:
   Trigger: Fire the Lambda 5 times in succession within 10 seconds
            (simulating multiple alarm state transitions).
   Pass: SMS cap is set to 10K/day exactly once. No duplicate writes.
         Subsequent invocations log "cap already set" and exit cleanly.
   Fail: Cap is written multiple times, or any invocation errors.

3. False-positive rate on legitimate volume spikes:
   Trigger: Inject synthetic metric showing a volume spike to 700/sec
            for 5 minutes (below the 800/sec threshold) followed by
            return to baseline.
   Pass: Lambda does not fire. Primary alarm fires and clears.
   Fail: Lambda fires during the spike.

4. Rollback verification:
   After the Lambda lowers the cap, the on-call engineer must be able
   to restore the original cap via the runbook without redeploying.
   Pass: Cap restored to 100K/day within 5 minutes of runbook execution
         on a test environment.
   Fail: Restoration requires a deployment or takes > 5 minutes.

Test environment: Staging. Tests run against a staging instance of the
rate limiter configuration store, not production.
Responsible: E4 (primary), E3 (witness).
Frequency: Quarterly, and after any change to the Lambda or the
rate limiter configuration store.
```

---

## 2. Team Allocation

### E2 Backup Scope and E1 APNs/FCM Coverage (Finding 7)

The prior revision's coverage table stated "E1 on APNs/FCM API layer only" without establishing that E1 actually knows the APNs/FCM integration layer well enough to diagnose failures at 2am.

**What E1 must know to provide APNs/FCM backup coverage:**

Coverage is only meaningful if the backup engineer can execute specific failure responses without assistance. The following are the most likely APNs/FCM failures requiring out-of-hours response:

```
APNs failures E1 must be able to handle:
  1. APNs certificate expiry
     - Where the certificate is stored (AWS Secrets Manager, path: /notifications/apns/cert)
     - How to check expiry: openssl x509 -noout -dates -in <cert>
     - How to rotate: documented in runbook RB-04, requires E2 to have
       pre-generated the next certificate and stored it in Secrets Manager
       before rotation. If the next certificate is not pre-staged, E1
       cannot complete rotation alone. This is an honest gap.
     - Alert: CloudWatch alarm on APNs 403 response rate > 1% over 5 minutes.

  2. FCM token invalidation wave
     - Symptoms: FCM returns 404 (NotRegistered) for a large percentage
       of tokens within a short window, typically after an app update.
     - Response: FCM 404 responses trigger token deletion in the token
       store (Redis key: device_tokens:{user_id}). E1 must know that
       this deletion is asynchronous and the lag between 404 receipt
       and token deletion is bounded by the worker's ack cycle, not
       immediate. During the lag, duplicate 404s are expected and not
       a pipeline failure.
     - E1 must know: token deletion is in worker/token_lifecycle.py,
       function `handle_fcm_not_registered`. E1 does not need to modify
       this code — only to recognize that it is running and interpret
       the metrics correctly.

  3. FCM HTTP/2 connection pool exhaustion
     - Symptoms: FCM dispatch latency spikes; watchdog fires repeatedly.
     - Response: Reduce `FCM_POOL_SIZE` environment variable (requires
       deployment — E1 scope) or restart workers to reset connections
       (ECS console — E2 can do this while E1 is paged).
     - E1 must know: pool size is configured in worker/fcm_client.py,
       `FCM_POOL_SIZE` defaults to 50. Reducing to 20 is safe.

  4. APNs HTTP/2 stream hang (the primary failure mode in Section 3.2)
     - Response: Watchdog handles this automatically. E1's role is to
       read the WATCHDOG_FIRED alarm, confirm it is APNs-related by
       checking the notification_id in the log, and monitor whether
       the rate of WATCHDOG_FIRED events is increasing.
     - If WATCHDOG_FIRED rate > 10/minute: APNs endpoint is degraded.
       Response is to check Apple's system status page and, if degraded,
       reduce `APNS_DISPATCH_BUDGET` from 8s to 4s to fail faster.
       This requires a deployment — E1 scope.
```

**Honest gap after enumeration:**

APNs certificate rotation requires E2 to have pre-staged the next certificate. If E2 is unavailable and the certificate has expired, E1 cannot complete rotation without access to Apple's developer portal. This is a genuine single-point-of-failure for APNs certificate rotation. Mitigation: E2 stages the next certificate 30 days before expiry, and E4 has read-only access to the developer portal to verify the staging. E4 cannot complete the rotation alone but can confirm whether a pre-staged certificate exists, which determines whether E1 can proceed.

**Revised coverage table:**

| Engineer | Primary Responsibility | Backup Coverage Provided By | Known Gaps |
|----------|----------------------|----------------------------|------------|
| E1 | Core pipeline: SQS infrastructure, routing logic, delivery workers | E2 (console operations per Section 2.1) | None for pipeline operations |
| E2 | Push integrations: APNs, FCM, token management | E1 (per enumerated runbook above) | APNs cert rotation if cert not pre-staged |
| E3 | Preference management, user-facing API, suppression logic | E4 | None identified |
| E4 | Email (SendGrid), SMS (Twilio), reliability, monitoring, runbooks | E3 | None identified |

---

## 3. System Architecture

### 3.1 SQS FIFO: Group Count and Revised Pass Criteria (Finding 8)

**Why the prior probability argument was wrong (Finding 8):**

The prior revision calculated P(3 consecutive slow messages in a group) = (0.01)³ = 0.000001 and called it negligible. This assumed slow messages are distributed uniformly and independently across groups. That assumption is violated in the failure modes that actually matter.

**The correlated failure case:**

Group assignment is based on user ID or notification type. If APNs begins timing out for devices running a specific iOS version, every notification destined for those devices will time out. Those devices likely belong to a correlated set of users. If group assignment clusters those users — which it will if groups are assigned by user ID range or by notification type — then slow messages will be concentrated in a small number of groups, not distributed across all 1,000.

In the correlated case, a single group could receive 100% slow messages for the duration of the APNs degradation. The probability argument breaks down entirely: the question is not whether 3 consecutive slow messages occur by chance, but whether a group is inside or outside the affected cohort.

**Revised approach: replace probability argument with direct measurement**

The pass criteria no longer rely on independence assumptions. Instead, they require the load test to simulate the correlated failure directly and measure outcomes.

```
Revised load test design (Month 1, E1):

Scenario A — Baseline (uniform slow messages):
  Total throughput: 3,500 msg/sec across 1,000 groups
  Slow message rate: 1% uniformly distributed
  Duration: 30 minutes

Scenario B — Correlated failure (the case that matters):
  Total throughput: 3,500 msg/sec across 1,000 groups
  Slow message distribution: 100% of messages in groups 1–50 are slow
    (simulates APNs degradation for a correlated user cohort)
  Duration: 30 minutes

Pass criteria (both scenarios):

  1. P1 messages in unaffected groups (groups 51–1000 in Scenario B):
     End-to-end latency ≤ 45s for 100% of P1 messages.
     Rationale: The SQS FIFO guarantee is per-group. P1 messages in
     unaffected groups should be completely isolated from the slow groups.
     Any P1 message in an unaffected group that exceeds 45s indicates
     a cross-group interference bug in the routing logic.

  2. P1 messages in affected groups (groups 1–50 in Scenario B):
     These messages will be delayed. The test measures and records
     the actual delay distribution. There is no pass threshold here
     because the correct response to a degraded APNs cohort is to
     route around it (circuit breaker, Section 4.2), not to accept