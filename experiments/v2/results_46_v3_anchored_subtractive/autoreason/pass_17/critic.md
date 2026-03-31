Here are the real problems I found:

---

**1. The 17 notifications/user/day figure is unanchored**

"Industry avg for engaged social apps" is not a source. This number drives every downstream scale estimate — 50M/day, 1,750/sec peak, the sub-cap split, the Redis sizing. If the real figure is 10 or 25, the entire capacity model is wrong. No citation, no internal data, no sensitivity analysis.

---

**2. The 30% DAU/MAU ratio has the same problem**

Also called "industry avg" with no source. DAU/MAU ratios vary enormously by app type and market. A social app at 10M MAU could plausibly be anywhere from 15% to 60%. This is the second foundational assumption with no backing.

---

**3. The peak multiplier of 3× is asserted, not derived**

The table says "Morning/evening spikes" but gives no data. If the actual peak multiplier is 5× or 6×, the system is undersized at design time. No measurement, no reference, no percentile.

---

**4. The AUTH fallback (Section 2.6) is referenced repeatedly but does not appear in this document**

The document claims Section 2.6 defines the AUTH fallback — "in-app notification with OTP polling." This is security-critical behavior. The section is not present in the text provided. This is the same class of defect as the previous version's missing sections.

---

**5. Section 2.5 (Lambda code and failure path) is also missing**

The document references it explicitly: "See Section 2.5 for the Lambda code and the full failure path." It does not appear. The dead-letter queue behavior, the paging logic, and the exit path are described only in prose in 2.1, not in code anywhere shown.

---

**6. Section 2.7 (RB-06 runbook) is referenced but absent**

"See Section 2.7 (RB-06) for the runbook step" — not present. The manual intervention path for a failed conditional write is undefined in the actual document.

---

**7. Section 2.8 and 2.9 are referenced but not shown**

Both are cited for critical enforcement logic — the DynamoDB conditional write enforcing the total constraint (2.8), and the cap configuration write-time validation (2.9). Neither appears in the document as provided. The executive summary claims all six previously missing sections are now present. They are not all present here.

---

**8. The DynamoDB cap read upper bound of 10s is unexplained**

The staleness derivation states "10s (measured from auth service in same VPC)" for DynamoDB. No measurement data is shown. A cold DynamoDB SDK call in the same VPC taking 10 seconds would indicate a serious latency problem, not a normal operating bound. This number is suspicious and unsupported.

---

**9. The staleness threshold derivation assumes the health check fires immediately after a successful write**

The comment says "In the worst case, the health check fires immediately after the health file timestamp." This is actually the best case for the staleness check — it maximizes the time available before the next check. The worst case is that the health check fires just before a successful write, meaning the file age at check time is nearly one full good cycle plus the failed cycle plus the interval. The derivation may be computing the wrong bound.

---

**10. The test for constant consistency does not verify the values are actually used**

`test_redis_timeouts_are_shared_not_duplicated` checks that the attributes don't exist on the constants modules. It does not verify that the Redis client objects in publisher or circuit_breaker are actually instantiated with these values. A developer could import the shared constants and then pass hardcoded literals to the Redis constructor. The test would pass and the divergence would go undetected.

---

**11. The SOCIAL sub-cap floor of 10K has no justification**

The Lambda can reduce the SOCIAL cap "down to 10K" during an attack. Why 10K and not 0? If the SOCIAL path is under active attack, why is any floor maintained? There is no explanation of what 10K protects or what harm reducing below it would cause.

---

**12. The 20% growth threshold for triggering a cap review ticket is not connected to any consequence timeline**

If p95 grows 21% between checkpoints, a ticket is raised "before the next checkpoint." Checkpoints are separated by months. A ticket raised at month 1 due to month-1 data doesn't need to be resolved until month 3. No SLA on ticket resolution is defined.

---

**13. The publisher architecture section is cut off mid-sentence**

"It is not a sidecar. It" — the document ends here. This may be a transcription artifact, but it means the publisher architecture is incomplete as presented.