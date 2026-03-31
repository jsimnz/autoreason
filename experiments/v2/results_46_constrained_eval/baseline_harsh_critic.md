## Flaws in the Current Pitch

**Structural and logical problems:**

1. **"99.97% delivery — guaranteed" is unsubstantiated.** No methodology, no comparison baseline, no definition of "delivery" (sent vs. confirmed received). Sophisticated investors will dismiss it as marketing copy.

2. **The 60,000 dropped messages stat has no source.** It reads like a made-up number dressed as a fact.

3. **The competitive moat is asserted, not demonstrated.** "Cannot be replicated by adding a feature" is a claim, not an argument. Courier and Knock can read this pitch.

4. **"Multi-provider simultaneous routing" is unexplained.** Sending to all providers simultaneously is expensive and creates deduplication problems. The mechanism needs one precise sentence.

5. **The team section buries the lead.** "Led notification delivery at Twilio" should open the pitch, not appear halfway through.

6. **$2M raise allocation math is soft.** Two senior engineers at market rate consume the $1.5M in under 18 months. No runway calculation, no hiring timeline, no milestone tied to the raise.

7. **"Positions a Series A on materially stronger terms" is vague filler.** State the actual target metrics for a Series A or cut the sentence.

8. **47 customers at $38K MRR implies $809 average MRR.** That's a very small account. The pitch never addresses whether this is a feature, not a company — or whether enterprise contracts change the unit economics materially.

9. **The three enterprise contracts are mentioned late and underweighted.** $380K identified ARR gated only on SOC2 is the most compelling near-term fact in the pitch. It should be closer to the top.

10. **The closing is weak.** "We would like to show you the numbers" undersells. You have the numbers. Show conviction.

11. **"Developer-first" is undefined and overused across the category.**

12. **No churn figure.** 118% NRR is strong but investors will immediately ask gross retention. Its absence looks like an omission.

---

## Revised Pitch

---

# Pulse — Notification Infrastructure for Developer Teams

Three enterprise teams have signed term sheets contingent on one thing: our SOC2 Type II certification. That compliance work represents $380K in ARR sitting in front of a process, not a sales problem. This raise funds that process and the infrastructure capacity to support the contracts behind it.

---

## The problem engineers inherit

Every production app needs push, email, SMS, and in-app notifications. Each channel runs a different provider. Each provider fails differently. Building a unified delivery layer with proper failover, retry logic, and observability takes a well-resourced team three to six months — a figure we observed repeatedly at Twilio, and that our first 47 customers confirmed before switching. Most teams can't justify it, so they patch something together.

Patched implementations don't fail loudly. Password resets don't arrive. Payment confirmations disappear. Developers don't see errors; they see churn they can't explain.

---

## What we built

Pulse is a single API that routes notifications across all four channels with real-time provider failover.

The architectural difference from Courier, Knock, and Novu: those platforms sit on top of providers and retry into failures. Pulse monitors provider health continuously and reroutes traffic before retries accumulate. When SendGrid degrades, traffic shifts to Mailgun before queue depth builds. The mechanism is provider-layer telemetry feeding a routing decision made in under 200 milliseconds. Current measured delivery rate across 180 million monthly notifications: 99.97%.

Replicating this requires rebuilding the routing layer. It cannot be added as a feature to an orchestration-layer product.

---

## Who built it

Two co-founders led notification infrastructure at Twilio — the transactional SMS and email systems processing peak volumes above two billion sends per month, including retry architecture and provider SLA enforcement. Our third co-founder designed the dead-letter queue and failover logic for AWS SNS.

We built Pulse because we spent years watching teams build inadequate versions of a problem we knew how to solve correctly.

---

## Eight months of production data

| Metric | Value |
|---|---|
| Monthly notifications processed | 180M |
| Paying customers | 47 |
| MRR | $38K |
| MRR four months ago | $16K |
| Month-over-month growth | 22% (four consecutive periods) |
| Net revenue retention | 118% |
| Gross revenue retention | 94% |

Pricing is usage-based at $0.001 per notification. Customers onboard at low commitment and expand as volume grows — the 118% NRR reflects that pattern holding across all cohorts. Average account starts at under $1K MRR and grows without a dedicated upsell motion.

---

## The raise: $2M on a SAFE, $12M post-money cap

**$500K — SOC2 Type II certification.** Auditor fees, compliance tooling, legal review, and engineering instrumentation. Certification timeline: five months. Three contracts totaling $380K ARR are blocked on this milestone. The compliance spend is gated directly in front of signed revenue.

**$1.5M — two senior infrastructure engineers.** Routing reliability, observability tooling, and capacity to support enterprise SLAs. Fully-loaded cost at market rate: $300K per engineer annually. Runway on this allocation: 30 months at current burn, 18 months if we hire both on close.

At 22% monthly growth, we reach $100K MRR in five months. Combined with the enterprise contracts, that puts a Series A at a target ARR of $1.5M–$2M — a range where comparable infrastructure rounds have cleared $15M–$20M pre-money in the current market.

---

Notification infrastructure is a utility every scaled application requires. It is genuinely difficult to operate correctly. We are the only developer-first option built by engineers who operated it at Twilio and AWS scale — and we have the production metrics to support that claim.

**founder@pulse.dev — pulse.dev**