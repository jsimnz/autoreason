# Pulse — YC Seed Pitch

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. Nobody wants to build it. Everyone does anyway.

We're Pulse. We built the notification layer engineering teams shouldn't have to build themselves.

The competitive landscape is real. AWS SNS is powerful but low-level — you're still stitching channels together yourself. OneSignal is built for marketers. Courier, Knock, and Novu are workflow-first — their architecture reflects their original customer: a product manager configuring a template. Ours reflects an engineer instrumenting a distributed system. The difference is in what we've actually built: a unified routing layer with per-carrier retry logic, real-time failure detection, and automatic fallback across providers. Not a feature on a roadmap — the thing that's been running 180 million notifications a month for eight months. That accumulated operational tuning takes time to replicate. That's the moat.

On delivery reliability: we measure gateway acceptance plus confirmed downstream delivery where carriers return confirmation signals. We don't claim omniscient end-to-end visibility — nobody has that across all platforms. What we can say precisely is that our retry architecture was built by engineers who ran these systems at Twilio and AWS SNS — two of us built Twilio's carrier fallback systems, one led SNS throughput scaling. The result is a meaningfully lower confirmed failure rate than customers see when they migrate from competitors. We'll show you the migration data. At a million users, the gap between our numbers and the industry average is 60,000 dropped notifications per send. For transactional alerts, that's not a marginal difference. That's a different reliability class.

Eight months in: 47 paying customers, $38K MRR, 180 million notifications monthly. We'll say plainly what that means: it's slow. For a market where roughly 8,000 US companies sit in our target band, 47 customers after eight months means our distribution is broken, not that the market is hard to find. We're infrastructure engineers who assumed product quality would pull customers in. It doesn't, at this stage, without someone whose job is to go get them. Our first twelve customers, now six-plus months in, have expanded spend as their user bases grew. None have churned. Small sample, but the expansion model is working where we can observe it.

Three enterprise deals are currently stalled on SOC2. That's on us — we should have started it at month two. We were thinking like engineers, not like an infrastructure vendor. That's a judgment call we got wrong and are correcting.

We're raising $2M. The sequencing is deliberate: SOC2 first, because it closes known revenue. Then one head of growth, because our distribution problem is structural. Then one senior infrastructure engineer to support enterprise scale. That's 18 months of runway and a Series A predicated on enterprise contract velocity — which we can demonstrate or we can't, and 18 months is enough time to find out honestly.

The companies that grow past our band don't rip out infrastructure that works. That's not optimism — that's the switching cost reality of deeply instrumented backend systems. We're asking for $2M to become the default.