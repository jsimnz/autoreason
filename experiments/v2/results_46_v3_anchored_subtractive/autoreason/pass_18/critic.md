## Real Problems Found

### 1. The Staleness Threshold Derivation Has an Arithmetic Error

The document states MAX_RETRIES = 3 means 3 total attempts, with sleep after attempt 1 and attempt 2 only. But then it calculates retry sleep as "2 sleeps after attempts 1 and 2" = 2 + 4 = 6s. If there are 3 attempts and sleep occurs after each non-final attempt, that is 2 sleep intervals — correct. But the backoff formula used is `min(2^attempt_number, 4)`. The document shows sleep after attempt 1 as `min(2^1, 4) = 2s` and after attempt 2 as `min(2^2, 4) = 4s`. The exponent base is the attempt number, not the retry count. This is not defined anywhere. Whether `attempt_number` is 0-indexed or 1-indexed, and whether the exponent tracks attempts or retries, is never established. A different reasonable interpretation (0-indexed: `min(2^0, 4)=1s`, `min(2^1, 4)=2s`) produces a different total and a different staleness threshold.

### 2. The DynamoDB Cap Read Timeout Is Unsupported

The staleness derivation lists a 10s upper bound for DynamoDB cap read, described as "measured from auth service in same VPC." No measurement methodology, percentile, sample size, or date is given. This is the same class of unsupported estimate the document criticized WAF throughput claims for. If this number is wrong and the actual p99 latency is higher, the staleness threshold is too low and the health check produces false positives.

### 3. The Test for Shared Constants Cannot Catch the Actual Failure Mode It Claims to Catch

The test asserts that `publisher.constants` does not have `REDIS_SOCKET_TIMEOUT_SECONDS` as an attribute. But if a developer adds a local definition in `publisher/constants.py` *after* the import line, the import still succeeds and the local name shadows the imported one at runtime — but `hasattr(pub_const, 'REDIS_SOCKET_TIMEOUT_SECONDS')` returns `True` for the imported name, not only a locally defined one. The test will always pass regardless of whether the value comes from the shared module or a local override, because `hasattr` cannot distinguish between an imported attribute and a locally defined one.

### 4. The AUTH Cap Headroom Rationale Is Circular on Post-Launch Baseline Shift

The document acknowledges that post-launch engagement increases may raise AUTH SMS volume, then states the 4× multiplier "provides margin for the post-launch baseline shift." But the magnitude of the post-launch shift is entirely unknown — the document provides no bound on it. If engagement increases drive AUTH SMS volume above 20K/day before the week-2 baseline is established, the cap is exhausted and OTP delivery via SMS fails. The 4× headroom is not justified as sufficient for an unknown shift; it is asserted as sufficient.

### 5. The AUTH Sub-Cap Adjustment Procedure on Post-Launch Baseline Shift Is Underspecified

The document states: "If the post-launch week-2 baseline shows p95 above 5,000/day, the AUTH cap is raised before the month-1 checkpoint and the SOCIAL cap is reduced proportionally." The SOCIAL cap floor is stated as 10K/day (adjustable by Lambda down to 10K). If AUTH p95 comes in high enough that raising AUTH to cover it would reduce SOCIAL below 10K, the procedure does not say what happens. The constraint is stated but the resolution is not.

### 6. The Document Is Truncated

The document ends mid-sentence: "It is not a sidecar. It" — Section 2.3 is incomplete. Sections 2.4 through 2.9 are claimed to exist and are referenced repeatedly throughout the document, but none of them appear. The executive summary explicitly lists resolution of finding 5 as "All six sections are present in this document. Each is complete. There is no forward reference to a section that does not appear below." This claim is false. The document has the same structural problem it claimed to fix.

### 7. The Review Action Threshold Is Asymmetric Without Justification

The review triggers a cap-raise ticket if p95 grows more than 20% from the previous baseline. There is no corresponding threshold for p95 shrinking. If AUTH volume drops significantly, the AUTH sub-cap remains unnecessarily large, consuming headroom that the SOCIAL sub-cap could use. The asymmetry is not acknowledged or justified.

### 8. The "Conservative" SMS Blackout Estimate Is Referenced but Not Present

The executive summary states finding 9 is resolved: "The estimate is replaced with a bounded range derived from documented ElastiCache failover behavior, DNS TTL, and connection pool reconnect logic." That derivation does not appear anywhere in the visible document. It is presumably in the truncated sections, but its absence means the claim of resolution cannot be verified and the estimate is still missing from the document as submitted.

### 9. The Fallback for AUTH Cap Exhaustion Is Deferred Without a Completion Guarantee

Section 2.1 states the AUTH sub-cap fallback is "specified in Section 2.6." Section 2.6 does not appear in the document. The fallback for complete OTP SMS failure — a user-facing security-critical path — is unspecified in the submitted document. This is not a forward reference to a later document; the executive summary claims all sections are present.

### 10. The Provisional Baseline Query Has No Stated Timezone or Boundary Condition

The Twilio export query filters on `date_range=last_90_days`. Twilio log timestamps are UTC. If the auth service operates in a region where user activity peaks near midnight UTC, day boundaries in the export will split peak periods across dates, artificially lowering per-day counts. The query does not account for this, and the p95 of 4,800/day may understate actual peak-day volume. The document does not acknowledge this.