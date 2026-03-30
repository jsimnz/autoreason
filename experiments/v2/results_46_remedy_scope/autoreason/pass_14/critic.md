## Real Problems

### 1. The Starvation Prevention Mechanism Is Broken by Design

The token bucket guarantees P2/P3 minimum rates of 200/sec and 50/sec fleet-wide, but the document never explains how these tokens are consumed relative to P0/P1 work. If workers are priority-ordered (drain P0 before P1 before P2), a single worker cannot simultaneously drain P1 and guarantee P2 minimums. The fleet-wide guarantee only works if some workers are *dedicated* to P2/P3 regardless of P0/P1 depth. The document describes per-channel, per-priority worker pools in the executive summary but never actually specifies whether workers are also split by priority tier. This is the central mechanism of starvation prevention and it's never resolved.

### 2. The Document Is Cut Off Mid-Sentence

Section 2.2 ends: "In the extreme case where P2 queue depth reaches the TTL" — and stops. This is a submitted design document with an incomplete section on a critical failure mode.

### 3. FCM Rate Limit Figure Is Stated as Fact Without Basis

"FCM's per-project rate limit is configurable up to ~10,000/sec" is presented as a concrete planning constraint, but FCM's actual rate limits are not publicly documented at this granularity and vary by project history, account standing, and negotiated agreements. Building the entire viral spike analysis around this number — including the conclusion that FCM is the binding constraint rather than worker capacity — is a structural problem. If the actual limit is 2,000/sec or 500/sec, the spike analysis and recovery timeline are wrong.

### 4. The Lua Script Is Referenced but Never Shown

The executive summary explicitly states the token bucket "check and consumption execute atomically in a single Lua script." That script never appears in the document. For a design that calls out atomic correctness as a core property, omitting the actual implementation means the correctness claim cannot be evaluated. The sweep process gets pseudocode; the more complex and correctness-critical atomic operation does not.

### 5. The Processing Sorted Set Is Introduced but Never Specified

The executive summary describes "a Redis Sorted Set for processing state" as a named architectural decision. Section 2.1 discusses the queue Sorted Set scored by enqueue timestamp, but the processing state Sorted Set — what it tracks, how workers interact with it, how it handles worker crashes, what prevents a message from being stuck in "processing" indefinitely — is never described. This is a significant gap for crash recovery and exactly-once delivery semantics.

### 6. The 16-Minute Worst-Case Delay Arithmetic Is Wrong

The document states: at 10,500/sec demand against 1,000/sec throughput, persisting for 10 minutes, P1 queue depth reaches ~570,000 messages. 10,500 - 1,000 = 9,500/sec accumulation × 600 seconds = 5,700,000 messages, not 570,000. The drain time estimate of "approximately 6 minutes" is also derived from the wrong queue depth figure. The entire quantified worst-case analysis in Section 2.1 is off by an order of magnitude.

### 7. Month 1 Acceptance of a Risk That May Be Unacceptable Is Never Escalated

The document states "accept the unmitigated risk for the first 60 days" for the pool exhaustion scenario, then immediately notes "if 16-minute DM delay under worst-case coincident failure is unacceptable, full payload storage in Redis is the correct architectural choice." But the actual arithmetic shows the delay is likely far longer than 16 minutes (see above). The decision to defer mitigation is presented as an engineering planning choice, but it has product and user-facing consequences that are never surfaced to a decision-maker. The document names a decision owner for traffic volume responses but not for this risk acceptance.

### 8. The Sweep Lock Extension Logic Is Incorrect

The code calls `lock.extend(120)` when elapsed exceeds 45 seconds, but the lock was acquired with a 120-second TTL. If 45 seconds have elapsed, the lock has 75 seconds remaining — extending it to 120 from the point of extension adds 45 seconds of coverage. But the sweep may then run for another 45+ seconds before hitting the 90-second overflow check. The extension logic assumes the lock library extends by a fixed duration from *now*, but does not account for how much time remains versus how much additional time the sweep may need. A sweep that takes 89 seconds will have extended the lock once at 45 seconds, giving it until ~165 seconds from start, which is fine — but a sweep that takes exactly 90 seconds triggers the overflow return without releasing the lock if the `finally` block's `lock.release()` is reached after the lock has already expired and been acquired by another instance.

### 9. The Capacity Shift Timing Figures Have No Stated Basis

"Manual, unrehearsed, 3 AM: 20–30 minutes" is presented with the same confidence as the quantified traffic model. These figures are not derived from anything — no incident history, no task breakdown, no reference. For a document that explicitly claims to quantify uncertainty and name assumptions, these are load-bearing numbers (they determine the risk window for the first 60 days) stated as if obvious.

### 10. Worker Specialization Creates an Unaddressed Operational Gap

Workers are specialized binaries per channel type, and the document acknowledges that scaling a channel requires deploying the correct binary. But the traffic response matrix specifies "provision additional worker instances" as a response to 45M–80M/day load without specifying *which* worker instances. If the overload is concentrated in push (the 70% channel), deploying generic "additional instances" does nothing. The matrix response is underspecified in a way that will cause confusion at exactly the moment it's needed.