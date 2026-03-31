# Notification System Design Proposal — Revision 5
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses nine critic findings from Revision 4. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **`signal` module used but never imported** — `import signal` added to the import block.

2. **Watchdog 2-second grace period is ungrounded** — The grace period is now derived from the remaining time budget after the watchdog fires: `visibility_timeout − watchdog_fires_at − cleanup_margin`, which is deterministic given the timing constants already established.

3. **`asyncio.shield` defeats `asyncio.wait_for`** — `asyncio.shield` removed. The task is cancelled directly. The consequences of direct cancellation are stated explicitly.

4. **SIGTERM collateral damage to co-resident messages is unspecified** — Each worker runs one in-flight message at a time. The architectural decision enabling this is stated explicitly, along with its cost.

5. **SMS attack ramp rate borrowed from a different company's incident** — The external ramp rate is replaced with a conservative bound derived from this system's own API-layer rate limits. The Lambda secondary threshold is derived from the same basis.

6. **Lambda test has no pass criteria** — Pass criteria defined: propagation latency bound, idempotency verification, false-positive rate on legitimate spikes, and rollback verification.

7. **E2 backup for APNs/FCM API layer asserts coverage without demonstrating it** — The runbook content E1 must know to provide backup coverage is enumerated. Honest gaps are stated.

8. **P1 blocking probability ignores group assignment skew** — The independence assumption is withdrawn. Pass criteria are rewritten to handle the correlated failure case directly.

9. **Proposal ends mid-sentence — Finding 5 (retry deduplication) unresolved** — Complete resolution provided: deterministic `notification_id` derivation, crash recovery path, and the specific race condition closed.

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

### SMS Cap and Email Fallback — Revised Alarm Derivation (Findings 5 and 6)

SMS is capped at 100K/day. Events exceeding the cap fall back to email.

**Why the prior derivation was wrong:**

The prior revision derived the alarm threshold using a ramp rate of 16/sec/minute from a 2023 Twilio postmortem at a "comparable service." That figure describes how fast an attacker ramped against a different company's infrastructure, with different API-layer rate limits, different CAPTCHA friction, and different account verification requirements. Using it as a measured property of this system was not justified.

**Revised derivation using this system's own constraints:**

The binding constraint on how fast an attacker can generate SMS volume against this system is this system's API-layer rate limiting. We control the API rate limiter. Its limits are known.

```
System constraints:
  API rate limit per authenticated user:        10 req/sec
  API rate limit per IP (unauthenticated):       5 req/sec
  Max concurrent attacker IPs before WAF fires: 500
    (CloudFront WAF rule: 500 distinct IPs with anomalous patterns
     within a 1-minute window)

Conservative worst-case:
  Before WAF fires: 500 IPs × 5 req/sec = 2,500 req/sec
  Each request triggers at most 1 SMS.
  WAF response time: ≤ 1 minute (CloudFront propagation SLA).

  In the worst case, an attacker sustains 2,500/sec for 60 seconds
  before WAF blocks them. This is a step function, not a gradual ramp.
  The attacker is at full volume from the first second.

Consequence for threshold derivation:
  A gradual-ramp model with headroom arithmetic does not apply.
  The alarm must fire fast enough that the response window begins
  before WAF has failed to fire.

Alarm structure:
  Primary alarm: 200/sec
    Normal peak SMS volume is 3.6/sec (derived above).
    200/sec is 55× normal peak — unambiguously anomalous.
    At 200/sec, WAF has not yet fired. The alarm gives on-call
    visibility before WAF automation takes over.

  Secondary alarm / automated response: 800/sec
    If volume reaches 800/sec, either WAF has not fired or the
    attacker is using authenticated accounts (bypassing IP-based WAF).
    Human response within 25 minutes is not guaranteed.
    Lambda auto-lowers the SMS cap to 10K/day.

Honest residual risk:
  If an attacker uses authenticated accounts, the IP-based WAF does
  not fire. Reaching 800/sec with authenticated accounts requires 80
  compromised accounts. Account compromise at that scale should be
  detectable via the account anomaly detection system (separate system,
  not in scope here). If it is not detected, the Lambda fires at
  800/sec regardless.
```

**Email fallback capacity validation:**

- Normal email volume: 4M/day ≈ 46/sec average, 138/sec at 3× peak
- SMS cap fallback email at most 100K/day ≈ 1.2/sec average, 3.6/sec at peak
- Combined peak: 141.6/sec — well within SendGrid Pro tier limit of 1,000/sec

**Lambda pass criteria:**

```
All four criteria must pass:

1. Propagation latency:
   Trigger: Inject synthetic CloudWatch metric event at 800/sec threshold.
   Pass: SMS cap change propagates to the rate limiter config store
         within 60 seconds of Lambda firing.
   Fail: Propagation > 60 seconds, or Lambda does not fire.

2. Idempotency:
   Trigger: Fire the Lambda 5 times within 10 seconds.
   Pass: SMS cap set to 10K/day exactly once. Subsequent invocations
         log "cap already set" and exit cleanly.
   Fail: Cap written multiple times, or any invocation errors.

3. False-positive rate on legitimate spikes:
   Trigger: Inject synthetic spike to 700/sec for 5 minutes,
            then return to baseline.
   Pass: Lambda does not fire. Primary alarm fires and clears.
   Fail: Lambda fires during the spike.

4. Rollback verification:
   Pass: Cap restored to 100K/day within 5 minutes of runbook
         execution without a deployment.
   Fail: Restoration requires a deployment or takes > 5 minutes.

Environment: Staging. Responsible: E4 (primary), E3 (witness).
Frequency: Quarterly, and after any change to the Lambda or the
rate limiter configuration store.
```

---

## 2. Team Allocation

### E2 Backup Scope (Unchanged from Revision 4)

E2's backup scope is limited to AWS console operations. The equivalence between environment variable changes and console operations was withdrawn in Revision 4 and remains withdrawn.

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

**Honest consequence:** If E1 is unavailable during a queue backlog that requires concurrency adjustment, E2 cannot resolve it without a deployment. The correct response is to increase visibility timeout via the SQS console to slow redelivery and escalate to E1.

### E1 APNs/FCM Backup Coverage (Finding 7)

Coverage is only meaningful if E1 can execute specific failure responses without assistance. The following are the most likely APNs/FCM failures requiring out-of-hours response:

```
APNs failures E1 must be able to handle:

1. APNs certificate expiry
   Location: AWS Secrets Manager, path /notifications/apns/cert
   Check expiry: openssl x509 -noout -dates -in <cert>
   Rotation: Runbook RB-04. Requires E2 to have pre-staged the next
   certificate in Secrets Manager before rotation. If not pre-staged,
   E1 cannot complete rotation alone. This is an honest gap.
   Alert: CloudWatch alarm on APNs 403 rate > 1% over 5 minutes.

2. FCM token invalidation wave
   Symptoms: FCM returns 404 (NotRegistered) for a large percentage
   of tokens within a short window, typically after an app update.
   Response: FCM 404s trigger async token deletion (Redis key:
   device_tokens:{user_id}). Lag between 404 receipt and deletion
   is bounded by the worker's ack cycle. Duplicate 404s during the
   lag are expected and not a pipeline failure.
   E1 must know: deletion is in worker/token_lifecycle.py,
   function handle_fcm_not_registered. E1 reads metrics; no code change.

3. FCM HTTP/2 connection pool exhaustion
   Symptoms: FCM dispatch latency spikes; watchdog fires repeatedly.
   Response: Reduce FCM_POOL_SIZE env var (requires deployment — E1
   scope) or restart workers to reset connections (ECS console — E2
   can do this while E1 is paged).
   E1 must know: FCM_POOL_SIZE defaults to 50 in worker/fcm_client.py.
   Reducing to 20 is safe.

4. APNs HTTP/2 stream hang
   Response: Watchdog handles automatically. E1 reads the
   WATCHDOG_FIRED alarm, confirms it is APNs-related via the
   notification_id in the log, and monitors whether the rate is
   increasing.
   If WATCHDOG_FIRED rate > 10/minute: APNs endpoint is degraded.
   Check Apple's system status page. If degraded, reduce
   APNS_DISPATCH_BUDGET from 8s to 4s to fail faster.
   This requires a deployment — E1 scope.
```

**Honest gap:** APNs certificate rotation requires E2 to have pre-staged the next certificate. If E2 is unavailable and the certificate has expired, E1 cannot complete rotation without access to Apple's developer portal. Mitigation: E2 stages the next certificate 30 days before expiry. E4 has read-only access to the developer portal to verify staging — E4 cannot complete rotation but can confirm whether a pre-staged certificate exists, which determines whether E1 can proceed.

| Engineer | Primary Responsibility | Backup Coverage Provided By | Known Gaps |
|----------|----------------------|----------------------------|------------|
| E1 | Core pipeline: SQS infrastructure, routing logic, delivery workers | E2 (console operations per above) | None for pipeline operations |
| E2 | Push integrations: APNs, FCM, token management | E1 (per enumerated runbook above) | APNs cert rotation if cert not pre-staged |
| E3 | Preference management, user-facing API, suppression logic | E4 | None identified |
| E4 | Email (SendGrid), SMS (Twilio), reliability, monitoring, runbooks | E3 | None identified |

---

## 3. System Architecture

### 3.1 SQS FIFO: Group Count and Revised Pass Criteria (Finding 8)

**Why the prior probability argument was wrong:**

The prior revision calculated P(3 consecutive slow messages in a group) = (0.01)³ = 0.000001 and called it negligible. This assumed slow messages are distributed uniformly and independently across groups. That assumption is violated in the failure modes that actually matter.

Group assignment is based on user ID or notification type. If APNs begins timing out for devices running a specific iOS version, every notification destined for those devices will time out. Those devices likely belong to a correlated set of users. If groups are assigned by user ID range or notification type, slow messages will be concentrated in a small number of groups, not distributed across all 1,000. In the correlated case, a single group could receive 100% slow messages for the duration of the APNs degradation. The probability argument breaks down entirely.

**Revised approach: simulate the correlated failure directly.**

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
   Rationale: SQS FIFO guarantees are per-group. P1 messages in
   unaffected groups must be completely isolated from slow groups.
   Any P1 message in an unaffected group exceeding 45s indicates
   a cross-group interference bug in the routing logic.

2. P1 messages in affected groups (groups 1–50 in Scenario B):
   These messages will be delayed. The test measures and records
   the actual delay distribution. There is no pass threshold here
   because the correct response to a degraded APNs cohort is to
   route around it (circuit breaker, Section 4.2), not to accept
   the delay as normal. The test establishes the baseline delay
   so the circuit breaker trip threshold is calibrated against
   measured data, not assumption.

3. Blocking duration per slow message: ≤ visibility_timeout (15s)
   If a slow message blocks longer than its visibility timeout,
   timeout handling has failed. This is a pipeline correctness
   failure.

4. AWS throttling: 0 events at 3,500 msg/sec.

5. P1 messages appearing in P0 groups: 0.
   Any occurrence means the priority classification logic is broken.
```

### 3.2 Hung-Call Mitigation — Thread-Based Watchdog (Findings 1, 2, 3, 4)

**The prior watchdog had four problems:**

1. `signal` module used but not imported.
2. The 2-second grace period before `os.kill` was arbitrary.
3. `asyncio.shield` prevents `asyncio.wait_for` from cancelling the underlying task, defeating the timeout.
4. SIGTERM collateral damage to co-resident messages was unspecified.

**Architectural decision enabling clean SIGTERM:** Each worker process handles exactly one in-flight message at a time. This costs throughput — a worker is idle during I/O wait rather than multiplexing coroutines. The benefit is that SIGTERM kills exactly one in-flight message with no collateral damage to other messages. The killed message's visibility timeout expires and SQS redelivers it to another worker.

**The failure mode the watchdog addresses:** A worker calls APNs or FCM. The HTTP/2 stream hangs at the network layer. The asyncio event loop is waiting on I/O that will never complete. `asyncio.wait_for` cannot fire its timeout because the event loop is not advancing. The visibility timeout expires. A second worker picks up the