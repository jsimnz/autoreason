## Real Problems with This Proposal

### 1. The 30% Re-engagement Send Rate Is Completely Unexamined

The document notes that the near-flat email cost across DAU/MAU scenarios is "a consequence of holding that send rate constant" and warns it "does not generalize beyond the 30% send-rate assumption." But it never justifies where 30% comes from. It's presented as a planning basis with no benchmark, no source, and no sensitivity analysis. The spike model gets a full sensitivity table. Email's most consequential assumption gets a disclaimer and nothing else. If re-engagement send rate is 10% instead of 30%, the entire email infrastructure sizing changes materially.

### 2. The Opt-Out Violation Framing Is Legally Incoherent

The document correctly states that TCPA, CAN-SPAM, and GDPR violations are "each independently actionable," then presents this as a binary architectural choice requiring sign-off. But the sign-off framing implies that if legal and product choose the cache-staleness architecture, the 180–900 daily violations become an accepted operating condition. TCPA statutory damages are $500–$1,500 per violation. At 180 violations/day, that's a potential $32.8M–$98.4M annual exposure. No sign-off process described in this document has the authority to accept that. The document treats a legal compliance failure as a product decision.

### 3. The Viral Spike Model Acknowledges It's Wrong and Proceeds Anyway

The document states the 8%/5min scenario produces a 3+ hour delay and that "the planning basis spike model is therefore not conservative." It then explicitly declines to size for the more realistic worst case and instead defers to production monitoring starting Month 2. This means the system launches knowing its spike handling is inadequate for plausible real-world events, with no mitigation other than hoping the bad scenario doesn't happen in the first two months.

### 4. E2 Owns Contract Negotiation for a System E1 Is Responsible For

E2 is assigned ownership of the SendGrid enterprise contract negotiation. If that contract fails, E1 is required to present the tradeoff to stakeholders within 48 hours. The person accountable for the fallback consequence is not the person responsible for preventing it. This is a standard accountability gap that will cause the 48-hour window to be missed or contested.

### 5. The Document Is Incomplete and Was Published Anyway

Section 1.1 ends mid-sentence: "Peak arrival rate ≥ 2,500/sec sustained over 3" — the threshold condition is not finished. This is a document that requires "explicit sign-off before this design is finalized" on five items, and it was distributed in an incomplete state. The calibration checkpoint that is described as "the mechanism for detecting trajectory toward sustained overload" is itself cut off before defining the response to the trigger condition.

### 6. Default C Is Structurally Unavailable But Still Listed

The escalation default section states that Default C "requires a specific person named before finalization" and that without a named person "it does not appear as a selectable option." Yet it appears in the document as a described option. Stakeholders reading this will treat it as available. The document cannot simultaneously present an option and declare it non-selectable — one of those statements will be ignored, and experience suggests it will be the disclaimer.

### 7. The Self-Hosted Email Fallback Scope Is Internally Inconsistent

The document estimates 6–8 engineer-weeks for the self-hosted path and notes this "consumes roughly 2 months of one engineer's capacity." With 4 engineers over 6 months, that is 1/12 of total team capacity — but the document also says this is "possible only if another planned workstream slips" without identifying which workstream or what that slip costs. The self-hosted path is presented as a real, scoped option when it is actually an unscoped contingency that could consume a material fraction of the team's remaining runway.

### 8. The Broadcast Cap Has No Enforcement Backstop

The 100K recipient hard cap is "enforced at the API validation layer." The document names a product owner as the "decision gate owner" for exceptions, but states that without a named owner, the cap is policy with no exceptions. There is no description of what happens when the API validation layer is bypassed — direct database writes, internal tooling, or a future admin interface. A cap enforced only at one API layer is not a hard cap.

### 9. The International Compliance Risk Is Flagged and Abandoned

The document correctly identifies GDPR, PDPA, and LGPD as potentially requiring regional data residency, then explicitly declares this "out of scope" while calling it "a prerequisite for compliance in those regions." Flagging a prerequisite as out of scope does not defer the risk — it defers the work while the risk accumulates. If the app has EU users on launch day, the US-only architecture may be non-compliant on launch day.

### 10. The 15 Notifications/User/Day Figure Has No Derivation

The combined volume of 37.5M push/in-app notifications is derived from 2.5M DAU at 15 notifications/user/day. That figure appears without any breakdown, benchmark, or justification. Unlike email (which is decomposed into activity and re-engagement components with explicit opt-in rate assumptions), push volume is simply asserted. For the highest-volume channel, this is the weakest derivation in the document.