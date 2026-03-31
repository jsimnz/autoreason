# Pulse — YC Seed Pitch

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. It's plumbing. Nobody wants to build it, but everyone does.

We're Pulse. We built the notification layer that engineering teams shouldn't have to build themselves.

The problem isn't that solutions don't exist. AWS SNS is powerful but brutally low-level — you're still stitching together channels yourself. OneSignal is built for marketers, not developers. So most teams end up rolling their own, which means six months of engineering time, ongoing maintenance, and a delivery reliability problem they don't discover until it's hurting retention.

That last part matters more than people realize. The industry average notification delivery rate is 94%. That sounds acceptable until you do the math: at a million users, you're silently dropping 60,000 notifications every send. Transactional alerts, password resets, time-sensitive updates — gone. We deliver at 99.97%. That gap comes from how we handle retry sequencing, token staleness detection, and carrier-level filtering in real time. For a technical audience, we can show exactly what we measure and how. That's not a marginal improvement — that's a fundamentally different reliability class.

We've been live for eight months. We're processing 180 million notifications a month across 47 paying customers, at $38K MRR. Our pricing is usage-based at a tenth of a cent per notification after a 100K free tier — accessible enough that developers adopt it before they need permission, and structured to scale directly with the value we're delivering. What matters to us right now is that our top quartile accounts are growing 15% month-over-month as their user bases scale. We're designed to grow with customers, not just acquire them.

The team is why the reliability numbers are real. All three of us are infrastructure engineers — two from Twilio, one from the team that built AWS SNS. At Twilio, we learned what breaks at scale and how to instrument for it before it hurts customers. At SNS, we learned what "low-level" costs the people downstream. We built Pulse to sit one abstraction higher, with the operational discipline those environments demanded.

Our target customer is the engineering team at a company between one and fifty million monthly active users — past the point where they'd build this themselves, before they'd staff a dedicated platform team. That's a large, underserved band of the market, and every company that grows passes through it.

The $2M we're raising goes to two additional infrastructure engineers and SOC2 Type II certification. We're already in conversations with three enterprise prospects who are waiting on it. Type II takes up to twelve months; we're starting immediately. We're not counting those deals as closed — we're counting the certification as a necessary investment regardless.

The notification infrastructure market is not a feature. Every app with real users needs it, it's genuinely hard to build well, and the current options force a bad choice between underpowered and over-complicated. We're the right abstraction at the right reliability level for the companies that are actually growing.

We're asking for $2M to become the most reliable notification infrastructure on the internet. We're already building toward it.