## Real Problems with This Proposal

### 1. The Circularity Is Unresolved, Not Managed

Section 1.2 openly admits the 17/day ceiling is derived from tier weights that "cannot be validated before the infrastructure decisions that depend on them." The document then anchors Phase 1 sizing to the 15/35/50 worst-case scenario and declares the circularity handled. It isn't. The worst-case tier split is itself derived from the same unvalidated benchmarks from "different products at different scales." Choosing the worst row of a table built on uncertain inputs doesn't escape the circularity — it just selects a specific uncertain number and calls it conservative.

### 2. The 1.7× Headroom Multiplier Has No Justification

The derivation applies a 1.7× multiplier to convert the weighted average to a planning ceiling. No basis is given for 1.7 specifically — not a percentile of historical variance, not a confidence interval, not a reference benchmark. The document acknowledges the inputs are uncertain but then applies a precise-looking multiplier as if precision is warranted. 1.5× or 2.0× would produce materially different sizing decisions and neither is argued against.

### 3. Graph Densification Risk Is Acknowledged but Unquantified and Unmitigated

Section 1.2 states that beta rates understate steady-state rates because the social graph is sparse, that "the magnitude of this suppression cannot be quantified before densification occurs," and that the 3× escalation threshold "is not derived from the suppression magnitude." This means the entire escalation framework is calibrated against a number known to be systematically low by an unknown amount. The document treats this as a disclosure rather than a problem. It is a problem: the thresholds could all be wrong in the same direction simultaneously, and the document provides no mechanism to detect this until after full launch.

### 4. The Document Is Cut Off Mid-Sentence

Section 2.3 ends with "**Result:** P1" and nothing follows. The P1 queue behavior analysis — which is cited as reconciling spike behavior with capacity thresholds — is incomplete. Any review of whether the system actually handles Scenario A is impossible because the conclusion is missing. This is not a minor editorial issue; it is the section where the sizing argument closes, and it doesn't close.

### 5. The 48-Hour False Positive Check Has a Structural Bias Problem

Section 1.2a states the default presumption favors confirming the finding, and that a valid artifact requires "a specific mechanism, not a general claim of noise." This sounds rigorous but creates a different problem: in a real beta, almost any spike will have a plausible specific mechanism available (a content event, a measurement window artifact, a single viral post). The protocol doesn't distinguish between a legitimate artifact explanation and a motivated one. Two engineers under schedule pressure will find specific mechanisms. The default-confirm framing doesn't prevent this — it just shifts where the rationalization occurs.

### 6. The Quiet Hours Rule Creates Unacknowledged Compliance Risk

Section 2.3 states quiet hours (10pm–7am) are enforced at the dispatcher and "cannot be disabled by user preference changes." For P3 notifications this may be reasonable. But the document doesn't address whether some P2 notifications — direct follows, mentions during late-night live events — might need to reach users who have explicitly opted into late delivery. More concretely, in some jurisdictions, suppressing a user's ability to receive their own account activity notifications regardless of their stated preference raises consent and data control questions. The document doesn't acknowledge this.

### 7. The Phase 2 Triggers Are Partially Redundant with the Decision Gate

Section 1.2 defines a decision gate with thresholds at 17, 25, and 51 notifications/day. Section 1.2 (Phased Procurement) then defines separate Phase 2 provisioning triggers based on whether observed rates are within 25%, 25–75% above, or more than 75% above Phase 1 sizing. These two frameworks use different reference points (absolute rate vs. relative to Phase 1 sizing) and different thresholds, and they are never reconciled. It is possible for both to be active simultaneously pointing to different actions, with no stated priority rule.

### 8. The P2 Collapse Threshold Is Arbitrary and Creates a Perverse Incentive

The collapse logic collapses P2 notifications into a summary if a user receives "3 or more" within a 5-minute window, but delivers individually if fewer than 3. The number 3 is not justified. More importantly, this creates a boundary condition where 2 notifications are delivered individually but 3 are collapsed — meaning a user who receives exactly 3 likes gets less information (a summary) than a user who receives 2. The document presents this as a cost-benefit tradeoff on notification fatigue but doesn't address that the threshold is both arbitrary and creates this inversion.

### 9. The Staffing Section Is Referenced Throughout but Never Appears

The reading order note explicitly states Section 7 (staffing) is placed last and that "staffing constraints in Section 7 were used to make every sizing and scope decision in Sections 1–6." Section 7 does not appear in the document. This means none of the staffing-dependent claims — that 4 engineers can execute this, that E1 can own the capacity review, that the on-call model is viable — can be evaluated. The document's own framing says staffing drove every decision. That section is absent.

### 10. The DAU/MAU Trigger Calibration Procedure Is Underspecified for Its Stated Purpose

The week-6 calibration sets a revised threshold at mean + 1.5 standard deviations. This is a one-tailed bound with no stated confidence level and no accounting for autocorrelation in daily DAU/MAU ratios (which are not independent draws — they are serially correlated by definition). Using a standard deviation computed from autocorrelated data as if it were i.i.d. produces an interval that is narrower than it should be, meaning the threshold will be set lower than intended and will trigger more frequently than designed. The document doesn't acknowledge this.