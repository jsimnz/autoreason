# Pulse — YC Seed Pitch

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. Nobody wants to build it, but everyone does.

We're Pulse. We built the notification layer engineering teams shouldn't have to build themselves.

The problem isn't that solutions don't exist. AWS SNS is powerful but brutally low-level — you're still stitching channels together yourself. OneSignal is built for marketers, not developers. So most teams roll their own, which means months of engineering time and a reliability gap they don't discover until it's already hurting retention.

Let me be precise about reliability, because I expect skepticism. What we mean by 99.97% versus the industry average of 94% is gateway acceptance plus confirmed downstream delivery where platforms return it, combined with active failure detection and re-routing for the remainder. We're not claiming to have solved a physics problem. We're claiming that our retry logic, fallback routing, and carrier relationships — built by engineers who ran these systems at Twilio and AWS SNS — meaningfully reduce the failure rate within what's actually measurable. At a million users, the difference between 94% and 99.97% is 60,000 dropped notifications per send. For transactional alerts and time-sensitive updates, that's not a marginal gap. That's a different reliability class entirely.

Eight months in: 180 million notifications a month, 47 paying customers, $38K MRR. Our adoption model is developer-led — engineers instrument for free, convert when they scale. Paid customers average roughly $800 MRR, and we see consistent expansion as their user bases grow. That's SMB, and we're not pretending otherwise. The free tier is a sales motion, not a subsidy problem.

Our target customer is the engineering team at a company between one and fifty million monthly active users — past the point where they'd build this themselves, before they'd staff a dedicated platform team. There are approximately 8,000 companies in that range in the US alone. Every company that grows passes through this band.

We're raising $2M. The allocation: two senior infrastructure engineers, SOC2 Type II certification, and 18 months of runway at current burn. We should have pursued SOC2 earlier — we didn't, and three enterprise prospects are currently stalled on it. We're not hiding that; we're fixing it in the next 90 days. Those deals are material at our current MRR, which is exactly why certification is the first use of proceeds, not an afterthought.

One more thing worth saying directly: we're three infrastructure engineers, and we know that's a distribution risk. The first hire after this round is a head of growth, not another engineer.

Notification infrastructure isn't a feature. Every app with real users needs it, it's genuinely hard to build well, and the current options force a bad choice between underpowered and overcomplicated. We're the right abstraction, at the right reliability level, built by the right team.

We're asking for $2M.