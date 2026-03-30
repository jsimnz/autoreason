## Real Problems with This Proposal

### 1. The Document Cuts Off Mid-Sentence

Section 1.4 ends abruptly: "At 1,750/sec in—". Sections 2, 3, and beyond are missing entirely. The escalation ladder referenced repeatedly (Section 3), the full worker sizing table, the Redis memory derivation, the idempotency state machine, and the delivery state machine are all absent. This is an incomplete document being reviewed as if it were complete.

### 2. The "Strongest Elements" Synthesis Claim Is Unverifiable

The preamble asserts this document takes the strongest elements from Version X and Version Y, but neither version is present for comparison. There is no way to verify that the synthesis is correct, that nothing was lost in combination, or that the two architectures are actually compatible at their interfaces. The claim functions as a trust signal without supporting evidence.

### 3. Self-Congratulatory Meta-Commentary Substitutes for Rigor

Phrases like "the arithmetic makes those inputs visible," "receives equivalent sensitivity treatment," and "this is decorative in this context and is retired" describe the document's own virtues rather than solving problems. The concurrent session model is called "decorative" and discarded, but no justification is given for why the routing fraction approach is more accurate — it's simply asserted to be non-decorative.

### 4. The 17 Notifications/DAU/Day Figure Is Poorly Grounded

The document cites the Braze 2023 Mobile Marketing Report for a "median of 15–20 notifications/day for active users of social apps," then picks the midpoint. But the document itself notes this conflates messaging-heavy apps with content-consumption apps. The working figure is the midpoint of a range drawn from a heterogeneous category. No attempt is made to characterize where this specific app falls within that category, despite the document having enough product context (DM feature presence, social graph structure) to make a more informed placement.

### 5. The 8% SMS-2FA Selection Rate Is Treated as Uncertain But Sized as If It's Known

The document flags this as a pre-launch product decision, which is correct. But then it builds a two-tier cap design around specific numbers (8% and 50%) without justification for why those are the right two tiers. If the decision hasn't been made, the 50% figure is as arbitrary as any other. The document warns engineers to "default to the $2,000/day cap" if the decision isn't made — this is a financial control decision being made by default rather than by product ownership.

### 6. The 13× Peak Factor for SMS Is Unexplained

The 13× peak factor appears for SMS specifically ("security events cluster at login peaks") but is never derived. Login peak factors for security events depend on timezone distribution, attack patterns, and session behavior. The document applies this multiplier to show the cap will be exceeded during legitimate incidents, which is an important finding — but the multiplier itself has no basis shown.

### 7. The Large Viral Event Arithmetic Is Presented With False Precision

The large viral event produces "~20,360,000 notifications" and "~22,600/sec." These figures are computed from assumed inputs (10,000 reshares, avg 2,000 followers per resharer) with no basis. The document acknowledges this is "order-of-magnitude" but presents it to four significant figures. The specific numbers will be cited in future planning discussions as if they were measured.

### 8. The avg_resharer_followers Assumption Drives Everything But Has No Basis

The entire fan-out model hinges on avg_resharer_followers being 800 (moderate) or 2,000 (large). These numbers are invented. On a 10M MAU platform, the follower count distribution is likely highly skewed — a small number of accounts have very large followings. The document acknowledges sensitivity to this distribution but provides no characterization of it and no data source. The moderate vs. large viral event distinction is therefore arbitrary.

### 9. The Comment Fan-Out Cap Is Mentioned But Never Specified

"Prior commenters (capped)" appears in the fan-out table for comments, with fan-out listed as 1–15. The cap value is never defined. This is an operational parameter — if it's set too high, comment threads on viral posts generate significant notification volume; if too low, users miss relevant replies. The design treats it as a solved problem when it's actually an open product and engineering decision.

### 10. Measurement Triggers Reference Section 1.5, Which Doesn't Appear to Exist

Section 1.5 is referenced multiple times as defining "measurement triggers for every major assumption." The document contains no Section 1.5. The triggers are scattered inline throughout Sections 1.1–1.3 instead. The references to Section 1.5 are either forward references to a missing section or internal inconsistencies from the synthesis of two prior drafts.

### 11. The Provisioned Floor of ~1,800/sec Is Never Derived in This Document

The number appears in Section 1.2 as a given ("the provisioned floor of ~1,800/sec") but its derivation is never shown. It is slightly above the working assumption of ~1,750/sec, which provides almost no headroom. The document notes that 40% DAU/MAU with 20/day "exceeds the provisioned floor before viral effects are applied" — which means the floor is inadequate under a plausible success scenario, not just an edge case.

### 12. The Channel Split Percentages Don't Add Up Cleanly

Push (70%) + In-app (20%) + Email (8%) + SMS (<1%) = ~99%. The SMS figure is left as "<1%" without specifying what it actually is. This makes the channel split table internally inconsistent and prevents verification of worker allocation arithmetic downstream.

### 13. The Redis Counter Isolation Claim Is Asserted Without Architecture

"The Redis counter uses a 24-hour sliding window... It is isolated with no eviction policy." This is a single sentence with no supporting design. What does "isolated" mean — a separate Redis instance, a separate database, a keyspace with specific memory limits? No eviction policy on a shared Redis instance is dangerous; no eviction policy on a dedicated instance requires capacity planning that isn't shown.

### 14. The On-Call Runbook Is Cited as a Dependency But Not Included

"The on-call runbook must include a procedure for temporarily raising the cap during verified security incidents." This is a real operational requirement that is deferred to a document that doesn't exist yet. The design creates a dependency on future work without tracking it.

### 15. The Sensitivity Table in Section 1.2 Contradicts the Provisioned Floor

At 30% DAU/MAU and 17/day, the table shows ~1,750/sec. The provisioned floor is ~1,800/sec. This is 2.9% headroom at the working assumption — before any viral contribution. The document presents this as adequate without acknowledging how little margin it represents.