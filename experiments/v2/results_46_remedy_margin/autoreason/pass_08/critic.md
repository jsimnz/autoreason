## Real Problems with This Proposal

### 1. The Cohort Validation Cannot Do What It Claims

The proposal uses a 50K-user beta cohort to validate a 17/day ceiling for a 10M MAU system. The cohort is 0.5% of MAU. The proposal acknowledges early adopter bias and applies tier reweighting, but the fundamental problem is not bias correction — it is that notification rates are driven by social graph density, and social graph density in a 50K cohort is structurally different from a 10M MAU network. A user in a sparse early-stage network generates and receives fewer notifications than the same user type in a mature network. The week-2 measurement will underestimate steady-state rates for this reason, independent of any tier reweighting. The proposal corrects for having too many power users but not for having too few connections per user.

### 2. The 17/day Figure Has No Derivation

The proposal calls 17/day a "planning ceiling" but never shows where it came from. It is not derived from the tier model (no per-tier rates are given), not from industry benchmarks (none cited), and not from prior product data (none exists, apparently). The entire scaling analysis — worker counts, Redis sizing, RDS throughput — depends on this number, and its origin is unaccounted for. The proposal's own corrected estimate from cohort data may come back below 17, which the proposal treats as confirmation, but a number that confirms any result below it is not a ceiling derived from analysis.

### 3. The Tier Weights Are Asserted Without Basis

The proposal applies "scale-representative tier weights" of 5% / 35% / 60% to correct cohort bias. These weights are presented as corrections to the observed cohort weights, but there is no stated basis for believing 5/35/60 represents the eventual general population. For a new social app that has not yet reached scale, the eventual user mix is unknown. Using assumed corrective weights to adjust an already uncertain measurement compounds the uncertainty rather than reducing it.

### 4. The >5× Interim Operating Mode Has an Unexamined Correctness Problem

The proposal describes aggressive batching as reducing instantaneous throughput by "roughly 8–10×" — but this figure is not derived. Batching at 15-minute intervals reduces throughput only if notifications arrive smoothly; if they arrive in bursts (which is the problem being managed), batching shifts the burst rather than flattening it. A 15-minute batch release of accumulated notifications creates a periodic spike at the batch boundary, not a smooth reduction.

### 5. Worker Throughput Is Forward-Referenced Without Derivation in Context

Section 1.3 states "30 P1 workers at ~350/sec each = 10,500/sec sustained capacity" and directs readers to Section 2.3 for derivation. The 350/sec figure for a single worker is doing significant work in the spike analysis — it determines drain times, headroom calculations, and the 10× scenario outcomes. If this figure is wrong by a factor of 2 (plausible depending on provider latency, serialization overhead, and network conditions to FCM/APNs), the entire quantitative spike analysis is wrong. The proposal presents the spike math with false precision given this dependency.

### 6. The Scenario A Alert Is Described as Useless but Kept

The proposal explicitly states the 2M-item page threshold fires "near the end of the burst" and that "manual scaling during a Scenario A burst does not help; the burst is over before intervention is possible." The alert is then justified as existing "to document the event." An alert that pages an engineer for an event that is already over and requires no action is an on-call burden with no operational value. The proposal identifies this problem and does not resolve it — it just explains why the alert is ineffective.

### 7. The SMS Section Is Incomplete

Section 1.4 lists three options for handling auth SMS when the budget cap is hit, states "Option 3 is the correct technical default," and then ends mid-sentence at the bottom of the document. The three outcomes for the required business decision are cut off after outcome 1. This is not a stylistic choice — the document is missing content that it explicitly promises to deliver.

### 8. The Response Time Range for 10× Scaling Is Not Validated

The proposal gives a 4–16 minute range for manual scaling response to a Scenario B 10× event and notes this "is an assumption until the month-5 load test validates it." The 10× scenario analysis — including the claim that worst-case delay is "degraded but not catastrophic" at ~22 minutes — depends entirely on this unvalidated range. If actual response time is 25 minutes (plausible for an on-call engineer woken at 3am), the queue depth at response exceeds 10.5M items and drain time extends significantly beyond the presented worst case.

### 9. The "Compounding Risk" Section Understates the Problem It Identifies

Section 1.1a correctly identifies that the 35% DAU/MAU scenario stresses Redis, RDS, and workers simultaneously, and calls this the "actual risk." But the trigger for action — "DAU tracks above 32% for two consecutive weeks" — is a lagging indicator. By the time two consecutive weeks of 32%+ DAU/MAU have been observed, the system has already been operating under elevated stress for at least two weeks. The proposal identifies compounding simultaneous risk but then proposes a sequential, delayed response to it.

### 10. The LIFO Behavior Acknowledgment Has Incomplete Consequences

The proposal states Redis Lists with BRPOP give LIFO behavior under accumulation and that "this affects every period of meaningful queue depth." The consequence described is that older notifications are delayed during accumulation. But for a social app, older notifications are also more likely to be stale — a "liked your post" notification from 20 minutes ago has less value than one from 20 seconds ago. LIFO behavior means the system preferentially delivers fresher notifications, which may actually be the right behavior. The proposal treats LIFO as a known tradeoff without examining whether it is a problem or an accidental feature, and without describing what happens to the oldest items in the queue during multi-minute accumulation events.