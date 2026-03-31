## Real Problems with This Proposal

### 1. The 30% DAU/MAU Ratio Is Doing Heavy Lifting Without Justification

The entire in-app volume estimate (15M/day) rests on a 30% DAU/MAU ratio described only as typical for "social apps." This is a wide category. A messaging-first app and a photo-sharing app have dramatically different ratios. The document acknowledges it will validate traffic assumptions in month 2, but the infrastructure is being sized and provisioned before that validation. If the actual ratio is 50%, in-app volume is 25M/day, not 15M. The document doesn't bound the error or state what happens to the design if the ratio is materially wrong.

### 2. The Peak Window Assumption Is Circular

The document states that morning and evening peaks together account for approximately 60% of daily volume across a 4-hour window, then uses this to derive the design ceiling. It acknowledges this is an assumption to be validated in month 2. But the design ceiling—4,250/sec—is already fixed. There's no stated process for revising infrastructure provisioning if month 2 data shows the peak window is actually 2 hours, not 4, which would roughly double the sustained peak rate. The document says "revise the traffic model" but doesn't say what gets re-provisioned or when.

### 3. The 2× Burst Multiplier Is Justified by the Same Scenarios It's Supposed to Cover

The document states the 2× multiplier handles "momentary intra-window spikes" from viral events and "traffic model error." But traffic model error is already addressed by the sustained peak calculation being based on conservative estimates. Applying the same multiplier to cover both a named operational scenario and the possibility that the model is wrong means the multiplier is doing double duty without any analysis of whether 2× is actually sufficient for viral spike events. A viral post on a 10M MAU social app could plausibly produce much more than 2× the window average for 30–60 seconds. The multiplier is asserted, not derived.

### 4. P0 Volume Estimate Has No Empirical Basis

P0 volume is estimated at 2% of push volume, described as an estimate to be measured once production data is available. But the SMS budget, the hard cap, and the alert thresholds are all derived from this number. The stress scenario uses a higher push failure rate but doesn't vary the P0 volume estimate at all. If P0 volume is actually 5% of push volume (still plausible for a social app with active DMs and security events), the baseline SMS cost nearly triples before accounting for failure rates. The budget analysis treats one uncertain input as fixed while stress-testing another.

### 5. The SMS Hard Cap Logic Has a Security Hole It Acknowledges and Doesn't Resolve

The document explicitly states that suppressing SMS fallback for a failed login alert because the budget cap is hit is "a security regression," and then sets the hard cap at $30,000/month with fallback suppression above that cap. The stress scenario already shows this cap can be breached under plausible conditions. The resolution—treat it as a P1 incident and page on-call—doesn't change the fact that during the time between cap breach and incident resolution, security-critical SMS notifications are being suppressed. The document identifies the problem and then accepts it anyway.

### 6. E1's Dual-Role Conflict Is Not Actually Resolved

The document says the conflict requires three things: infrastructure stability, E2 having triage capability, and a documented handoff protocol. But then it acknowledges: "If a novel infrastructure failure occurs simultaneously with a push incident during E1's Gate 3 week, we have a genuine resource constraint." The "resolution" is that simultaneous novel failures are unlikely. This is a restatement of acceptable risk, not a resolution. The document criticized an earlier approach for restating the problem rather than solving it, then does exactly that.

### 7. The Taxonomy Owns Too Many Downstream Dependencies for a 3-Day Timeline

The notification type taxonomy is described as a hard prerequisite for P0/P1/P2 classification, SMS gate enforcement, and channel routing logic. It's allocated to days 1–3 of week 1 for a single engineer (E1). The document also identifies a structural risk—the P0 priority signal and SMS fallback eligibility may need to be separated—that requires explicit resolution during this same window. Three days for a single engineer to define a taxonomy that gates every downstream component, with a known structural ambiguity to resolve, is not a realistic allocation. The document doesn't acknowledge this tension.

### 8. Gate 3 Is Not Actually a Gate

Gates 1 and 2 have explicit failure conditions that defer launch. Gate 3—solo on-call during the first week of channel operation—has no failure condition. "Problems surfaced during solo on-call are fixed before the channel reaches full traffic" is not a gate; it's a description of normal operations. If the coverage partner fails to handle incidents competently during Gate 3, there's no stated consequence, no deferral condition, and no escalation path. The gate structure is asymmetric.

### 9. The Runbook Maintenance Section Is Incomplete

Section 2.5 ends mid-sentence: "The monthly review" — the document is cut off. This is the section governing how runbooks stay current through month 6, which the document identifies as a primary risk mitigation for the bus factor problem. The incompleteness isn't a minor formatting issue; it means the maintenance process for a stated primary risk mitigation is undefined.

### 10. Cross-Training Is Dismissed Without Addressing Knowledge Transfer Timing

The document states that "cross-training in the sense of watching someone else work does not constitute coverage ability" and replaces it with gate-verified runbook execution. This is reasonable. But the gates are scheduled relative to channel launch dates, and the document doesn't specify when coverage partners actually learn the systems they'll be covering. Gate 1 requires a coverage partner to execute runbooks independently in staging—but there's no point in the timeline where the coverage partner is allocated time to learn the system before being tested on it. The gates test readiness without allocating time to achieve it.