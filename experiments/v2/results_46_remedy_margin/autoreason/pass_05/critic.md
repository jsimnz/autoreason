## Real Problems with This Proposal

### 1. The 50K Cohort Validation Is Structurally Weak

The document claims a 50K-user beta cohort provides reliable behavioral signal in week 2. But the cohort is self-selected (early adopters), not representative of the eventual 3M DAU population. Early adopters systematically over-engage. The "heavy users, casual users, dormant users" distribution claim is asserted, not demonstrated. A week-2 measurement from this cohort could confidently validate the wrong number, and the document treats cohort bias as solved rather than acknowledged.

### 2. The Decision Gate Has No Teeth

The recalibration table assigns "E1" as decision owner with a 72-hour window for >5× scenarios. But the >5× contingency section immediately below says the honest response involves communicating to stakeholders and deciding whether to hire engineers. E1 cannot make hiring decisions. The decision owner for the scenario that actually breaks the project is not named, and the 72-hour window is implausible for a decision requiring executive involvement.

### 3. Section 2.3 Is Incomplete and the Document Knows It

The document cuts off mid-sentence: "The previous version of this document derived P0 worker counts using the 350 notifications/sec per worker figure from APNs/FCM HTTP/2 benchmarks." The actual P0 worker count derivation is never provided. The P1 worker count of 30 appears in the architecture diagram without derivation. The document explicitly criticizes the previous version's throughput model but never replaces it with a correct one. Worker counts are load-bearing architectural decisions presented without justification.

### 4. The Scenario B Math Undermines the Architecture Without Resolution

Section 1.3 calculates that under 10× sustained load for 10 minutes, 7.35M items accumulate in the P1 queue. The document calls this "not acceptable" and says it "drives the worker count decision in Section 2.3." Section 2.3 is incomplete. The problem is identified, declared critical, and then never resolved in the document as written. There is no stated P1 worker count that handles Scenario B.

### 5. E4 Scope Correction Creates a New Problem It Ignores

The document corrects the previous E4 allocation arithmetic and concludes E4 has "no slack." It then states that if query performance becomes a sustained time sink, "E1 and E3 are responsible for fixing the underlying schema or query pattern." E1 owns queue infrastructure and architecture recalibration. E3 owns preference management and user-facing API. Neither has database performance as a primary responsibility, and neither has slack time identified to absorb this. The document transfers an overflow problem from E4 to two engineers without examining whether they can absorb it.

### 6. The Block Suppression Structural Guarantee Is Overstated

The document claims type-level enforcement prevents accidental caching of block suppression. But it immediately concedes "this does not prevent a future engineer from writing a new `CachedBlockSuppression` implementation." The CI integration test is described as verifying "block suppression bypasses cache under load" — but if a cached implementation is wired in, it may pass functional tests while violating the safety property under specific timing conditions. The document presents this as a solved enforcement problem when it is actually a convention enforced by code review vigilance, which is what the previous version had.

### 7. The SMS Cost Range Is Presented Without a Budget Decision

Section 1.4 presents a cost range of $240K–$1.38M/month and says the enforcement mechanism is in Section 3.4. The document does not contain Section 3.4 as written here. More fundamentally, a 5.75× cost range is not a planning input — it is an unresolved business decision about geographic targeting. The document treats this as a technical problem with a technical solution (budget gates) when the actual question is whether the product can afford SMS at international rates at all.

### 8. The Viral Spike Model Still Has an Unjustified Number

Section 1.3 replaces the 90-second spike assumption with two scenarios, then sizes P1 workers for "5× sustained." The choice of 5× as the Scenario B design target is not justified. The document acknowledges sustained events can run at "5–10× above peak for 10–30 minutes" and then silently selects the lower bound of that range as the design point without explaining why 5× is the right threshold rather than 10×.

### 9. The Incremental Delivery Claim Has No Schedule

The executive summary states "working system by month 2, iterated through month 5, hardened in month 6." No milestone breakdown appears anywhere in the document. Given that E4's reconciliation job alone takes 3–4 weeks in month 2, and E2 is building four channel integrations, "working system by month 2" is either defined very narrowly or is optimistic. The document never defines what "working" means at month 2.

### 10. The In-App Store Ordering Caveat Is Deferred Without Consequence

The architecture diagram notes that the in-app store bypasses the queue with "ordering implications described in Section 2.6." Section 2.6 does not appear in this document. A direct PostgreSQL write path that bypasses priority queues has real implications for notification ordering consistency, especially during high load when queued notifications are delayed. This is flagged and not addressed.