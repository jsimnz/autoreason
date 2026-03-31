# Pulse — YC Seed Pitch

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. Nobody wants to build it. Everyone does anyway.

We're Pulse. We built the notification layer engineering teams shouldn't have to build themselves.

The competitive landscape is real and we'll name it directly. AWS SNS is powerful but brutally low-level — you're still stitching channels together yourself. OneSignal is built for marketers. Courier, Knock, and Novu are workflow-first — visual editors and template systems optimized for product managers. We made a different bet: infrastructure-first, optimized for delivery reliability, built for the engineer who needs to instrument in an afternoon and never think about it again. That's a real distinction, and it's why teams choose us over tools that feel like they were designed for a marketing dashboard.

On reliability: our 99.97% delivery rate versus the industry's 94% average requires a caveat. We measure gateway acceptance plus confirmed downstream delivery where platforms return confirmation, with active failure detection and re-routing for the remainder. What we can say precisely: our retry logic, fallback routing, and carrier integrations — built by engineers who ran these systems at Twilio and AWS SNS — measurably reduce drop rates within what's observable. At a million users, the gap between 94% and 99.97% is 60,000 dropped notifications per send. For transactional alerts and time-sensitive updates, that's not a marginal difference. That's a different reliability class.

Eight months in: 180 million notifications delivered monthly, 47 paying customers, $38K MRR. Average customer is around $800 MRR. We won't oversell that — it's SMB-weighted, and it reflects that we're three infrastructure engineers who underinvested in distribution. The free tier converts developers who instrument early; expansion revenue follows their user growth. Our oldest cohorts are holding, which is the honest version of our churn story.

Three enterprise prospects are currently stalled on SOC2. That's a go-to-market failure, not a product failure, and it reflects exactly the blind spot we're correcting. We operated with infrastructure-engineer assumptions about what enterprise buyers need. That's changing.

We're raising $2M. First use of proceeds: SOC2 Type II, 90 days, closes those three deals. Second: one senior infrastructure engineer and one head of growth — because our distribution problem is structural, not incidental, and we're not hiring our way around it with another engineer. That gives us 18 months of runway and a Series A story built on enterprise contracts and a repeatable sales motion we don't currently have.

Our target customer is the engineering team at a company between one and fifty million MAU — past the point where they'd build this themselves, before they'd staff a dedicated platform team. There are roughly 8,000 such companies in the US alone, and every company that grows passes through this band. The customers who eventually staff platform teams don't rip out infrastructure that works.

Notification infrastructure isn't a feature. Every app with real users needs it. The current options are underpowered, overcomplicated, or workflow tools wearing infrastructure clothing. We're the right abstraction, at the right reliability level, with a clear-eyed view of what we've gotten wrong.

We're asking for $2M.