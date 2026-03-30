Here are the real problems I found. I've organized them by type.

---

## Structural / Scope Problems

**The document ends mid-sentence.** Section 1.1 cuts off at "Excess recipients are" with no continuation. This is not a minor formatting issue — it means the fanout cap decision, which is one of the six named unresolved decisions (Decision 3), is never actually described. The document references Section 1.1 for the fanout cap option but the section doesn't contain it. Decision 3's fallback ("Option A — accept consistency gap") is named in the Unresolved Decisions table but Option A is never defined anywhere visible in this document.

**Section 7.1 is referenced constantly but never appears.** Named owners, deadlines, the runbook gate, the on-call rotation owner, the SMS budget owner, the legal/compliance owner, the engineering answer to the feed deduplication question — all of these are deferred to Section 7.1. The document cannot function as described without it. Every fallback authority chain terminates in a section that doesn't exist in this draft.

---

## Decision Accountability Problems

**The fallback authority framing has a gap.** The preface carefully explains that product owners own the consequences of not deciding. But Decision 6 (runbook authorship) falls back to the on-call rotation owner making a go/no-go call — meaning the person who bears operational risk is also the person who can waive the protection designed to manage that risk. This is not a theoretical concern; it is a structural incentive problem. The person most likely to say "we'll figure it out" is the one who gets to make that call unilaterally.

**Decision 4's engineering prerequisite is unresolved at the time of writing.** The document states that engineering must answer whether the feed deduplicates at read time before framing Decision 4 as a product decision, and that this answer must be recorded in Section 7.1 before the pre-flight checklist closes. But the document is being circulated now, framing Decision 4 as a product decision, before that engineering answer exists. The sequencing the document prescribes is already violated by the document's own existence.

**The SMS co-sign requirement has no enforcement mechanism.** The document states that if the SMS budget owner role is not filled, Decision 2 falls back to the 200/day cap and the product owner is notified. But the document also says "engineering does not resolve organizational gaps." If the SMS budget owner role genuinely isn't filled, there is no one to notify engineering that the role is unfilled. Engineering would have to independently discover this, which contradicts the stated separation of responsibilities.

---

## Technical / Analytical Problems

**The 90-second crash recovery window is stated but not derived here.** The executive summary says "the derivation of that window is in Section 4.2," but Section 4.2 is not in the provided text. This means the most consequential recovery parameter in the system — the window that determines whether orphaned entries are reclaimed or lost — cannot be evaluated.

**The Redis loss scenario is underspecified relative to its stated severity.** Section 6.2 is referenced multiple times for the conditions under which in-flight entries can be lost rather than duplicated, the estimated probability, and the recovery procedure. Section 6.2 is not in the provided text. The executive summary calls this out as a distinct failure mode from the general crash recovery guarantee. A reader cannot assess whether the "estimated probability given stated replication lag bounds" is acceptable without seeing it.

**The sensitivity table's peak multiplier values are not derived or sourced.** The plan row uses 2.2×, the extreme row uses 3.0×, and different intermediate rows use different values, but there is no explanation of where these multipliers come from. The document is careful to note that 14 active hours is an assumption, but treats the peak multipliers as given. If the multipliers are also assumptions, they compound with the DAU/MAU and notifications-per-user assumptions in ways the document does not acknowledge.

**The correlation structure of the sensitivity table is inconsistent.** The document states that DAU/MAU ratio and notifications-per-user are positively correlated, then constructs two intermediate scenarios that intentionally break this correlation (high-retention/conservative notifications, moderate-retention/aggressive re-engagement). This is described as intentional. But the peak multipliers in those intermediate rows are not explained — why does the high-retention/conservative row use 2.2× (same as plan) and the moderate-retention/aggressive row use 2.5×? If peak multiplier is also correlated with engagement, the intermediate rows may use the wrong multipliers.

**The 200/day fallback cap is not cross-validated against the 20/hour ceiling.** The document presents these as separate controls addressing separate problems, but they interact. 200/day at 20/hour means a user could exhaust their daily cap in 10 hours. Whether this is the intended behavior — and whether the burst allowance (Decision 1) applies against the hourly ceiling, the daily cap, or both — is not specified.

**The power-user SMS cost calculation uses inconsistent share assumptions.** The body text states "at 2% SMS share" for the $15,000/day figure, then says "at 5% SMS share" for the $75,000/day figure. The Unresolved Decisions table says "up to $75,000/day at 5% SMS share." But Section 1.2 is referenced for the full cost table and is not present in this text. There is no basis to evaluate whether 2% or 5% is the operative planning assumption for SMS share.

---

## Operational Problems

**The runbook separation argument is correct but creates a problem the document doesn't acknowledge.** The preface argues that runbooks embedded in design documents become incorrect as the design changes. This is true. But the design document itself contains operational parameters — the 90-second recovery window, the Redis failover behavior, the worker failure behavior in Section 4.3 — that operators will need during incidents. If the runbook references the design document for these values, and the design document changes, the same staleness problem recurs one level up.

**The pre-flight checklist gate for the runbook has no stated timeline consequence.** The document says the on-call rotation owner can accept the runbook gate failure in writing. It does not say what happens next — whether the system launches without a runbook indefinitely, whether there is a post-launch deadline for the runbook, or whether the written acceptance expires. The fallback creates a permanent exception path with no closure condition.

**The staffing arithmetic is referenced but not shown.** Section 1.5 is cited as the source of the derivation from 16 theoretical deployments to 6 actual deployments. Section 1.5 is not in the provided text. The executive summary says "the arithmetic is in Section 1.5" and "the bound does not follow from the decisions." Without seeing the arithmetic, it is not possible to verify either claim.