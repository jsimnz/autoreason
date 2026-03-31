# Pulse — YC Seed Pitch (Revised)

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. Nobody wants to build it. Everyone does anyway.

We're Pulse. We built the notification layer engineering teams shouldn't have to build themselves.

The competitive landscape is real and we'll name it directly: Courier, Knock, Novu, and others exist. Most are workflow-first — they're building visual editors and template systems for product managers. We made a different bet. We're infrastructure-first, optimized for delivery reliability at scale, built for the engineer who needs to instrument in an afternoon and never think about it again. That's a real distinction, and it's why teams at companies between one and fifty million MAU choose us over tools that feel like they were designed for a marketing dashboard.

On reliability: our 99.97% delivery rate versus the industry's 94% average requires a caveat. We measure gateway acceptance plus confirmed downstream delivery where platforms return confirmation, with active failure detection and re-routing for the remainder. The 94% figure uses varying methodologies across providers. What we can say precisely: our retry logic, fallback routing, and carrier integrations — built by engineers who ran notification infrastructure at Twilio and AWS SNS at the scale of hundreds of millions of daily messages — measurably reduce drop rates within what's observable. At a million users, that gap is 60,000 dropped notifications per send. For transactional alerts, that's a different reliability class.

Eight months in: 180 million notifications delivered monthly, 47 paying customers, $38K MRR. Average customer is around $800 MRR. We won't oversell that — it's SMB-weighted, and it reflects that we're three infrastructure engineers who underinvested in distribution. We know that. The free tier converts developers who instrument early; the expansion revenue follows their user growth. We don't have churn data we're proud enough to recite, which tells you we're early, not that we're hiding something catastrophic — our oldest cohorts are holding.

Three enterprise prospects are currently stalled on SOC2. That's a go-to-market failure, not a product failure, and it reflects exactly the blind spot we're correcting. We operated with infrastructure-engineer assumptions about what enterprise buyers need. That's changing.

We're raising $2M. First use of proceeds: SOC2 Type II, 90 days, closes those three deals. Second: one senior infrastructure engineer and one head of growth — because our distribution problem is structural, not incidental, and we're not hiring our way around it with another engineer. That gets us 18 months of runway and a Series A story built on enterprise contracts, lower churn visibility, and a repeatable sales motion we don't currently have.

The path through this band — one to fifty million MAU — does churn winners upward. We're not pretending otherwise. The replacement pipeline is every funded consumer and B2B app that grows. That's not a small number. And the customers who staff platform teams don't rip out infrastructure that works.

Notification infrastructure isn't a feature. Every app with real users needs it. The current options are underpowered, overcomplicated, or workflow tools wearing infrastructure clothing. We're the right abstraction, at the right reliability level, with a clear-eyed view of what we've gotten wrong.

We're asking for $2M.