## Real Problems

### 1. The 75/sec Per-Worker Figure Is Internally Inconsistent

The document derives a push worker throughput of 75/sec, explicitly stating this is "10% of peak capacity" (800/sec APNs limit). It then uses 75/sec × 18 workers = 1,350/sec for push alone, which it rounds into the 1,800/sec floor. But 18 workers × 75/sec = 1,350/sec for push, not 1,800/sec. The remaining 450/sec comes from email, in-app, and SMS workers. The summary statement "24 workers × 75/sec = 1,800/sec provisioned floor" is arithmetically false — you cannot multiply a push-specific throughput figure by all 24 workers, which include email, in-app, and SMS workers with completely different throughput profiles.

### 2. The Viral Cohort Derivation Circular-References Itself

The corrected approach criticizes the prior 2× assumption, then substitutes a 35% volume-share assumption attributed to "a log-normal distribution with that shape" — where "that shape" is defined by the Facebook 2014 paper describing top-decile users generating 5–8× the median. The document then integrates over this distribution without showing the integration, without citing the actual paper for the specific claim, and without acknowledging that applying a top-decile ratio from a 2014 Facebook paper to the top 5% of a 10M MAU social app in a different era is itself an assumption of the same epistemic quality as the 2× figure it replaced. The corrected derivation is not structurally sounder — it is longer.

### 3. The SMS Volume Is Derived From an Undisclosed Input

Section 1.1 lists SMS at ~360K/day and says "derived from auth event rate; see Section 1.3." Section 1.3 does not appear in this document. The SMS worker sizing (7/sec, 1 worker sufficient) therefore rests on a derivation that is referenced but absent. This is not a minor gap — SMS has the highest per-unit cost of any channel and the isolated Redis counter for spend capping is called out as a key design decision. The foundation for that entire subsystem is missing.

### 4. The Stress Case Arithmetic Is Inconsistent With Its Own Labels

The 2× stress case is labeled "2×" but the arithmetic does not produce 2× the point estimate. The point estimate is ~2,200/sec. A true 2× case would be ~4,400/sec. The document's derivation produces ~4,205/sec and then rounds to ~4,400/sec — acceptable — but it achieves this by making the cohort 50% larger AND the multiplier 50% higher simultaneously, which is not "2× the point estimate." It is a specific combination of input errors that happens to approximately double the output. The 3× case has the same problem: 300,000 users × 14× multiplier + 560 = ~6,230/sec, rounded to ~6,600/sec, but the inputs are described as "75–100% over point estimate," which is not a consistent description of a 3× scenario. The labels are marketing, not math.

### 5. The APNs Rate Limit Source Is Misrepresented

The document cites "APNs documentation, 2023" for the 1,000 concurrent streams figure, then immediately says the rate limit of 500–1,000/sec is "undocumented but observed." These are two different claims sourced differently, but they are presented in the same sentence with a single citation. The 400/sec design figure — "20% margin below observed lower bound of 500/sec" — is then applied as if it were a documented constraint. APNs rate limits are per-bundle-ID and vary by account tier and Apple's internal policies. Using a single observed lower bound from unspecified sources as the conservative design ceiling for a production system is not conservative — it is an unvalidated assumption with false precision.

### 6. The 4-Minute Scaling Claim Has No Basis

The document states that scaling from 24 to 59 workers "takes ~4 minutes from pre-configured AMIs." No source, measurement, or derivation is provided for this figure. AWS EC2 instance launch time from pre-configured AMIs varies by instance type, region, availability zone conditions, and whether the AMI is warm in the regional cache. Four minutes is plausible but can easily be 7–10 minutes under load or during regional degradation — precisely the conditions under which scaling would be triggered. The 2× stress case response plan depends on this figure being accurate.

### 7. The Email Head-of-Line Blocking Argument Does Not Support the Conclusion

The document argues that email's 2ms CPU cost creates head-of-line blocking in multi-channel workers. The calculation shows email consuming 0.288 vCPU at 1,800/sec total. This is real overhead, but head-of-line blocking is a queuing problem, not a CPU utilization problem. The actual argument for channel specialization should be about queue scheduling — a push notification waiting behind an SMTP connection establishment — not CPU percentage. The 0.288 vCPU figure could equally support an argument for CPU allocation tuning within a multi-channel worker. The conclusion (channel specialization) may be correct, but the evidence presented does not demonstrate the claimed mechanism.

### 8. The Document's Self-Description of Epistemological Honesty Is Undermined by Its Own Structure

The executive summary and Section 1.4 references repeatedly emphasize uncertainty acknowledgment and validation paths. But Section 1.4 is referenced throughout and does not appear in this document. The re-sizing triggers, validation paths, and hard thresholds that are cited as the primary mechanism for managing estimation uncertainty are entirely absent. The document's credibility claim rests on material that is not present.