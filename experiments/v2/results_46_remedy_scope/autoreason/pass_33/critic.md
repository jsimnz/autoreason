## Real Problems

### 1. The Fallback Authority Contradiction Is Unresolved

The document repeatedly states that "engineering does not have unilateral authority to make product behavior decisions" — but the fallbacks are engineering-specified values (3 burst, 200/day cap, 24-hour deduplication window, Option A). If product owners have authority over these decisions, engineering selecting the fallback *is* engineering making the product decision unilaterally. The document doesn't resolve this; it papers over it by calling silence "a choice the owner owns." That's a governance fiction, not a governance structure.

### 2. The SMS Cost Exposure Is Underspecified in a Way That Matters

The document calculates $15,000–$75,000/day in potential unbudgeted SMS costs and names a "budget owner" who must review this. But the budget owner is not named here — they're deferred to Section 7.1, which is cut off. If that person doesn't exist, has no budget authority over SMS, or is the same person as the product owner, the entire review mechanism fails silently. The document treats a named-person dependency as resolved when it is not.

### 3. The 90-Second Crash Recovery Window Derivation Is Referenced But Not Present

The executive summary says "the derivation of that window is in Section 4.2." Section 4.2 is listed in the table of contents but not included in the document. The window is cited as a design basis for the duplication-not-loss claim, which is itself a qualified claim with a known exception (the Redis promotion window). Readers cannot evaluate whether 90 seconds is correct, conservative, or arbitrary.

### 4. The Correlated Sensitivity Table Has an Unstated Assumption Baked Into Its Structure

The table presents four discrete rows as if they represent the meaningful scenario space. But the document already acknowledges that DAU/MAU ratio and notifications-per-user are positively correlated and that treating them as independent understates risk. The table doesn't model intermediate cases — e.g., high DAU/MAU with moderate notification rate, or moderate DAU/MAU with extreme notification rate. These are plausible real scenarios (a high-retention app with conservative notification policy, or a low-retention app with aggressive re-engagement). The table's structure implies these scenarios don't exist.

### 5. The Month-1 Recalibration Procedure Is Cut Off Mid-Sentence

Section 1.1 ends with "Compute the number of hours per" and stops. This is not a minor formatting issue — the recalibration procedure is load-bearing. The document explicitly states that all peak rate figures carry ±25% uncertainty until recalibration occurs, and that the procedure is "specified in Section 1.1, not referenced to it." The procedure does not exist.

### 6. The Token Bucket Starvation Prevention Is Circular at This Point in the Document

Section 1.1 derives the fanout worst-case completion time from a P2 guaranteed rate of 200 tokens/sec, citing Section 3.2 as the source. Section 3.2 is not included in this document. The fanout SLA claim — "~10 minutes worst case" — has no verifiable basis in what is actually written here. The document acknowledges the dependency explicitly but doesn't resolve it for the reader.

### 7. The Redis Promotion Window Loss Scenario Is Acknowledged Without a Probability Bound That Is Actually Calculable

The executive summary states the Redis primary failure scenario has "its probability bound" specified in Section 6.2. Section 6.2 is listed in the table of contents but not present. A probability bound on a hardware failure during a specific replication window requires knowing the replication lag distribution, the promotion window duration, and the primary failure rate — none of which are stated anywhere in the visible document. The claim that a probability bound exists is not the same as the bound existing.

### 8. The Fanout Cap Options Have Asymmetric Engineering Review Requirements That Are Not Explained

Option C requires "one sprint" of engineering review before acceptance, but Options A and B require none. The document doesn't explain what makes Option C different in a way that requires review. If the concern is queue saturation risk from a higher cap, that risk exists for Options A and B as well — the document already derived worst-case completion time under sustained congestion. The asymmetry is asserted, not justified.

### 9. Decision 4's Correctness Note Asks the Product Owner to Answer a Question Engineering Should Already Know

The deduplication window correctness note asks whether the notification feed is "append-only" or "deduplicated at read time by event ID." This is not a product preference question — it is a question about how the existing product works. Engineering either knows this or can find out. Framing it as something the product owner must answer before accepting the fallback is either a documentation gap or an admission that the system being designed has not been integrated with the existing product architecture.

### 10. The Six-Worker Reduction Rationale Is Deferred to a Section That Isn't Present

The executive summary states the reduction from 16 to 6 worker deployments is justified by staffing arithmetic in Section 1.5. Section 1.5 is listed in the table of contents but not included. The claim that 6 deployments is the correct number given the staffing constraint cannot be evaluated. The document presents the conclusion as if the arithmetic is available when it is not.