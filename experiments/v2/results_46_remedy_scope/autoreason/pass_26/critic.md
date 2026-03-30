## Real Problems

### Structural and Process Problems

**The self-completeness guarantee is unfalsifiable as written.** The document claims "every section referenced in this document exists in this document" and that the table of contents is the completeness check. But the table of contents only lists section titles — it cannot verify that the *content* of those sections is actually present and complete. Section 1.3 is visibly truncated mid-sentence ("Engineering lead and—"), meaning the document has already violated its own guarantee while asserting it. A reader following the stated verification method would not catch this.

**The pre-flight check mechanism is described but not defined.** The document repeatedly states the deployment pipeline will "return a non-zero exit code" and "not clear the pre-flight check" if placeholders remain. But nowhere is the pre-flight check itself specified — what system runs it, where the check logic lives, what format Section 7.1 must be in for the check to parse it. This is a circular dependency: Section 7.1 is supposed to contain named owners, but Section 7.1 doesn't exist in the provided document.

**Section 7.1 and Section 7.2 are referenced throughout but absent from the document.** This is not a minor omission. The document's own escalation chains, authorization thresholds, scaling sign-off procedures, named owners, and deployment gates all terminate in these sections. The document explicitly states that anyone who finds a missing section should "file it against the engineering lead and do not proceed with the referenced action." By the document's own rules, the entire document is blocked.

**Four product decisions are gated on Section 7.1 for owner and deadline, but Section 7.1 doesn't exist.** The mechanism designed to force resolution of unresolved decisions is itself unresolved.

---

### Escalation Logic Problems

**The month-1 escalation chain has a logical gap it claims to have closed.** The document argues that routing through the engineering lead fails if the engineering lead caused the problem, and routes to a named backup instead. But the backup's authority is described as "time-triggered, not permission-triggered" — yet the backup is *also* named in Section 7.1, which doesn't exist. The chain terminates in an undefined reference.

**"Escalate to whoever is above the engineering lead in the org chart" is not actionable.** The document explicitly acknowledges it cannot name this person because org charts change. But this is the terminal escalation path for the scenario where all three named people are simultaneously unavailable — the highest-stakes scenario. Acknowledging the gap without addressing it is not the same as addressing it.

**The day 33/day 34 trigger logic conflates cause with timing.** The document says if neither the on-call owner nor the engineering lead has initiated the review by day 33, the backup acts. But the backup is supposed to act "without determining whose failure caused the gap." However, the backup still needs to *know* that neither person has acted — which requires the backup to be monitoring for this condition continuously. There's no mechanism described for how the backup would know to act on day 33.

---

### Technical and Analytical Problems

**The 45-minute worst-case fanout bound is stated but not derived.** The document says the token bucket "bounds worst-case fanout completion time for a 100,000-recipient event at approximately 45 minutes under congestion." The token bucket parameters are not shown in this section. The queue saturation assumptions are not shown. The arithmetic is not shown. This is a product-visible SLA-adjacent claim with no visible derivation.

**The per-user rate limit analysis contradicts itself.** The document states the 20/hour ceiling "provides no meaningful protection against users generating 50–100/day" — and that is correct, because 50–100/day is well below 480/day (20/hour × 24). But then it says power-user stress is "addressed through per-user queue partitioning and Redis key sharding." Those mechanisms address throughput distribution, not the spam-prevention gap the document just identified. The actual problem — that the rate limit doesn't limit power users in the relevant range — is named and then not resolved.

**The peak rate scaling claim ("superlinearly") is asserted without verification.** The document says the extreme row's peak rate is 4.76× the plan row's while daily volume is only 3.6× higher, and calls this "internally consistent with the methodology, not an error." But the multipliers (2.5×, 3×, 3.5×, 4×) are stated assumptions, not measured values. The superlinear scaling is a consequence of chosen multipliers, not empirical data. Calling it internally consistent is true but does not validate the multipliers themselves.

**The 90-second crash recovery bound is described as "explicit and derived in Section 4.2" but Section 4.2 is not present in the provided document.** This bound matters operationally — it determines worst-case duplicate delivery windows — and its derivation is deferred to a section the reader cannot verify.

**The FCM/APNs rate limit caveat is applied inconsistently.** The document correctly marks P1 delay figures as unverified pending the Section 1.4 procedure. But the claim that "the binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput" is also contingent on the same unverified FCM rate check — and is not marked as unverified. One downstream claim is flagged; the upstream architectural claim is not.

**The deduplication memory bound is described as "bounded by 60 seconds of per-user throughput" but the interaction with the cross-channel delivered-ID set is deferred to Section 2.2**, which is absent. For power users at 50+ notifications/day, the delivered-ID set is not bounded by 60 seconds — it's bounded by whatever retention window is used for cross-channel deduplication. That window is not stated anywhere in the visible document.

---

### Internal Consistency Problems

**The document states "Four items are flagged as unresolved product decisions" but only two are visible in the provided text** (burst allowance and fanout cap). The other two are not present. The document's own completeness guarantee is violated.

**Option D under fanout cap says it "requires engineering to produce a revised capacity estimate before this option can be accepted" and that "selecting this option without scheduling the estimate work blocks the deployment checklist gate."** But the deployment checklist gate is the pre-flight check in Section 7.1, which doesn't exist. The blocking mechanism for a bad product decision is itself blocked.

**The traffic response matrix referenced throughout Section 1.3 is not present** — the section ends mid-sentence. The document's own self-completeness policy requires this to be filed as a defect, which means the traffic response procedure for the 55M–80M/day scenario is unavailable. This is one of the six incident-condition entry points listed in "How to Use This Document."