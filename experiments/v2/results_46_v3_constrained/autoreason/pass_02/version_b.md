# Pulse — YC Seed Pitch (Revised)

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. It's plumbing. Nobody wants to build it, but everyone does.

We're Pulse. We built the notification layer that engineering teams shouldn't have to build themselves.

The problem isn't that solutions don't exist. AWS SNS is powerful but brutally low-level — you're still stitching together channels yourself. OneSignal is built for marketers. Courier and Knock are newer entrants we respect, but they're optimizing for workflow orchestration rather than delivery reliability at infrastructure scale. Most teams still end up rolling their own, which means months of engineering time and a reliability problem they don't discover until it's hurting retention.

Delivery reliability is where we've focused our engineering. Across SMS and push — the channels where carrier filtering and device-level failures dominate — we're delivering at 99.97% versus an industry average of 94% on those same channels, measured the same way: confirmed receipt, not dispatch. We achieve this through active carrier relationship management, real-time fallback routing, and retry logic built by engineers who previously operated these systems at Twilio and AWS SNS. At a million users, the difference between 94% and 99.97% is 60,000 dropped notifications per send. For transactional alerts and time-sensitive updates, that's not a marginal gap.

Eight months in, we're processing 180 million notifications a month across 47 paying customers at $38K MRR. We'll be direct about what those numbers mean together: a significant portion of our volume is in the free tier, because our adoption model is developer-led — engineers instrument first, convert when they scale. Our paid customers average roughly $800 MRR, and we see consistent expansion as their user bases grow. The free tier is a sales motion, not a subsidy problem.

Our target customer is the engineering team at a company between one and fifty million monthly active users. There are approximately 8,000 companies in that range in the US alone, and at our pricing, even 2% penetration at average contract value represents a $150M+ ARR opportunity. Every company that grows passes through this band.

We're raising $2M. The allocation: $800K for two senior infrastructure engineers, $100K for SOC2 Type II certification, and $1.1M in operating runway — 18 months at current burn. We should have pursued SOC2 earlier. We didn't, and three enterprise prospects are now waiting on it. We're not hiding that; we're fixing it in the next 90 days.

On team composition: we're three infrastructure engineers, and we know that's a distribution risk. The first hire after this round is a head of growth, not another engineer.

We're asking for $2M. Notification infrastructure isn't a feature — it's a layer every scaling app needs, and we're the right team to build it.