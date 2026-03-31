# Pulse — YC Seed Pitch

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. It's plumbing. Nobody wants to build it, but everyone does.

We're Pulse. We built the notification layer that engineering teams shouldn't have to build themselves.

The problem isn't that solutions don't exist. AWS SNS is powerful but brutally low-level — you're still stitching together channels yourself. OneSignal is built for marketers, not developers. So most teams end up rolling their own, which means six months of engineering time, ongoing maintenance, and a delivery reliability problem they don't discover until it's hurting retention.

That last part matters more than people realize. The industry average notification delivery rate is 94%. That sounds acceptable until you do the math: at a million users, you're silently dropping 60,000 notifications every send. Transactional alerts, password resets, time-sensitive updates — gone. We deliver at 99.97%. That's not a marginal improvement. That's a fundamentally different reliability class.

We've been live for eight months. We're processing 180 million notifications a month across 47 paying customers, with $38K in MRR. Our pricing is simple: usage-based at a tenth of a cent per notification after a 100K free tier. It's accessible enough that developers adopt it before they need permission, and it scales directly with the value we're delivering.

The team is the reason the reliability numbers are real. All three of us are infrastructure engineers — two came from Twilio, one from the team that built AWS SNS. We've collectively operated notification systems at a scale most startups will never reach. We built Pulse because we knew exactly what the right version looked like, and it didn't exist.

Our target customer is the engineering team at a company between one and fifty million monthly active users — past the point where they'd build this themselves the first time, but before they'd staff a dedicated platform team. That's a large, underserved band of the market, and every company that grows passes through it.

The $2M we're raising has two specific destinations: two additional engineers to accelerate the reliability and routing infrastructure, and SOC2 certification. That certification is the unlock for enterprise contracts. We're already in conversations with three companies that can't sign until we have it.

The notification infrastructure market is not a feature. Every app with real users needs it, it's genuinely hard to build well, and the current options force a bad choice between underpowered and over-complicated. We're the right abstraction at the right reliability level for the companies that are actually growing.

We're asking for $2M. We'd like Pulse to be the notification layer the internet runs on.