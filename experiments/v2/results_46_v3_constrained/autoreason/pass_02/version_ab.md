# Pulse — YC Seed Pitch

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. It's plumbing. Nobody wants to build it, but everyone does.

We're Pulse. We built the notification layer that engineering teams shouldn't have to build themselves.

The problem isn't that solutions don't exist. AWS SNS is powerful but brutally low-level — you're still stitching together channels yourself. OneSignal is built for marketers, not developers. So most teams end up rolling their own, which means months of engineering time and a reliability problem they don't discover until it's already hurting retention.

Delivery reliability is where we've focused our engineering. Across push and SMS — the channels where carrier filtering and device-level failures dominate — we deliver at 99.97% versus an industry average of 94%, measured the same way: confirmed receipt, not dispatch. We achieve this through active carrier relationship management, real-time fallback routing, and retry logic built by engineers who previously operated these systems at Twilio and AWS SNS. At a million users, the difference between 94% and 99.97% is 60,000 dropped notifications per send. For transactional alerts and time-sensitive updates, that's not a marginal gap. That's a different reliability class entirely.

Eight months in, we're processing 180 million notifications a month across 47 paying customers at $38K MRR. A portion of that volume is in the free tier — our adoption model is developer-led, engineers instrument first and convert when they scale. Paid customers average roughly $800 MRR, and we see consistent expansion as their user bases grow. The free tier is a sales motion, not a subsidy problem.

Our target customer is the engineering team at a company between one and fifty million monthly active users — past the point where they'd build this themselves the first time, before they'd staff a dedicated platform team. There are approximately 8,000 companies in that range in the US alone. Every company that grows passes through this band.

We're raising $2M. The allocation: two senior infrastructure engineers, SOC2 Type II certification, and 18 months of operating runway at current burn. We should have pursued SOC2 earlier. We didn't, and three enterprise prospects are currently waiting on it. We're not hiding that — we're fixing it in the next 90 days.

One more thing worth saying directly: we're three infrastructure engineers, and we know that's a distribution risk. The first hire after this round is a head of growth, not another engineer.

Notification infrastructure isn't a feature. Every app with real users needs it, it's genuinely hard to build well, and the current options force a bad choice between underpowered and over-complicated. We're the right abstraction, at the right reliability level, built by the right team.

We're asking for $2M. We'd like Pulse to be the notification layer the internet runs on.