## Real Problems with This Proposal

### 1. The Document Cuts Off Mid-Sentence

The APNs error handling section ends abruptly: "The push" — nothing follows. This means the APNs error handling spec is incomplete. FCM error handling, the rest of §1.4, §1.5, and everything beyond is missing entirely. The document claims to be "a complete technical design" in the Preface. That claim is false. Any engineer implementing from this document hits a hard stop at the most operationally detailed section.

### 2. The 14-Day Validation Window Solves a Problem That May Not Exist at Day 14

The document argues that by day 14, "enough traffic has been observed to replace the peak multiplier and the per-user notification rate with measured values." But the document also states the DAU/MAU ratio "is still stabilizing" at day 14. If the user base is still growing or churning rapidly in the first two weeks post-launch — which is the norm for a social app — then the measured peak and per-user rates at day 14 may not be representative of steady-state behavior either. The argument that two of three assumptions are resolved at day 14 while the third is acknowledged as unstable does not actually reduce compounding risk as much as claimed.

### 3. Tier 1 Legal Caveat Is Unresolved but the Design Proceeds Anyway

The document notes that delivering Tier 1 notifications to all channels regardless of user opt-in "may conflict with applicable regulations in specific jurisdictions" and calls this "an open item requiring legal sign-off before launch." The design is then fully specified as if this sign-off will be obtained. If legal review concludes that opt-in is required for SMS or email even for security events in certain jurisdictions, the entire Tier 1 delivery architecture changes. The document treats a potentially architecture-invalidating dependency as a footnote.

### 4. "Immutable Tier Assignment" Conflicts with the Tier 3 Preference Override

The document states: "The tier assignment is immutable — it cannot be changed by user preference or batching logic, only by the event type definition." Then, three paragraphs later: "Users who prefer immediate delivery of likes and follows can upgrade these to Tier 2 cadence via preference settings (§1.5)." These two statements directly contradict each other. The clarification that "the preference controls delivery timing, not the worker assignment" is an attempt to resolve this, but it creates a new problem: if a Tier 3 notification is delivered on Tier 2 cadence, it will behave like a Tier 2 notification to the user while being processed by Tier 3 infrastructure. The document never specifies how quiet-hour suppression, in-app store write timing, and retry behavior apply to this hybrid case.

### 5. Ownership Transfer Process Has a Circular Failure Mode

If the project lead leaves or is unavailable, the document says "the team lead assumes temporary ownership." But the project lead is also responsible for enforcing that the 14-day review happens, and the team lead is listed as the enforcement backstop for the review. If both the named owner and the project lead are simultaneously unavailable — not unusual in a four-person team where one person might be on leave — the escalation chain loops back to a role that is also absent. A four-person team has no slack for this kind of chain.

### 6. The 2× Provisioning Headroom Is Described as Both Sufficient and Insufficient in Adjacent Paragraphs

§1.1.1 states the 2× headroom "does not fully cover the scenario where all three are simultaneously wrong in the same direction" and that this is addressed by the 14-day validation window. §1.1.3 then states the system is "intentionally over-provisioned at launch" with baseline instances set to handle 2× the projected peak, framed as adequate insurance. These two characterizations are not reconciled. The 2× headroom is simultaneously the known-insufficient fallback and the confident provisioning stance.

### 7. The Spike Buffering Calculation Assumes a Known Spike Duration

The queue backlog calculation in §1.1.3 assumes a 2.5-minute auto-scaling gap and a 3× spike, producing ~58MB of backlog described as "well within capacity." But the document has already acknowledged that the 3× peak multiplier is "explicitly unsupported by product-specific data." The spike buffering adequacy argument is built on the same unsupported multiplier it is supposed to protect against. A 6× spike — which the document acknowledges is possible if all three assumptions are wrong simultaneously — produces a different backlog figure that is never calculated.

### 8. The In-App Store Write Guarantee Is Forward-Referenced but Never Defined in the Visible Document

§1.4.2 is referenced twice — once for Tier 2 ("see §1.4.2 for the implementation guarantee") and once implicitly for Tier 1 — but §1.4.2 does not appear in the document as presented. This is either a missing section or a reference to content that was never written. Either way, the "implementation guarantee" that every Tier 2 notification is written to the in-app store before push is attempted has no specification.

### 9. Notification Rate Table Uses Percentages of DAU That Are Internally Inconsistent

The direct message row states "20% of DAU send at least one" and maps this to 500,000 daily notifications. But a DM creates a notification for the *recipient*, not the sender. If 20% of 2.5M DAU send at least one DM, the number of DM notifications depends on how many recipients those senders reach, which is not specified. A user sending one DM to ten people generates ten notifications. The table conflates sender activity with notification volume without acknowledging this.

### 10. The Dead-Letter Queue Alert Has No Specified Response SLA

§1.3 states that after retry exhaustion on all Tier 1 channels, "an alert fires to the on-call engineer." There is no specified response time, no defined action the on-call engineer is expected to take, and no defined outcome. For a Tier 1 security event — a password reset that failed delivery — the alert existing is not the same as the user being helped. The document specifies the alert mechanism but not what happens after it fires.