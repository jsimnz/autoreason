# Pulse — YC Seed Pitch (Revised)

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. Nobody wants to build it, but everyone does.

We're Pulse. We built the notification layer engineering teams shouldn't have to build themselves.

The problem isn't that solutions don't exist. AWS SNS is powerful but brutally low-level — you're still stitching channels together yourself. OneSignal is built for marketers, not developers. So most teams roll their own, which means months of engineering time and a reliability gap they don't discover until it's hurting retention.

Let me be precise about reliability, because I expect skepticism. Push notification delivery confirmation at the device level isn't something Apple or Google expose cleanly. What we measure — and what we mean by 99.97% versus the industry average of 94% — is gateway acceptance plus confirmed downstream delivery where the platform returns it, combined with active failure detection and re-routing for the remainder. The 94% baseline is from published industry benchmarks on gateway-level failures alone. We're not claiming to have solved a physics problem. We're claiming that our retry logic, fallback routing, and carrier relationships — built by engineers who ran these systems at Twilio and AWS SNS — meaningfully reduce the failure rate within what's actually measurable. At a million users, the difference is tens of thousands of dropped notifications per send. For transactional alerts, that matters.

On the team: two of us ran notification infrastructure at Twilio and AWS SNS respectively. We're not claiming we have better carrier relationships than Twilio at scale. We're claiming we've built the right abstractions for the developer segment Twilio doesn't prioritize — companies between one and fifty million MAU, past the point of building it themselves, before they'd staff a dedicated platform team. Twilio's sales motion starts above where we operate.

Eight months in: 180 million notifications a month, 47 paying customers, $38K MRR. Average paid customer is around $800 MRR, which is SMB, and we're not pretending otherwise. Our current motion is developer-led adoption — engineers instrument for free, convert when they scale. That produces good retention and natural expansion, but it's not enterprise sales. We know those are different motions with different support burdens. We're not trying to run both simultaneously. The SOC2 certification we're pursuing unlocks three stalled enterprise prospects, and yes — at our MRR, those deals are material. That's exactly why it's the first use of proceeds, not an afterthought.

On the raise: $2M, targeting 18 months of runway. We're aware that two senior infrastructure engineers and a growth head is an aggressive hire plan against current revenue. Our burn is low — we're not paying ourselves market rate. That's a short-term choice, not a permanent one, and this raise corrects it.

We're asking for $2M. The notification layer is genuinely hard to build well, and the current options force a bad choice. We're the right abstraction, at the right reliability level, for the companies that need it most.