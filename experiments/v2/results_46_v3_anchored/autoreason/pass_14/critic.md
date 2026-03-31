Here are the real problems with this proposal:

**1. The DAU/MAU ratio is used inconsistently for worker sizing.**
The document states worker sizing uses 38.5M/day (35% DAU/MAU × 11/DAU) as the high-case planning input, but the spike model uses 27.5M/day (25% DAU/MAU × 11/DAU) as its planning basis. The spike backlog and drain time calculations are therefore understated relative to the worker sizing scenario. The numbers in the same document are not internally consistent.

**2. The 90% concentration in 4 hours is applied to SMS without justification.**
SMS in this app is primarily OTP and authentication. OTP traffic does not follow social engagement peaks — it follows login events, which are distributed differently from like/comment activity. Applying the same concentration model to SMS as to social push notifications is not justified and could meaningfully mis-size the SMS queue and its dedicated workers.

**3. The spike model assumes spike traffic is entirely social volume, but never states this.**
The backlog calculation implicitly assumes the 5% spike is all low-priority social notifications. If a viral moment also triggers a surge in direct messages or account security alerts — which is plausible if the viral event involves account compromise or a controversial interaction — the isolation argument for high-priority queues breaks down. The model does not address mixed-priority spikes.

**4. The email peak concentration assumption is never validated against actual send behavior.**
The 90%/4-hour window is described as a "US-centric planning basis," but re-engagement emails are typically scheduled sends, not event-driven. Scheduled sends are deliberately spread or batched by the sending system, which can either compress or flatten the concentration window depending on how the scheduler works. The document applies the same concentration model to both event-driven push and scheduled email without acknowledging this distinction.

**5. The "unmodeled factor" of graph densification is acknowledged and then ignored in all subsequent calculations.**
The document explicitly states that as the social graph densifies, per-user notification rates will increase without DAU growth, and that this is a known unmodeled factor. It then sets a reassessment trigger at 13/DAU/day before Month 4. But the worker sizing uses 11/DAU/day with 10% headroom — meaning the headroom is entirely consumed before the reassessment trigger fires. There is no buffer between the point where reassessment is triggered and the point where the system is already at capacity.

**6. The broadcast cap enforcement is listed at three layers but the document is cut off before Section 6 is described.**
The executive summary states the hard cap is enforced at the API layer, the worker layer, and the database write layer, and that Section 6 describes this. The document ends before Section 6. The three-layer enforcement claim is unverifiable within this document, and the interaction between layers — specifically what happens when a job passes the API layer check but fails the database write layer check — is never specified.

**7. The compliance framing for opt-out is stated with legal certainty the document cannot support.**
The document states that the cache-staleness path "is not available for selection regardless of stakeholder preference" and that this creates "legally non-negotiable" exposure. TCPA, CAN-SPAM, and GDPR compliance for cache staleness windows is fact-specific and jurisdiction-specific. Stating this as an absolute in a design document without citing a legal opinion creates a false sense of settled law and could itself create liability if the framing is wrong.

**8. The self-hosted email fallback engineering cost estimate has no basis.**
"6–8 engineer-weeks" for deliverability tuning, bounce handling, DKIM/SPF/DMARC, monitoring, and IP warm-up is presented as a concrete estimate. IP warm-up alone for a volume of 1.75–4.75M emails/day typically takes 4–8 weeks of calendar time regardless of engineer effort, because ISP reputation is built incrementally. The estimate conflates engineer-weeks with calendar time and does not address the calendar constraint, which is the binding one.

**9. Default C for capacity overruns is described as "not a selectable option" but is still presented as an option.**
The executive summary lists three defaults and explains that Default C requires a named person before it can be selected. This means Default C is effectively on the table and will attract stakeholder attention as a way to defer the decision. Presenting it at all while calling it unselectable is incoherent process design that will generate confusion in sign-off conversations.

**10. The Month 2 calibration checkpoint triggers reassessment but specifies no consequence.**
If observed notifications/DAU/day exceeds 13 before Month 4, the document says this "triggers a reassessment." It does not specify who conducts the reassessment, what decisions it can produce, what the timeline is, or what happens to the Month 4 and Month 5 milestones while the reassessment is underway. The trigger exists but the process it initiates does not.