# Pulse — YC Seed Pitch

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. Nobody wants to build it. Everyone does anyway.

We're Pulse. We built the notification layer engineering teams shouldn't have to build themselves.

The competitive landscape is real. AWS SNS is powerful but low-level — you're still stitching channels together yourself. OneSignal is built for marketers. Courier, Knock, and Novu are workflow-first — their architecture reflects their original customer: a product manager configuring a template. Ours reflects an engineer instrumenting a distributed system. Customers switching from Knock have told us directly they hit a ceiling when they needed programmatic control over delivery logic. That's the specific gap we fill, and we can show you the migration tickets.

On delivery reliability: we measure gateway acceptance plus confirmed downstream delivery where carriers return confirmation signals. We won't claim omniscient end-to-end visibility — nobody has that across all platforms. What we can say precisely is that our retry architecture was built by engineers who ran these systems at Twilio and AWS SNS. The result is a meaningfully lower confirmed failure rate than customers see when they migrate. We'll show you the raw migration data and let you assess it. At a million users, the gap between our numbers and the industry average represents 60,000 dropped notifications per send. For transactional alerts, that's not a marginal difference. That's a different reliability class.

Eight months in: 47 paying customers, $38K MRR, 180 million notifications monthly. We'll say plainly what that means: distribution is broken. For a market where roughly 8,000 US companies sit in our target band, 47 customers after eight months means we were thinking like infrastructure engineers, not like an infrastructure vendor — assuming product quality would pull customers in. It doesn't, at this stage, without someone whose job is to go get them. Our first twelve customers, now six-plus months in, have expanded spend as their user bases grew. None have churned. Small sample, but the expansion model is working where we can observe it.

Three enterprise deals are currently stalled on SOC2. That's on us — we should have started it at month two. We got that wrong and are correcting it.

We're raising $2M with deliberate sequencing: SOC2 first, because it closes known revenue and is a prerequisite for the customer segment we're actually targeting. Then one enterprise sales hire — not a growth generalist, someone who has sold developer infrastructure before, because one person with the right motion is meaningfully different from one without it. Then one senior infrastructure engineer. Our Series A thesis isn't a vague promise — it's get into active evaluation at ten enterprise accounts, close two, and show expansion from the current cohort. That's a bar we can either hit or not, and 18 months is enough time to find out honestly.

The companies that grow past our band don't rip out infrastructure that works. That's the switching cost reality of deeply instrumented backend systems. We're asking for $2M to become the default.