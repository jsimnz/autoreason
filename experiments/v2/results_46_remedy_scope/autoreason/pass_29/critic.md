## Real Problems Found

### 1. SMS Cost Arithmetic Is Wrong by Orders of Magnitude

Section 1.2 states SMS costs "approximately $9,000/day at list price" at 900K messages/day and $0.01/message. 900,000 × $0.01 = $9,000. That's actually correct for a single day, but the document never flags that this is **$3.3M/year** at the planning baseline. More critically, the "5% of volume" scenario is stated as "daily cost exceeds $22,000" — that's 2.2M messages × $0.01 = $22,000/day, or **$8M/year**. A document this careful about other risks treats a potential $8M/year cost exposure as a one-paragraph note with no owner, no hard cap, no kill switch specification, and no approval threshold. The SMS opt-out compliance owner in Section 5.4 is named as responsible for "monitoring this" — monitoring cost is not the same as having authority to act on it.

### 2. The Document Is Truncated Mid-Section

Section 1.3 ends mid-sentence: "`notif`" — the deployment list is cut off. This is the section operators are directed to during incidents. The "How to Use This Document" section sends readers to Section 1.3 for traffic spikes, scale-down, dashboard failures, and the >80M/day scenario. The CLI commands and deployment names promised in the introduction to Section 1.3 are absent. Finding 8 in the revision table was "paragraph completed in full" — this document repeats that failure in a more operationally critical location.

### 3. Sections 1.3a Through 8 Are Entirely Absent

The Table of Contents lists 1.3a, 1.3b, 1.3c, 1.4, 1.5, and all of sections 2 through 8. None of them appear in this document. The revision table claims findings 3, 4, 5, 6, 7, 9, 10, 11, 12, and 13 are resolved and cites specific section numbers as verification locations. Those sections do not exist in this document. This is the same structural failure as Revision 2, which was finding 1. The revision table's own first row — "All sections in the ToC are now present in this document" — is false.

### 4. The Revision Table's Verification Claims Are Systematically False

The table states findings are "resolved" and directs readers to verify at specific sections. Finding 3 says "Section 7.1 is present" — it is not present. Finding 4 says resolutions are at "1.1, 2.2" — Section 2.2 does not exist in this document. Finding 5 says both FCM/APNs branches are "specified in full" at "1.4, 6.1, 6.2" — none of those sections exist. Finding 6 says the 90-second derivation is "present in Section 4.2" — Section 4 does not exist. Finding 7 says the 45-minute fanout derivation is "present in Section 3.2" — Section 3 does not exist. The revision table is not a record of what was done; it is a record of what was intended, presented as fact.

### 5. The 45-Minute Fanout Bound Is Still Asserted, Not Derived

Section 1.1 states the worst-case fanout completion time is "approximately 45 minutes for a 100,000-recipient event" and says "That bound is derived from token bucket parameters in Section 3.2, not asserted here." Section 3.2 does not exist in this document. This is the exact problem identified as Finding 7 in the revision table, which claims it is resolved. It is not resolved.

### 6. The 90-Second Crash Recovery Bound Is Still Asserted, Not Derived

The executive summary states crash recovery reclaims orphaned entries "within a 90-second window" and says "The derivation of that bound is in Section 4.2." Section 4.2 does not exist. This is Finding 6, claimed resolved.

### 7. Circular Dependency Between Unresolved Decisions Is Not Managed

The "How to Use This Document" section states: "The Redis provisioning decision (Section 6.1) depends on two prior decisions in order: (1) the cross-channel deduplication retention window (Section 2.2), then (2) the FCM rate verification outcome (Section 1.4)." The fallback for decision 4 (deduplication retention window) is 24 hours. The fallback for decision 1 (burst allowance) is 3. But there is no fallback specified for the FCM rate verification outcome — it is a verification procedure, not a product decision, so it has no listed fallback. If FCM rate verification is not completed before launch, the Redis provisioning decision has no path to resolution even if all product decisions use their fallbacks. The document does not address this.

### 8. Named Owners and Deadlines Are Referenced but Cannot Exist

The document repeatedly states "Owner and deadline: Section 7.1" for five separate decisions. Section 7.1 does not exist in this document. The pre-flight checklist referenced throughout also lives in Section 7.1. The escalation chain in Section 1.1 references Section 7.2 for the day-34 fallback. Section 7.2 does not exist. Every operational dependency on named humans is unresolvable.

### 9. The Day-34 Escalation Fallback Has a Logical Gap

Section 1.1 states that if the backup is unavailable by day 34, "the fallback is specified in Section 7.2: it names the senior engineer on the current on-call rotation by role, not by name." This means the fallback authority is whoever is currently on call — but if the primary and backup are both unavailable, there is no stated mechanism for determining who is on call or where the on-call schedule lives. A role-based reference only works if the on-call schedule is accessible. No location for that schedule is specified.

### 10. The "No Daily Cap" Fallback Accepts Unbounded Spam Risk Without Quantifying It

The fallback for the daily spam threshold decision is "no daily cap enforced; spam risk accepted until product decides." The document identifies power users generating 50+ notifications/day as a stress case but does not quantify what "spam risk accepted" means in operational terms — no estimate of what fraction of users might hit problematic volumes, no specification of what triggers a retroactive decision, and no stated condition under which engineering can act unilaterally without the product decision. "Until product decides" has no deadline and no escalation path if product never decides.

### 11. Peak Multiplier Methodology Produces Internally Inconsistent Results

The document states "peak_rate = (daily_volume × peak_multiplier) / 86,400" and calls the extreme row's 4.76× higher peak rate relative to the plan row "a consequence of the methodology, not an error." But the methodology divides by 86,400 seconds regardless of what the peak multiplier represents. If the multiplier is a ratio of peak-hour rate to average rate, dividing total daily volume by 86,400 and then multiplying by the multiplier does not produce a peak rate — it produces an average rate scaled by a factor whose meaning is undefined. The document does not define what the peak multiplier actually represents (peak hour vs. average? peak minute? burst?), making the resulting numbers unverifiable and the "not an error" claim unsupported.

### 12. The Revision Process Itself Is Now a Credibility Problem

This is Revision 3. The revision table documents 13 findings from Revision 2 and claims all 13 are resolved with auditable evidence. The majority of those claims are false — the sections cited as evidence do not exist. A reviewer who trusted the revision table and spot-checked one or two sections might miss this. The revision table creates the appearance of rigor while the document remains structurally incomplete. This is a worse failure mode than Revision 2, which did not claim to have fixed things it had not fixed.