## Real Problems with This Proposal

### 1. The Confidence Interval Derivations Are Not Actually Shown

The document repeatedly claims delay figures have confidence intervals "derived from input distributions" and references "§2.3 with complete derivations," but §2.3 is never shown in the excerpted document. The executive summary table presents figures like "47 min (CI: 15–110 min)" as if they are derived, but no derivation is visible. The document status section lists "complete derivations in §2.3" as a resolved finding from a prior version, yet the reader cannot verify this claim. If the CI is just the delay figure scaled by the ±50% volume uncertainty, that's not a derivation from input distributions — it's a scaling, and those are different things.

### 2. The 30/sec Per Worker Figure Is Presented as a Midpoint of a Range It Doesn't Actually Center

The document says 30/sec is the "midpoint" of a 2.7× latency range of 15–40ms. But 15–40ms processing latency does not directly translate to 25–67 ops/sec in a simple inversion — that would be true only if a worker is purely serial with no I/O overlap, no batching, and no overhead. The worker capacity range given is 22–53/sec, which doesn't correspond to the inversion of 15–40ms either. The arithmetic is never shown, and the claimed midpoint (30/sec) sits closer to the low end of the 22–53 range, not the middle. This inconsistency is unresolved.

### 3. Session-Correlation Applied to Email Routing Creates a Circular Dependency That Isn't Resolved

The document notes that email routing depends on detecting whether a user has an active session at routing time. During a spike — exactly when the system is most stressed — Redis may be unavailable or under pressure. If the session-correlation check depends on Redis, and Redis is in failover (10–30 second window per §5.3), the routing logic cannot determine session state. The document does not specify what the fallback routing behavior is when session state is unavailable. The in-app consistency contract is addressed in §4.3, but the email/push routing fallback during Redis unavailability is not addressed anywhere visible.

### 4. The "Recoverable vs. Unrecoverable" Default Framing for Decision A Is Asserted, Not Demonstrated

The document justifies changing the default from Option A to Option B on the grounds that Option B is reversible and Option A "by inaction was not recoverable in the same way." But the upgrade path from Option B to Option A is described as "approximately 2 engineer-weeks" — which means it requires timeline slack. Whether that slack exists is supposedly addressed in §7.1, but the actual aggregation isn't visible here. The claim that Option A has "no defined downgrade path if it proves over-engineered" is also asserted without analysis. A dedicated worker pool can be collapsed into a shared pool; that's not obviously harder than the reverse.

### 5. The Burst Multiplier Scenario Analysis Replaces One Uncalibrated Figure With Another

The document criticizes the prior version for using an uncalibrated 12× burst multiplier, then replaces it with a 3–5× range from Firebase engineering posts described as "the entire cited basis." But the sensitivity table uses 5× as the stress case for sizing. The document then states that "any multiplier above 5× is extrapolation beyond cited data and is treated as a qualitatively different failure mode." This is definitional, not analytical. Treating >5× as a different failure mode doesn't mean it won't happen — it means the document has chosen not to plan for it. For a social app specifically, viral events driving >5× spikes are a foreseeable scenario, not an edge case requiring separate treatment.

### 6. The Interaction Analysis for Decisions A and B Is Incomplete

The document identifies the key interaction question: "Is priority isolation required during infrastructure failover?" But it presents this as a binary. There is a third option not analyzed: Option B (weighted fair-share) with a modified fallback that provides partial priority isolation during PostgreSQL failover — for example, by maintaining separate PostgreSQL queues per priority tier. The document's framing forces a choice between full priority isolation (Option A) and no priority isolation during failover (Option B + Sentinel), when the actual design space is larger.

### 7. The Volume Summary Table Is Cut Off

The in-app row in the Volume Summary table ends mid-sentence: "Client-side read; not a" — the document is truncated. This is not a minor formatting issue; it means the accounting summary that the entire channel exclusivity argument depends on is incomplete.

### 8. The DAU/MAU Validation Commitment Has a Gap Between the Trigger and the Action

The validation commitment says: measure DAU/MAU at 500K MAU; if above 45%, "re-evaluate worker count before scaling to 2M MAU." But the document doesn't specify what "re-evaluate" means operationally, who has authority to delay the scale-up, or what the lead time is to provision additional workers. A 45% DAU/MAU ratio at 500K MAU means the system is already in the "slight overload" scenario from the sensitivity table. The gap between detection and remediation is unaddressed.

### 9. The 78% Weighted Daily Email Fraction Is Derived From Assumed Session Fractions That Are Themselves Unvalidated

The email volume model constructs a weighted average from three time windows with assumed "not in session" fractions (65%, 80%, 95%). These fractions are not sourced — they are not from the Braze survey, the Firebase posts, or any other cited reference. They are presented as inputs to a calculation that then produces a figure (7.8M/day) treated as a planning number. The document acknowledges DAU/MAU and opt-in rate as unvalidated assumptions but does not flag the session-distribution fractions as equally unvalidated.

### 10. The "More Workers, Not a Different Queue Topology" Claim Is Repeated as a Design Principle Without Justification

The document states twice that if spike delays are unacceptable, "the answer is more workers — not a different queue topology." This is asserted as a conclusion but never argued. There are queue topology changes — such as adding a spillover queue with different drain priority, or per-notification-type queues — that could reduce delay for specific high-priority types without adding workers. The document's dismissal of topology alternatives appears to foreclose design options without analysis.