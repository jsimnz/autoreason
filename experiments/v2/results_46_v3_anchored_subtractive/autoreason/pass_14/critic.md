## Real Problems Found

### 1. Staleness Threshold Formula Is Wrong

The formula in the comment is `PUBLISH_INTERVAL_SECONDS × MAX_RETRIES × BACKOFF_CEILING_SECONDS + 30 = 60 × 3 × 4 + 30 = 750s`. But the actual retry window is not `MAX_RETRIES × BACKOFF_CEILING_SECONDS`. With exponential backoff capped at 4 seconds, three retries sleep for `min(2,4) + min(4,4) + min(8,4) = 2 + 4 + 4 = 10 seconds`, not 12. More importantly, the threshold is supposed to represent how long the publisher can be failing before the health check fires — but 750 seconds is **12.5 minutes**. A publisher that has been silently failing for 12 minutes before ECS restarts it is not meaningfully monitored. The margin chosen makes the health check nearly useless for operational response.

### 2. `publish_once` Uses a Single `now` for All Redis Reads Across Multiple Calls

The `today` date string is derived from `now`, which is captured once in `run()` before `publish_once` is called. But if the clock ticks past midnight during a slow publish cycle (Redis slow, DynamoDB slow, CloudWatch retrying), `_get_redis_counter` is still using yesterday's date key while the actual Redis counters may have rolled over. The proposal does not define how Redis counters are keyed or when they roll over, so this boundary condition is unexamined.

### 3. `_get_current_cap` Raises on First Call With No Cache, But This Is Not Handled in `publish_once`

If DynamoDB fails on the very first publish cycle, `_get_current_cap` raises. `publish_once` does not catch this — the exception propagates to `run()`, which logs it and sleeps. The health file is never written. After 750 seconds ECS restarts. On restart the cache is empty again. If DynamoDB remains unavailable, the publisher loops in this state indefinitely without ever emitting metrics. The `CapReadHealthy` metric — which is supposed to alarm on DynamoDB failures — is never written to CloudWatch during a sustained DynamoDB outage. The alarm that is supposed to fire cannot fire because no data points arrive.

### 4. AUTH Sub-Cap Is Adjustable by E1 But the Total Constraint Is Not Revalidated at Adjustment Time

Section 2.2 says the AUTH sub-cap is "adjustable by E1 via validated procedure, Section 2.9" — but Section 2.9 is not present in this document. The total constraint `AUTH + SOCIAL ≤ 100K` is enforced at write time in DynamoDB, but the sub-cap values themselves are stored somewhere (DynamoDB, presumably) and the conditional write checks the running totals, not the cap configuration values. If E1 raises the AUTH cap from 20K to 90K without correspondingly reducing the SOCIAL cap, the configuration is inconsistent — both caps could be set above 50K — and the system would not reject the configuration change, only individual writes that breach the runtime total. The proposal does not describe how cap configuration changes are validated against the total constraint.

### 5. The Dead-Letter Queue for Conditional Write Failures Is Not Described

Section 2.1 and Section 2.5 both reference a dead-letter queue for failed conditional writes, and Section 2.7 references runbook step RB-06. Section 2.5 is described as containing "the Lambda code and the full failure path." Section 2.7 and the Lambda code are not present in this document. The conditional write failure path — stated as a resolution to a prior finding — is referenced but not actually specified here.

### 6. Redis Counter Reads Are Described as "Non-Blocking" But Redis Is Also the Circuit Breaker

The proposal states the publisher reads Redis counters via "cheap, non-blocking reads" and separately that "the Redis circuit breaker still gates dispatch" if the publisher is down. But the circuit breaker and the publisher read the same Redis counters. If Redis is degraded in a way that causes slow reads rather than outright failure, the publisher's `publish_once` may block or time out — but the proposal sets no timeout on Redis reads. A hung Redis read inside `publish_once` would cause the health file to go stale eventually, but during the 750-second window before ECS restarts, CloudWatch would receive no updated metrics while the circuit breaker might also be behaving incorrectly.

### 7. `CapReadHealthy` Alarm Is Referenced but Not Defined

Finding 2's resolution states the publisher emits `CapReadHealthy` and that "CloudWatch alarms on SMS consumption are not fed incorrect data silently." Finding 3's resolution states that `INSUFFICIENT_DATA` is now treated as an alarm state "with the full alarm definition specified." But no alarm definition for `CapReadHealthy` appears in this document. It is described as alarming "independently" but the alarm threshold, period, evaluation periods, and action are not given.

### 8. The 3× Headroom Rationale for the AUTH Cap Is Circular

The 20K AUTH cap is justified as ≥ 3× the observed p95 of ~4,800/day. The document then states: "If actual AUTH volume is 9,600/day (2× the p95 estimate), the 20K cap still provides 2× headroom." This is presented as evidence of robustness, but 2× headroom on a hard cap that causes AUTH SMS to fail completely when exhausted — for OTP codes and login alerts — is not a safety margin, it is a description of how far off the estimate can be before authentication breaks. The document does not address what happens to users who cannot authenticate when the AUTH cap is exhausted, nor is there a defined fallback for AUTH SMS the way there is for SOCIAL SMS.