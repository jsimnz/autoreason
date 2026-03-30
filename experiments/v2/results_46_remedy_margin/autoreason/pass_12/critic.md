## Real Problems with This Proposal

### 1. The Document Is Incomplete

Section 1.2b cuts off mid-sentence at "Decision criteria:" with no content following. This is not a minor formatting issue — it describes the month-3 revisit decision criteria, which is referenced as a critical gate throughout the document. The proposal is being submitted or reviewed in an incomplete state.

---

### 2. The On-Call Math Doesn't Work

A 4-engineer team rotating weekly with 2-person on-call coverage means each engineer is on-call primary or secondary roughly half of all weeks. The proposal allocates 20% of each engineer's time to operational work. On-call weeks, especially for primary, routinely consume far more than 20% even at low incident rates — and this is a new system in beta, where incident rates are highest. The 20% figure and the on-call structure are in direct tension with each other, and the proposal doesn't acknowledge it.

---

### 3. Section 7 Is Placed Before Sections 1–6 but References Them

The document opens by explaining that Section 7 appears first because everything else is grounded against it. But Section 7.3 references "Scenario A events" and "Section 2" and "Section 4" — content the reader hasn't seen yet. The justification for the ordering contradicts the actual dependency structure of the content.

---

### 4. The Sparsity Correction Is Invoked Without Being Quantifiable

The proposal repeatedly states that sparse-graph readings must be corrected upward for steady-state density, and that this makes above-ceiling readings more alarming. But the magnitude of the suppression correction is explicitly described as "unknown." The decision gate table applies specific multiples (1.5×, 3×) as triggers, but those multiples are chosen against a baseline that could itself be off by an unspecified suppression factor. The thresholds are presented with precision that the underlying uncertainty doesn't support.

---

### 5. The False Positive Protocol Has a Structural Bias Problem

The >3× false positive protocol states the "default presumption favors confirming the finding" and that a valid artifact requires a "specific mechanism, not a general claim of noise." But the review is conducted by E1 and the engineering lead — the same people who designed the sizing assumptions being challenged. There is no independent check. The presumption toward confirmation sounds rigorous but doesn't address the conflict of interest in who is doing the confirming.

---

### 6. E2 Owns a Critical Undesigned Component

The LIFO mitigation — switching to round-robin polling across sub-queues partitioned by notification ID modulo N — is described as E2's implementation responsibility, but N is never defined, the sub-queue partitioning scheme isn't specified, and no design exists. This is assigned as an implementation task for a component that hasn't been designed. At queue depths above 500K items (a page-worthy condition per 7.3), the system would be operating without this mitigation until E2 builds it.

---

### 7. The 48-Hour Architectural Review Timeline Is Unrealistic

If the >3× finding is confirmed, the Section 1.2a escalation protocol activates. But Section 1.2a only analyzes queue equilibrium under the >3× case — it does not describe what the escalation protocol actually is. A 48-hour window for a confirmed finding that invalidates the core sizing assumption, with no defined response, is not a protocol.

---

### 8. The Phase 1 "60% Capacity" Claim Is Inconsistent

The proposal states Phase 1 provisions at 60% capacity anchored to the 15/35/50 worst-case scenario, and that this means the system "cannot absorb a full Scenario B spike during weeks 3–8." But Section 1.2a's equilibrium analysis is conducted at post-suppression rates that assume a dense graph. During a sparse beta, Scenario B behavior is different. The equilibrium analysis doesn't apply to the period when the 60% capacity constraint is actually in effect.

---

### 9. The DAU/MAU Trigger Calibration Depends on Beta Data That May Not Exist

The calibration procedure requires 14+ days of beta data by week 3. The beta starts in week 3 (per Phase 1 provisioning). This means the calibration window and the beta start are simultaneous — there cannot be 14 days of beta data by week 3 of beta. The fallback to 33% with a five-consecutive-day rule is applied "if fewer than 14 days of beta data by week 3," which is the guaranteed condition, not a fallback.

---

### 10. Secondary Coverage Assignments Create Single Points of Failure

E3 covers E2 (queue infrastructure), and E2 covers E3 (channel integrations). These are mutual coverage assignments between two engineers with no overlap with the Lead or E1. If both E2 and E3 are unavailable simultaneously — vacation, illness, simultaneous incidents — queue infrastructure and all channel integrations have no coverage. The proposal acknowledges no dedicated SRE or DBA, but the coverage matrix doesn't actually provide redundancy for the most operationally critical components.

---

### 11. The Infrastructure Cost Estimate Is Underspecified for Its Purpose

The proposal states the honest treatment of circularity costs "$5–10K/month additional at the $8–15K/month managed services range." This is a 2× range on the baseline and a 2× range on the delta. These ranges overlap in ways that make budgetary planning meaningless — the additional cost could be 33% of the low end or 67% of the high end of total spend. The precision implied by calling this a "direct cost" isn't supported by the numbers given.