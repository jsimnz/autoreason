Here are the real problems with this proposal:

**1. The opt-out violation estimate is presented as if it's derived, but it isn't.**
"150–750 opt-out violations per day" appears in the executive summary as a specific range requiring legal sign-off, but nowhere in the document is the derivation shown. What is the assumed cache staleness window? What fraction of users are actively changing preferences? What is the preference-change rate? The number is stated with false precision and then used to create urgency around a sign-off, but a reviewer cannot validate or challenge it.

**2. The SMS aggressive scenario math is inconsistent with itself.**
The table shows the aggressive scenario as login_rate=0.40, OTP_rate=0.20, producing 300K SMS/day at $67.5K/month. But the executive summary states the realistic worst-case is $33–40K/month. These two numbers cannot both be correct given the same assumptions. The document never reconciles them, and the discrepancy is large enough to matter for the budget sign-off it's requesting.

**3. The viral spike model is circular.**
The document sizes for 3,500/sec because of a viral spike model producing 3,125/sec, then says the spike is "absorbed by queue depth" with only 12% headroom. If the spike is absorbed by queue depth rather than by worker throughput, then the sizing target is not actually driven by the spike — it's driven by normal-use peak with the spike handled by backlog. The document cannot simultaneously claim the sizing target covers the spike and that the spike is handled by queuing.

**4. The SendGrid throughput constraint is introduced and then dropped.**
Section 1.1 correctly identifies SendGrid as the binding constraint at high email volumes, noting standard plans support only ~27 emails/sec. The planning basis requires 181 emails/sec. This means the planning basis already exceeds standard SendGrid plan capacity by 6x. The document then says the 35%/30 scenario requires only "a SendGrid plan negotiation" — but it never addresses that the planning basis itself requires a non-standard contract. This is not a high-scenario problem; it is a Day 1 procurement problem.

**5. The peak concentration model applies only to push but is labeled as combined.**
The sensitivity matrix column labeled "Combined Peak/sec" adds push+in-app peak and email peak, but the email peak is derived from a different concentration assumption (80% in 4 hours, from the table footnote) while the push peak uses 90% in 4 hours. SMS peak is not included at all despite having its own queue. The "combined" figure is not actually combined — it omits SMS and uses inconsistent concentration assumptions across channels.

**6. The worker count is never specified.**
The document repeatedly states that the solution to throughput overruns is "add workers," but the baseline worker count for any queue is never given. Without a baseline, "add workers" is not a concrete escalation action — it is a placeholder. The Month 2 decision gate ("add workers before Month 3") has no operational meaning if the current worker count is unknown.

**7. The escalation default selection is structurally broken.**
Defaults A, B, and C are presented as a pre-document-finalization requirement, but Default C contains a bracket placeholder that the document itself says must be filled before finalization. This means the document cannot be finalized with Default C selected unless someone fills the bracket — but the document is being circulated for sign-off on Default C selection before the bracket is filled. The dependency is circular and will predictably result in the bracket never being filled before the document is treated as final.

**8. The DAU/MAU sensitivity table shows email volume is nearly flat, but this is presented as a reassuring finding when it should be a warning.**
The document calls the flat email curve "a derived result, not an assertion." But the flatness means email cost and throughput requirements are largely insensitive to whether the product succeeds or fails at engagement. A team that thinks it can reduce email infrastructure costs by improving retention is wrong. This implication is not drawn out, and the finding is framed as a validation of the model rather than a constraint on the product's cost structure.

**9. The runbook coverage claim is unverifiable as written.**
Section 5 is referenced in the executive summary as describing "a runbook that covers the five most common failure patterns, owned and tested before Month 6." Section 5 does not appear in the document as provided. The executive summary is making a specific operational claim about a section that either doesn't exist or was cut, and that claim is load-bearing for the "proven infrastructure" architectural bet.

**10. The 30-second average queue depth assumption has no basis.**
The Redis working set calculation uses "30-second average queue depth" as an input, producing a ~30MB working set. This number is never justified. Queue depth depends on worker count, provider latency, and backlog behavior — none of which are specified. If average queue depth is 5 minutes during a viral spike (a plausible number given 12% headroom), the working set grows by 10x, which is still manageable but changes the memory sizing analysis. The assumption is doing real work in the calculation and is unsupported.