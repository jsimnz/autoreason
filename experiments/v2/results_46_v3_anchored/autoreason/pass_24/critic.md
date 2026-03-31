## Real Problems with This Proposal

### 1. The Discord Benchmark Is Doing Too Much Work

The 14/DAU figure rests heavily on a "Discord 2023 infrastructure post" that reportedly cited exactly 14 notification events/active user/day. This is suspiciously convenient — it's the same number being justified. No URL, publication name, or author is cited. If this source doesn't exist or doesn't say what's claimed, the entire design basis collapses. The Instagram and Twitter figures are vague ranges that bracket almost any number; the Discord citation is the only one doing precise justification.

### 2. The Beta Cohort Validation Plan Has a Circular Problem

The plan says if beta data isn't available before Month 2, "the 14/DAU basis is used as-is and the risk of undersizing is accepted." But the beta cohort is described as a soft launch of 50,000 users — soft launch typically *is* Month 1 or Month 2. The document never establishes that beta cohort data will exist *before* Month 2 infrastructure decisions lock. The validation plan may be structurally too late to change anything.

### 3. The 16/DAU Revision Trigger Is Arbitrary

The design basis is 14/DAU. The trigger for revision is 16/DAU — a 14% increase. No rationale is given for why 16/DAU specifically is the threshold rather than 15 or 17. More importantly, the document acknowledges that 16/DAU puts the system "approaching Default A" — meaning Default A activates during *normal operation*, not spikes. The trigger should arguably be lower, but there's no reasoning shown for where it sits.

### 4. The Sign-Off Table Has a Row Count Mismatch

The introductory text says "Seven Items Requiring Sign-Off." The sign-off table contains eight rows. This is either a counting error or a row was added after the introduction was written and never reconciled. In a document being presented for stakeholder sign-off, this is a credibility problem.

### 5. The Document Is Cut Off Mid-Sentence

Section 1.1 ends: "An alert is warranted only if Default B persists beyond 30 minutes or activates more than" — the sentence stops. This is not a minor editorial issue. The alert threshold for Default B activation frequency is a defined operational parameter. Its absence means the monitoring specification is incomplete as submitted.

### 6. Default A/B Counter Behavior Specifies Activation But Not Deactivation Symmetry

The changelog says counter behavior is "fully specified" including that activation requires N consecutive above-threshold samples. The document states the counter decrements on each sample below threshold but does not reset to zero. However, the deactivation condition — how many consecutive below-threshold samples are required to exit Default A back to normal — is not stated in the visible text. The asymmetry between activation (N consecutive above) and deactivation (decrements without a stated exit count) is unresolved.

### 7. The Cost Estimate Methodology Is Inconsistent With Its Own Framing

The document says the additional cost is "approximately $1,260/month over the 11/DAU-sized alternative." But the 11/DAU alternative is described as producing Default B activation during "normal high-end operation" — meaning the 11/DAU sizing is not a real alternative because it would cause routine operational degradation. Presenting the cost delta against an option that was already rejected on correctness grounds understates the true cost of the chosen design relative to a genuinely comparable baseline.

### 8. The Geographic Distribution Placeholder Has No Fallback for the Period Before Measurement Exists

The document says geographic distribution is measured "from day one of soft launch" and action triggers are defined for APAC-dominant conditions. But infrastructure must be *configured before* soft launch. The document never specifies what geographic assumption is used for pre-launch infrastructure provisioning — the placeholder is acknowledged but the configuration decision it affects is left unresolved.

### 9. The "Invisible Data Loss" Bound Appears in the Changelog as Resolved But the Bounded Estimate Is Not Visible in the Document Body

The changelog says "non-compliant producer volume estimated; data loss duration bounded; severity assessment provided" with references to §1.1 and the Sign-Off Table. Neither the visible §1.1 content nor the sign-off table contains these estimates. The resolution claimed in the changelog is not present in the document as shown.

### 10. The Spike Model Produces Rates That Exceed the Design Basis by 5× With No Infrastructure Response Specified Beyond "Tier 1 Only"

Type 4 spikes at 20,415/sec are described as a "designed failure mode" with Tier 1 only and Tier 2 queued. But the document never specifies the queue depth bound for Tier 2 during a Type 4 event, nor what happens when that bound is hit — and the sign-off table explicitly lists "queue depth bounds and backpressure behavior" as an *unresolved item requiring sign-off by End of Month 1*. The spike model is presented as if the behavior is designed, but the design of that behavior is pending a decision that hasn't been made.