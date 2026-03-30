## Real Problems with This Proposal

### 1. The 17/day Figure Is Circular

The cohort validation is supposed to validate the 17/day planning assumption, but the system is already being sized to that number before the cohort data exists. The week-2 gate only triggers adjustments — the queue architecture, worker baseline, Redis sizing, and infrastructure procurement decisions all precede it. The validation is presented as a check but functions as a post-hoc confirmation of decisions already made.

### 2. The >5× Gap Is Acknowledged But Not Actually Handled

The document explicitly states there's a 1–2 week decision window against a 5–7 month fix time, calls it an "honest gap," and then says the resolution is "executive sponsorship" and a "go/no-go." This is not a contingency plan — it's a description of being stuck. Naming the gap doesn't close it. The document treats transparency about the problem as equivalent to solving it.

### 3. LIFO Acceptance Is Understated for P1

The document acknowledges LIFO inversion but frames it as a rare post-spike edge case. However, LIFO behavior affects *every* period of queue accumulation, not just extreme spike drains. Any sustained load above worker throughput — including normal diurnal peaks if sizing is slightly off — produces ordering inversion. The "nearly empty queue" assumption that makes LIFO acceptable only holds if the system is never meaningfully backlogged, which contradicts the spike scenarios the system is explicitly designed to handle.

### 4. The 3-Minute Manual Scaling Estimate Is Load-Bearing and Unvalidated

The spike math depends on manual intervention at the 3-minute mark. This figure is used to bound worst-case delay calculations. The document acknowledges it's unvalidated until month 5 but doesn't account for what the spike math looks like if the actual response time is 10 or 20 minutes. The calculations presented as bounding the problem are built on an assumption that could be wrong by an order of magnitude.

### 5. P0 Sorted Set Ordering Doesn't Solve the Problem It Claims To

Using Redis Sorted Sets with timestamp scores for P0 ensures FIFO ordering *within the queue*, but P0 notifications (authentication codes, security alerts) have correctness requirements that go beyond ordering. An auth code that sits in a queue for any duration — even in perfect FIFO order — may expire before delivery. The ordering fix addresses the wrong property. The actual P0 problem is latency, not ordering.

### 6. The DAU/MAU Sensitivity Analysis Omits Compounding Effects

The table shows DAU/MAU ratio effects on individual variables in isolation. A 35% ratio doesn't just add 6 P1 workers — it simultaneously increases Redis memory pressure, RDS write throughput, and the spike scenario math, all of which interact. The proposal presents these as independent adjustments but they're not. The 35% scenario may push multiple components past thresholds simultaneously in ways the isolated sensitivity table doesn't reveal.

### 7. Tier Reweighting Assumes Stable Tier Boundaries

The bias correction applies scale-representative weights (5%/35%/60%) to observed tier rates. This assumes the tier boundaries themselves are meaningful — that "top 10% by content generation" in the cohort maps to the same behavioral reality as "top 10%" in the general population. In an early adopter cohort, the bottom 50% may still be significantly more engaged than the eventual general population's bottom 50%. The correction adjusts proportions but not the rates within each tier, which may themselves be inflated across all tiers.

### 8. The SMS Default Decision Is Made Without Authorization

The document states that if the product/finance decision isn't made by month 3, E2 will implement Option 2 (restricted notification SMS, uncapped auth SMS) as the default. This is an engineer unilaterally making a business and financial decision — uncapped auth SMS has real cost implications — because a deadline was missed. The proposal frames this as responsible default behavior, but it's actually the technical team making a spending commitment that belongs to finance.

### 9. The Viral Spike Scenario A Math Is Never Completed

Scenario A (20× instantaneous, 90–120 seconds) is described qualitatively — "the queue absorbs the burst; workers drain over the following minutes" — but the actual drain time is never calculated. The document provides full math for Scenario B (5× sustained) and the undesigned-for 10× case, but the 20× burst scenario, which is described as the more extreme spike type, has no quantitative drain analysis. The claim that queuing handles it is asserted, not demonstrated.

### 10. The Document's Self-Referential Structure Creates Verification Burden

Multiple sections explicitly depend on numbers derived in other sections ("the spike math here depends on figures in Section 2.3," "both sections are present"). Section 1.3 cannot be evaluated without Section 2.3, which isn't included in this document. The proposal presents itself as unusually transparent, but critical load-bearing numbers are deferred to sections that aren't shown. Reviewers are asked to trust that the derivations exist and are correct.

### 11. The "Incremental Delivery" Bet Conflicts with the Validation Timeline

The proposal commits to a working single-channel system by end of month 2. The week-2 cohort validation — which could trigger a complete architectural reassessment — occurs *before* that milestone but after design decisions are locked. If the >5× case is confirmed in week 2, the month-2 milestone is already being built on the wrong foundation. The incremental delivery timeline and the validation gate are sequenced such that the validation can only confirm a problem after significant build work is underway.