Here are the real problems with this proposal.

---

**The compliance claim is wrong on its face.**

Section 2.4 is referenced repeatedly as containing "two compliant architectures," but Section 2.4 does not exist in this document. The executive summary tells stakeholders that one path "is not available for selection regardless of stakeholder preference" and that "Legal must confirm which compliant architecture is acceptable" — but there is nothing for Legal to review. The document asserts TCPA/CAN-SPAM/GDPR compliance postures without presenting the actual architectures. This is not a drafting gap; it means the compliance framing in the executive summary is unverifiable.

---

**The sign-off structure is internally contradictory.**

The executive summary lists five items requiring sign-off, then immediately removes one from the sign-off list ("This is not a sign-off item — it is a constraint"). A fifth item (Default C) is presented as an option but then explicitly excluded from selection. Presenting non-selectable options in a sign-off list that stakeholders are expected to act on creates confusion about what decisions are actually being requested. Two of the five items are not real decisions.

---

**The SMS budget numbers are not derived anywhere.**

The executive summary states a planning basis of ~$17K/month and a worst-case of $67.5K/month. Neither figure appears in Section 1.1 or anywhere else in the visible document. There is no SMS volume derivation, no per-message rate, no send policy assumption. The sensitivity table in Section 1.1 lists "75K SMS per day" as a planning basis with no explanation of where that number comes from. For a line item flagged as requiring executive sign-off by Week 2, the absence of any derivation makes the sign-off request meaningless.

---

**The DAU/MAU ratio assumptions are inconsistent across the document.**

The planning basis is stated as 25% DAU/MAU (2.5M DAU). Worker sizing uses 35% DAU/MAU as the "high-case planning input." The combined peak throughput table then uses 27.5M push/in-app per day (the 25% basis) rather than the 38.5M figure used for worker sizing. The document simultaneously claims to be conservative in worker sizing and then uses the lower volume figure for the throughput table that informs queue and infrastructure design. These cannot both be right.

---

**The email concentration assumption is applied inconsistently.**

The document states "all channels use a consistent concentration assumption within a scenario" and then uses 90% concentration for email in the combined peak table. But email — particularly re-engagement and digest email — is explicitly scheduled and batched by the sender, not user-driven. Applying the same peak concentration model to scheduled batch email as to organic push notifications is not a neutral planning choice; it overstates email peak load significantly. The document does not acknowledge this.

---

**The "self-hosted fallback" scope is presented as resolved when it is not.**

The document states with confidence that if the SendGrid contract fails, "the specific workstream that slips is the Month 2 in-app notification delivery milestone." This precision implies the Month 1–2 workload is fully scoped and that the self-hosted email path has been estimated against it. Neither is demonstrated. The 6–8 engineer-week estimate for the self-hosted path is asserted without a task breakdown, and the claim that it displaces exactly one milestone — not two, not a different one — is not supported by any schedule analysis visible in this document.

---

**The viral spike model proves its own architecture is insufficient but does not follow through.**

The document correctly shows that the 8%/5min spike scenario produces 57-minute drain times even with isolated high-priority queues. It then states that autoscaling "is the mechanism" for handling this, contingent on Kubernetes HPA or equivalent — and the sentence cuts off. There is no statement of whether HPA is in scope, who owns it, what the autoscaling trigger thresholds are, or what the scaling latency is. HPA does not provision and warm workers instantly; during a spike that peaks in 5 minutes, autoscaling response time is itself a critical variable. The document raises the problem and provides no resolution.

---

**The broadcast notification hard cap enforcement is mentioned in two sections that do not exist.**

The executive summary states the 100K recipient cap is described in "Section 1.1 and Section 6." Section 1.1 as written contains no cap definition, enforcement mechanism, or exception process. Section 6 does not appear in this document. The cap is presented as a finalized policy requiring a named exception gate, but the policy itself is not written anywhere reviewable.

---

**The "known unmodeled factor" for graph density is flagged but its implications are not followed.**

The document correctly notes that notification volume grows with social graph density independently of DAU growth, then states that a calibration checkpoint will trigger reassessment if observed rates exceed 13/DAU/day before Month 4. But the reassessment consequence is not defined. If the observed rate hits 14 or 16/DAU/day in Month 3, what changes? Worker sizing? Queue depth? Infrastructure contracts? The checkpoint is defined; the response is not.

---

**The accountability structure for the re-engagement policy decision is unworkable.**

E1 must obtain a written re-engagement policy decision from product by end of Week 2 so the SendGrid contract can be sized correctly. But E1 also owns the SendGrid contract and must begin procurement in Week 1. The document does not explain how a contract negotiation begins in Week 1 when the primary sizing input — the re-engagement send rate — is not resolved until Week 2. The contract tier is explicitly stated to depend on the policy decision. Starting procurement before that decision is made means negotiating to an unknown target.