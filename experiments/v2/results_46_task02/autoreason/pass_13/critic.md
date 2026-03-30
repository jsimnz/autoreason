## Real Problems

### 1. The 75 notifications/sec per worker figure is unsupported

The derivation shows APNs theoretical throughput of 4,000/sec, then states "in practice… approximately 75 notifications/sec" with no arithmetic connecting the two numbers. The gap between 4,000 and 75 is a 98% reduction. The table showing latency components doesn't produce 75/sec — it describes latency per operation but never integrates those into a throughput figure. The number appears to have been chosen to make 24 workers produce the desired 1,800/sec floor, then justified backward.

### 2. The document is truncated mid-sentence

Section 1.2 ends with "Available for queue storage: 13.07 GB − 1.2 GB − " and the document cuts off. The Redis capacity and runway analysis is incomplete. This is presented as a "synthesized" and "completed" document in the executive summary, which is false.

### 3. The viral cohort 35% volume share assumption is never justified

The entire corrected derivation pivots on "the top 5% of users account for approximately 35% of all notifications — a standard heavy-tail assumption for social apps." No citation, no benchmark, no validation path. The prior approach was criticized for using 2× the all-user average, but the replacement assumption is equally ungrounded. The document acknowledges the prior figure was wrong but does not establish that 35% is right.

### 4. The 8× viral spike multiplier has no basis

The document lists "8× personal baseline" as the viral spike multiplier with "Could be 4–20×" as the uncertainty range. There is no derivation, no reference to historical events, no mechanism explaining why 8× rather than 4× or 20× is the point estimate. For a figure that drives the entire burst model, "no pre-launch data" is acknowledged but no methodology for arriving at 8× is provided.

### 5. The "50% simultaneous error" framing for the 2× stress case is circular

The document states the 2× case is the "base stress case because it requires inputs to be simultaneously wrong by 50% — plausible given no pre-launch historical data." But this is the justification for provisioning at 1,800/sec rather than 4,400/sec. If the 2× case is genuinely plausible, provisioning below it requires a stronger argument than "queue growth is manageable with a short alert-to-action window." The document does not quantify what "manageable" means in terms of notification latency or user impact during that window.

### 6. The APNs connection model is internally inconsistent

Each worker is described as holding "2 persistent APNs HTTP/2 connections (100 concurrent streams each = 200 in-flight APNs requests)." But the throughput derivation then uses "200 streams / 0.050 sec = 4,000/sec per worker" — treating all 200 streams as available simultaneously. HTTP/2 stream multiplexing over 2 connections with 100 streams each does not guarantee 200 simultaneous in-flight requests; APNs imposes its own concurrent notification limits per connection that are not addressed.

### 7. The 4-minute scaling claim is asserted, not derived

"Scaling from 24 to 59 workers takes approximately 4 minutes" is stated as the basis for the shedding trigger timing, but the figure is never derived. It references "3 additional c6g.2xlarge instances launched from pre-configured AMIs" but doesn't account for instance boot time, AMI hydration, health check delays, or the time for new workers to establish persistent APNs connections before they can process notifications.

### 8. The shedding trigger timing is referenced but never defined

The document repeatedly mentions "shedding trigger derivation below" and "shedding and scaling must engage within 10 minutes" but the actual trigger definition, threshold values, and alert-to-action sequence are never presented — either because the document is truncated or because they were never written.

### 9. The 17 notifications/DAU/day figure is load-bearing but unvalidated

The document acknowledges this figure "drives the entire sizing model" and calls for validation in month 1, but the design is built, sized, and provisioned on it before any validation occurs. The sensitivity analysis at 8/day and 35/day is referenced in Section 1.4 but Section 1.4 does not appear in the document.

### 10. The jemalloc size class correction is applied inconsistently

The document derives ~700 bytes per Redis entry, then states actual allocation will be ~768 bytes due to jemalloc size classes, and says runway calculations will use 768 bytes. But the runway calculation is in the truncated section, so it cannot be verified. More importantly, the 500 MB buffer described as covering "growth and fragmentation beyond the jemalloc model" is not derived — it is a round number appended after the jemalloc correction, suggesting the fragmentation model is not actually complete.

### 11. The receipt-independent delivery state machine is mentioned but never described

The executive summary lists "receipt-independent delivery state machine" as a key design decision that "resolves idempotency circular dependency during connection failures." The state machine itself — states, transitions, timeout values, retry behavior — does not appear anywhere in the document.