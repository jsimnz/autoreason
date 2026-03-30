## Real Problems with This Proposal

### 1. The Gate System's "Automatic" Enforcement Is Illusory

The document claims the enforcement mechanism is the project tracker, not a person's authority. But project trackers do not move work items to hold states — people do. Someone has to configure the tracker rules, someone has to verify the gate wasn't quietly resolved through a back-channel, and someone has to resist when a PM says "just mark it unblocked, we have verbal confirmation." The document has transferred the authority problem to a tooling problem without acknowledging that tooling requires human configuration and maintenance. The robustness claim is false.

### 2. The Owner Role Assignment Task Has No Gate

Section 0.3 states that if owner names aren't recorded by end of Week 2 of Month 1, gates 1–4 are treated as unresolved. But this meta-task — recording the names — has no gate of its own, no owner role assigned to it, and no scope reduction consequence. It's enforced by the same authority-based mechanism the document just argued is insufficient. This is the most critical dependency in the system and it's handled more loosely than anything else.

### 3. The Bayes Calculation Launders an Unvalidated Assumption

The entire activity-correlation correction rests on R = 3, described as "conservative" with no empirical basis. The document then uses this derived figure to claim empirical corroboration from industry reports that show 5–8% in-session delivery rates. But 6.6% falling within 5–8% doesn't validate R = 3 — it's consistent with a wide range of R values. The derivation is circular: a free parameter is chosen to produce a result, then the result is said to be corroborated by data that the free parameter was implicitly chosen to match.

### 4. The Provisioned Floor Arithmetic Is Presented Inconsistently

The executive summary states the provisioned floor provides "66% headroom" at peak. Section 1.2 states the working assumption provides "40% headroom." These are different claims about the same number. The 66% figure compares peak demand (3,126/sec) to provisioned floor (5,200/sec). The 40% figure computes headroom differently. A reader cannot tell which framing is correct or why both appear without reconciliation.

### 5. The Flag Threshold Derivation Is Circular

The ✓/⚠/✗ thresholds in Section 1.2 are defined relative to the provisioned floor, which was itself sized to make the working assumption ✓. The sensitivity table therefore cannot reveal whether the working assumption is actually safe — it can only show whether scenarios are better or worse than the working assumption. Scenarios that would require re-sizing are marked ✗, but the document provides no analysis of how long re-sizing takes or what the consequence is of discovering a ✗ scenario post-launch.

### 6. GATE-2's Scope Reduction Default Contradicts Its Purpose

If GATE-2 is unresolved, the fallback is to use 20/day as a conservative upper bound. But 20/day is within the range the document already identifies as requiring review (⚠ at 30% DAU/MAU). The scope reduction for an unresolved gate produces a planning state that itself triggers a re-sizing review. This is not a safe default — it's a deferred version of the same problem.

### 7. The Sequential Gate Dependency Creates Compounding Slip With No Recovery Mechanism

GATE-3 shifts if GATE-2 slips. The document acknowledges this. But GATE-3 feeds in-app worker sizing, which feeds the engineering budget in Section 5. If GATE-2 slips by two weeks, GATE-3 slips by two weeks, and the engineering work dependent on GATE-3 slips by at least two weeks. In a six-month project with four engineers, two weeks is roughly 8% of total project time. The document describes the slip mechanism but contains no analysis of whether the six-month window survives even a single two-week slip on this chain.

### 8. The Naive Model Is Dismissed Without Testing Whether It Matters

The document argues at length that the naive session-fraction model produces ~2.5% versus the corrected 6.5%. But it never establishes that this difference has material consequences for worker sizing. If in-app workers are cheap to scale or if the in-app tier is not a bottleneck, the entire derivation is engineering effort spent on a number that doesn't constrain anything. The document doesn't show that in-app worker sizing is a binding constraint justifying the analysis.

### 9. Section 1.3b Is Absent

The document cuts off mid-header. Email volume, SMS volume, and spend caps are referenced throughout the executive summary and gate register (GATE-1, GATE-4, GATE-5 all depend on SMS spend cap calculations; GATE-1 depends on email worker sizing). These sections don't exist in the document. The gate system references deliverables that have no content.

### 10. "Named Individual" Is Not Actually Named

Every gate requires sign-off from a "named product owner," "named analytics owner," or "named security lead." But no names appear anywhere in the document. The document describes a structure that requires specific people while deferring the identification of those people to a separate task. Until names are assigned, the gate system has no subjects — it's a set of rules with no actors.