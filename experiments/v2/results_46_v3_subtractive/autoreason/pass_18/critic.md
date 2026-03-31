## Real Problems with This Proposal

### 1. The Cost Estimate Contains an Unfilled Placeholder That Directly Affects the Acceptance Rationale

Section 1.1.1 states the over-provisioning trade is accepted because a capacity emergency costs "a minimum of 2 engineer-weeks ($X in loaded labor cost, to be confirmed with finance)." The acceptance rationale is explicitly built on this comparison, and the $X is never filled in. This is the same structural problem as the placeholder references criticized in Revision 3 — the document acknowledges it needs confirmation but presents the conclusion as settled anyway. The trade may be correct, but the justification is incomplete in the same way a prior revision was criticized for being incomplete.

---

### 2. The Email Cost Estimate Is Almost Certainly Wrong by an Order of Magnitude

Section 1.1.1 estimates 75M emails/month at pessimistic provisioning and derives a monthly SES cost of ~$7,500. But the traffic model shows approximately 8M routed events/day at pessimistic DAU. Even if only a fraction route to email, 75M emails/month implies roughly 2.5M emails/day — about 31% of all routed events going to email. No email opt-in rate assumption is stated in Section 1.1.1 to justify this figure. Section 1.2.3 addresses email opt-in sensitivity, but the cost section does not reference it or show the derivation. The 75M figure appears to be assumed rather than derived from the traffic model, which means the dominant cost line item (67% of total) has no traceable basis within the document.

---

### 3. The Fanout Multiplier of 1.05 Is Implausibly Low and Its Derivation Is Not Present in Section 1.5.1

The table states the fanout multiplier for non-high-follower actions is 1.05, meaning the average non-high-follower action generates 1.05 recipient notification events. This implies that across all posts, comments, likes, and follows from non-high-follower users, the average action reaches just 1.05 people. For a social app, this would mean the overwhelming majority of actions reach zero or one other user. The document says the derivation is in Section 1.5.1, but Section 1.5.1 is not present in the provided text. The multiplier is load-bearing for the entire traffic model, and its absence means the routed event volume figures throughout the document cannot be verified.

---

### 4. The Trigger Mechanism Has No Enforcement Path When E2 Is Unavailable

The scaling trigger assigns monitoring ownership to E2, but there is no backup owner, no automated alerting that fires independent of E2, and no stated consequence if E2 misses the signal. On a 4-engineer team over 6 months, personnel unavailability is a real probability. The degradation scenario in Section 1.1.2 depends entirely on the trigger being caught promptly — a missed week converts the 8–11 day buffer into a 1–4 day buffer. The document identifies the zero-buffer problem as real but does not address the single-point-of-ownership problem in the monitoring step that initiates the mitigation.

---

### 5. The 2× Spike Disclosure Is Internally Inconsistent

Section 1.1.2 states that during a 2× spike, "some social notifications are delayed by up to 3–4 days for events that occurred during the spike." It then states this is disclosed via a status page update. But the proposal also states the system is a social app with 10M MAU. A status page disclosure of 3–4 day notification delays for social interactions is a product-level incident, not an infrastructure footnote. The document frames this as an acceptable operating outcome while simultaneously offering the product lead the option to reject it — but the product lead decision is described as happening "before launch," meaning this document is presenting a potentially unacceptable user experience as the default accepted state pending a conversation that has not yet occurred.

---

### 6. The SQS Cost Calculation Applies a Fixed Overhead Multiplier Without Basis

Section 1.1.1 estimates SQS cost by assuming "~3 API calls/event" as a fan-in/fan-out overhead multiplier. SQS billing includes sends, receives, and deletes. Whether 3 is the right multiplier depends entirely on the queue topology — number of queues, visibility timeout behavior, dead-letter queue interactions, and whether long polling is used. The queue topology is referenced but not present in the provided text. The 3× multiplier is asserted without derivation, applied to the dominant variable-cost component of the queue infrastructure line.

---

### 7. The Batching Reduction Factor Range Is Too Wide to Be Actionable

Section 1.1.1 states that email batching reduces SES volume by a "1.01–1.4× reduction factor," which reduces SES cost by "$75–$2,000/month." A range spanning nearly two orders of magnitude in dollar impact is not a cost estimate — it is an acknowledgment that the batching behavior is not modeled. The document explicitly notes this "does not change the infrastructure provisioning decision," which is true, but it also means the stated cost figures could be off by $1,925/month on the dominant cost line, and the document treats this as acceptable without quantifying the conditions under which the high or low end applies.

---

### 8. The Compliance Gate Structure Creates a Circular Dependency That Is Not Acknowledged

Section 1.2.1 ties the legal review gate to "four weeks before the preference management UI enters QA." The preference management UI presumably implements the opt-in/opt-out behavior that is the subject of the legal review. If legal review requires changes to the opt-in design, those changes affect the UI that was used to set the gate date. The document does not acknowledge this dependency, meaning a legal change request arriving during the four-week window could invalidate QA readiness for the very milestone the gate was anchored to.

---

### 9. The Transactional SMS Volume Derivation References Section 1.4, Which Is Not Present

The executive summary states that Section 1.4 now contains a quantified transactional SMS estimate with derivation and that the channel volume table is updated. The cost section uses 300K transactional SMS messages/month. Section 1.4 is not present in the provided text. The 300K figure therefore has no visible derivation, and the Twilio cost estimate ($2,370/month, the second-largest variable cost) cannot be verified.

---

### 10. The Document Describes Itself as Revision 4 Resolving Ten Criticisms, but Several Referenced Sections Are Absent

Sections 1.2.1, 1.2.3, 1.3, 1.3.3, 1.4, 1.5.1, and 1.6.1 are all referenced in the executive summary as containing resolutions to specific criticisms, and several are referenced within the sections that are present. None of these sections appear in the provided text. The executive summary asserts "where a prior resolution was asserted but the supporting content was absent or incomplete, the content is now present" — but this claim cannot be evaluated because the content is not present in this revision either. This is structurally identical to the problem that generated Criticism 5 in the prior round.