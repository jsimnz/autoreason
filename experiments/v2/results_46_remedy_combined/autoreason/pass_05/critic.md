## Real Problems with This Proposal

### 1. The Scale Model Is Internally Inconsistent

The proposal sizes worker capacity for 210M push/day (worst case) but sizes costs against 82.5M push/day (base case). These are used in the same cost justification. If the worst case materializes, cost projections are wrong by a factor of 2.5x. The document acknowledges this gap but does not resolve it — it just names it and moves on. A team operating under a budget will hit an unpleasant surprise if the high scenario materializes, which is precisely the scenario the architecture is supposedly designed for.

### 2. The FIFO Queue Section Is Incomplete and Cut Off Mid-Table

Section 2.2 ends abruptly. The table modeling P1 volume against traffic fraction is truncated. This is not a minor formatting issue — the FIFO throughput ceiling is identified as a structural risk that could require a full architecture migration (Scaling Trigger B). The analysis that would justify confidence in the design is simply missing. The document cannot be reviewed or approved in this state.

### 3. The Email Digest Volume Is Asserted, Not Modeled

The proposal says "up to 3M users × 1 email/day = 3M emails/day maximum" but provides no model for what fraction of users actually opt into daily digest vs. weekly vs. none. The transactional email section is carefully modeled from event rates; the digest section is just a ceiling. These are treated equivalently in the summary table, which obscures that one number is a model output and the other is a cap that may never be approached.

### 4. The OTP SMS Cost Model Has a Category Error

The proposal models OTP SMS volume as "~5% of DAU" triggering 2FA logins. But DAU for a 10M MAU social app is not 10M — it is typically 30–50% of MAU, or 3–5M users. Using MAU as the denominator for a daily action rate inflates the baseline estimate. The credential stuffing scenario then uses "20% MAU" for forced re-auth, mixing denominators within the same threat model.

### 5. The Preference Staleness Tradeoff Is Named But Not Bounded

The executive summary says the preference system "trades occasional staleness for throughput" and calls this an explicit tradeoff. But nowhere in the visible document is the staleness window defined, measured, or bounded. "Occasional staleness" is not a specification. A user who opts out of push notifications and receives them for an unspecified window afterward is a legal and trust problem, not just a product quality issue. The proposal identifies this as a known tradeoff without quantifying what is being traded.

### 6. The E2 "Fix" Is Not Actually Fixed

The revised allocation gives E2 650h against a 768h budget and calls it "still tight but workable." But the 768h individual budget already subtracted 20% for on-call, meetings, code review, and ramp-up. E2 owns two of the most integration-heavy channels (push and email), shared ownership of cross-channel consistency, and is the most likely person to be pulled into unplanned work when push token management breaks in production. "Tight but workable" for the most loaded engineer on the most complex channels is not a resolved problem — it is a deferred one.

### 7. The Security Default Is Pre-Decided Without the Authorization It Claims to Require

The proposal explicitly states that decisions requiring authorization from outside engineering are identified and the engineering default is stated. Then, for the email OTP fallback during a security incident, it says: "This default is documented here so Security can review it and override it if their threat model requires a different posture." This is not the same as obtaining authorization before launch. The code shown implements the fallback as a fait accompli. The proposal cannot simultaneously claim it does not make business risk decisions unilaterally and then implement a security-incident authentication posture subject only to a post-hoc review.

### 8. The Test Harness Contingency Has No Mechanism for Scope Renegotiation

The 80h contingency tranche is described as releasing when dependent designs are complete, with the note that "if they are more complex, scope will be renegotiated at that point with actual information." There is no process defined for this renegotiation — no owner, no decision point, no criteria. In practice, when those designs complete at month four and the 80h is insufficient, the buffer has already been partially consumed by integration and bugs. "Renegotiate with actual information" is not a mechanism; it is an intention.

### 9. The Scaling Trigger Ownership Is Structurally Problematic

Scaling Trigger B — the one that requires a structural architecture migration from FIFO to standard queues — lists E1 as owner and says it "requires full team review before activation." But Trigger B fires during sustained peak traffic, which is exactly when the team is least available for a deliberate architectural review. The proposal provides no pre-authorization criteria, no pre-staged migration plan, and no definition of what "full team review" means under incident conditions. The trigger is defined but not actionable.

### 10. Industry Opt-In Rate Data Is Cited Without Sources

The proposal defends the 55% blended opt-in rate with specific figures ("iOS opt-in rates post-iOS 14 range from 40–55%... Android opt-in is higher, approximately 70–80%") but cites no sources. These figures are used to justify the central cost estimate. If they are wrong — and opt-in rates vary substantially by app category, prompt timing, and user demographics — the base scenario cost model is wrong. The proposal presents these as "defended with industry data" but the defense is assertion, not citation.