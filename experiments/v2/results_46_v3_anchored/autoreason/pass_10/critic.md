## Real Problems with This Proposal

### 1. The "Structural Insight" on Email Volume Is Circular

The document claims email costs are "driven primarily by MAU count and send-frequency policy, not engagement rate" — then immediately admits this is a consequence of holding the 30% re-engagement send rate constant across scenarios. The "insight" is just the assumption restated. The table doesn't demonstrate a structural property; it demonstrates what happens when you fix the variable that would change the result. The document acknowledges this in the same paragraph, which means the "derived structural insight" heading is misleading.

### 2. The Opt-Out Violation Number Is Presented as Acceptable Without Basis

The executive summary says legal must assess whether 180–900 opt-out violations per day "constitutes a compliance problem." Under CAN-SPAM, TCPA, and GDPR, the question isn't whether a frequency is a compliance problem — individual violations are the problem. Framing this as a threshold question for legal to assess obscures that the system is designed to knowingly send messages to people who have opted out, at a rate of potentially 900 per day. "Legal must assess the number" is not a risk mitigation; it's a liability acknowledgment dressed as a process step.

### 3. The 69-Minute Delay Bound Depends on a Spike Model That Isn't Validated

The spike model assumes 5% of daily volume arrives in 10 minutes. There is no basis given for this figure — not historical data, not industry benchmarks, nothing. The entire drain time calculation, the "acceptable for social notifications" conclusion, and the priority queue recommendation all rest on this number. If the actual spike is 10% of daily volume in 5 minutes, the backlog and drain time are roughly 8× worse. The model is presented with false precision.

### 4. Worker Count Math Ignores Parallelism Constraints

The calculation concludes 5 workers sustain 2,800/sec by dividing throughput by per-worker capacity. This assumes each worker's 150ms provider API call is non-blocking and that a single worker can pipeline 100 notifications into a single FCM/APNs batch call with 150ms total latency. FCM HTTP/2 batch limits and APNs connection limits per worker are not addressed. Five workers making ~6 batch calls per second each to FCM is a specific operational assumption that may hit per-project rate limits — the exact problem the design claims to solve with per-channel queues.

### 5. The Broadcast Cap Has No Enforcement Mechanism Described

The document states a hard cap of 100K recipients per notification job. It names this as policy and says a product owner must be the "decision gate owner." There is no description of where this cap is enforced technically — not in the queue layer, not in an API validation step, not in a job submission interface. A policy with no enforcement point is not a hard cap.

### 6. Default C Is Described as Unavailable, Then Left as an Option

The executive summary says Default C "cannot exist as a placeholder" and creates a "circular finalization dependency" — then lists it as one of three available choices for stakeholders. If it's genuinely unavailable without a named person, it shouldn't appear as a selectable option in an unfilled document. Its presence invites exactly the placeholder condition the document warns against.

### 7. The SendGrid Fallback Is Not Actually Scoped

The document mentions self-hosted email (Postfix + SES relay) as an alternative if SendGrid enterprise pricing is unacceptable, then dismisses it by saying the team "may not have capacity to absorb" the operational complexity. With 4 engineers and a 6-month window, this is a real constraint — but the document doesn't assess whether the team actually has that capacity or what it would cost in engineering time. It's listed as an option while being functionally ruled out, which means there's no real fallback if the SendGrid contract fails.

### 8. The Table in Section 1.1 Is Cut Off

The full sensitivity matrix ends mid-row at the 25%/15 row. This is a document completeness failure, but more importantly, the rows that would show the 35% DAU/MAU scenarios — the ones driving the "sustained overload" discussion — are missing. The text references the 35%/15 scenario (3,498/sec) as a critical scaling boundary, but the table that should show it doesn't exist in the document.

### 9. Month 2 Calibration Is Referenced as a Mechanism but Never Defined

The document refers to "the Month 2 calibration checkpoint" as the mechanism for detecting trajectory toward sustained overload. This checkpoint is not defined anywhere in the visible document — not what metrics trigger action, not what the action is, not who owns it. Referencing an undefined mechanism as a risk mitigation is not a mitigation.

### 10. The 90% Concentration Assumption Is Called Conservative Incorrectly

The document says the 90% concentration assumption is "conservative for a globally distributed app" and that global distribution is a "favorable deviation." This conflates the direction of conservatism. A 90% concentration in 4 hours produces the *highest* peak rate — it is conservative in the sense of worst-case for infrastructure sizing. But calling global distribution "favorable" is only true for infrastructure cost; it may be unfavorable for latency, data residency, and regional compliance requirements. The document treats a US-centric architecture as a safe default without acknowledging that a social app at 10M MAU almost certainly has non-trivial international users for whom this is a design gap, not a favorable deviation.