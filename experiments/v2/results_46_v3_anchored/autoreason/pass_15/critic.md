## Real Problems with This Proposal

### 1. The Spike Model Is Cut Off

The document ends mid-sentence: "We cannot size workers for every—". Section 1.1 is incomplete. The viral spike model, which was explicitly called out as important ("The problem with 'we'll monitor and respond'"), has no resolution. Downstream sections referencing spike behavior (worker sizing, queue depth limits, circuit breakers) are presumably built on analysis that doesn't exist in this document.

### 2. The 25% Headroom Claim Is Structurally Inconsistent

The document states worker sizing targets 2,650/sec with "approximately 4% headroom" over the 2,540/sec combined peak, then separately claims "25% volume headroom" as the primary buffer against growth. These two headroom figures apply to different things and the document conflates them. The 4% throughput headroom is the actual operational margin. The 25% volume headroom (38.5M → 48.1M/day) is a daily capacity ceiling, not a peak throughput buffer. At the same concentration ratios, a 25% volume increase produces a 25% peak rate increase — which would be 3,175/sec against a 2,650/sec worker ceiling. The document never reconciles this.

### 3. The Reassessment Trigger Fires Too Late to Matter

The trigger activates at 13/DAU/day, leaving 5.7% headroom before the capacity ceiling. The reassessment process then takes up to 8 business days (5 days for projection + 3 days for stakeholder decision). If notification rate is growing, the system may breach capacity during that 8-day window. The document acknowledges the monitoring-vs-response-time problem in the viral spike section but doesn't apply the same logic to the gradual densification case.

### 4. The Email Peak Rate Reduction Is Presented as a Win but Depends on an Unverified Architectural Requirement

The document reduces the email peak from 203/sec to 132.6/sec (a "real cost reduction") based on the assumption that the scheduler implements rate-limited dispatch. This is then described as "a launch prerequisite, not an assumption to be validated later." But the SendGrid contract tier (215/sec sustained) is being sized and presumably signed before the scheduler is built and verified. If the scheduler launches without proper rate-limiting — a realistic failure mode — the actual peak could exceed 600/sec, blowing past the contracted tier. The contract decision and the architectural verification are not sequenced correctly.

### 5. The Self-Hosted Fallback Milestone Impact Is Understated

The document says the Month 2 in-app milestone slips to Month 3 if the SendGrid contract fails. But 6–8 engineer-weeks of email infrastructure work in Months 1–2 on a 4-engineer team is 15–20% of total team capacity for that period, not just the in-app slip. The document doesn't account for what else moves — push delivery hardening, preference system, batching logic — it only names one milestone impact.

### 6. The Compliance Architecture Decision Is Deferred Without a Fallback

Section 2.4 is referenced but not included in this excerpt. The executive summary states the cache-with-staleness path "is not available for selection" pending legal review. But there is no stated behavior if legal review is not completed before launch. The document requires legal sign-off but specifies no deadline, no default architecture that activates in the absence of a decision, and no launch gate that enforces this. Compare this to the escalation default (Default A activates automatically) — the compliance item has no equivalent.

### 7. The 1% DAU SMS Assumption Has No Basis

The SMS volume derivation states "1% of DAU trigger an SMS-required authentication event per day" with no citation, no comparison to industry benchmarks, and no discussion of how this changes with 2FA enrollment rates, bot activity, or account recovery patterns. The sensitivity table goes up to 5% DAU but doesn't explain what drives movement between scenarios. The planning basis of ~$17K/month could be off by 4x under the "aggressive 2FA" policy, which is not a hypothetical — it's a product decision that may already be made.

### 8. The Graph Densification Factor Is Named and Then Ignored in the Model

The document explicitly calls out graph densification as "a known unmodeled factor" that increases per-user notification rates without DAU growth. It then proceeds to use DAU-scaled volume projections throughout. The reassessment trigger (13/DAU/day) would catch densification only if it manifests as higher observed rates — but if the graph is densifying, the per-DAU rate increases while DAU stays flat, which is exactly what the model can't predict in advance. The trigger may not fire on the right signal.

### 9. The SendGrid Contract Tier Is Sized for a Scenario That Requires a Product Decision Not Yet Made

The required contract tier (215/sec) is sized for the 50% re-engagement scenario. But the 30% re-engagement rate is described as "a product policy assumption, not a neutral planning basis" requiring Product confirmation by Week 2. If Product selects 10% re-engagement, the contract is over-provisioned. If Product selects 100% (daily digest), the contract is inadequate at 238/sec peak. The contract is being sized against a policy assumption that is simultaneously flagged as unconfirmed — with the same Week 2 deadline as the SMS budget decision, but no stated consequence if Product misses it.

### 10. Four Engineers for Six Months Is Never Stress-Tested Against the Work Described

The document accounts for 6–8 engineer-weeks for self-hosted email fallback and 2 engineer-weeks for batching changes if option (b) is selected in the reassessment process. It mentions a Month 2 working system, Month 5 iteration, and Month 6 hardening. But there is no aggregate engineer-week budget showing whether the described work fits in 96 engineer-weeks. Given the compliance architecture, preference system, four-queue monitoring overhead, viral spike handling, and the SendGrid/self-hosted fork, the absence of any capacity accounting is a real gap — not a formatting issue.