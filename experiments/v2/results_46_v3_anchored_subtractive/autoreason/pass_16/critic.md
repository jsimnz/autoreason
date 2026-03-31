## Real Problems Found

### 1. CloudWatch Call Timeout Is Undefined and the Derivation Is Cut Off

The staleness threshold derivation is literally truncated mid-sentence at "× MAX\_RET". The document claims in Finding 1 that the threshold is corrected to 220s with a step-by-step derivation. That derivation does not exist in the document. The 220s number is asserted but never derived. The original criticism is unresolved.

Additionally, the derivation in progress acknowledges that the CloudWatch SDK timeout is not specified in constants — it falls back to the "30s AWS SDK default" — but this value appears nowhere in the codebase shown. An undocumented implicit dependency on SDK defaults is the same kind of gap the document claims to have fixed for other values.

---

### 2. The Staleness Threshold Number Is Not Present in the Document

Section 2.3 discusses the derivation but the constant `STALENESS_THRESHOLD_SECONDS = 220` never appears in any code block. The health check logic that reads this value is never shown. The document claims the prose and the number now match, but neither the number nor the prose that uses it is actually present.

---

### 3. The `publish_once` Function Is Still Not Shown

Finding 2 claims the complete `publish_once` function is now shown. It is not present anywhere in the document. The health file write timing is described in prose but the code is absent. The resolution claim is false.

---

### 4. DynamoDB Conditional Write Does Not Actually Prevent TOCTOU for Cap Configuration Changes

Section 2.9 is referenced repeatedly as the place where cap configuration change validation occurs. Section 2.9 does not exist in the document — the section list ends before reaching it. The claim that cap constraint enforcement at configuration write time closes the TOCTOU window cannot be evaluated because the section is missing.

---

### 5. Sections 2.4 Through 2.9 Are Still Partially or Fully Missing

Finding 5 claims all sections are now present in full. The document ends abruptly mid-derivation. Sections 2.4, 2.5, 2.6, 2.7, 2.8, and 2.9 are all absent from the visible document. This is the same finding from the previous review, unresolved again.

---

### 6. The AUTH Cap Headroom Logic Contains a Numerical Inconsistency

The document states the 20K cap is set to "≥ 3× the observed pre-launch p95 (4,800/day)" and then immediately states "this is a 4× growth margin." 3 × 4,800 = 14,400, not 20,000. 20,000 / 4,800 = 4.17×. The document describes the same headroom as both 3× and 4× in consecutive sentences without acknowledging the difference. The 3× claim in the heading and the 4× claim in the body are inconsistent, and neither is clearly the operative number.

---

### 7. The Review Action Threshold Assigns the Ticket to E1 Regardless of Who Owns the Checkpoint

The review action threshold states: "the primary owner raises a ticket... assigned to E1." But the month-3 checkpoint has E2 as primary. If E2 performs the month-3 review and finds p95 has grown more than 20%, the procedure assigns the resulting ticket to E1, not E2. This reintroduces the single-owner concentration problem that Finding 7 claimed to resolve, specifically for the month-3 checkpoint.

---

### 8. The Redis Timeout Values Are Duplicated Across Separate Modules With No Enforcement of Consistency

The document explicitly states that `CB_REDIS_SOCKET_TIMEOUT_SECONDS = 5` and `REDIS_SOCKET_TIMEOUT_SECONDS = 5` are "the same values" but in "separate modules." There is no shared constant, no import relationship, and no test shown that would catch these diverging. The document acknowledges this duplication and treats it as acceptable without justification. If they diverge, the circuit breaker and publisher will have different timeout behaviors, which affects the failure mode analysis in Section 2.3.

---

### 9. The "3–5 Minute SMS Blackout" Estimate Is Not Supported

The document states ElastiCache failover "typically completes in 60–90 seconds" and derives a "3–5 minute" total blackout window. ElastiCache Redis failover times are not fixed — they depend on DNS propagation, connection pool reconnection logic, and whether the application uses cluster-aware clients. None of these are addressed. The 60–90 second figure has no cited source and no measurement basis comparable to the startup timing measurements cited elsewhere. The total window estimate is therefore unsupported.

---

### 10. The `INSUFFICIENT_DATA` Alarm Handling for Missing Cap Metrics Is Described but Never Defined

Finding 6 claims the alarm on `INSUFFICIENT_DATA` state handles the missing cap metric. Section 2.4, which would contain the CloudWatch alarm definitions, does not exist in the document. The behavior described in Finding 6's resolution cannot be verified. The resolution claim is self-referential to a missing section.