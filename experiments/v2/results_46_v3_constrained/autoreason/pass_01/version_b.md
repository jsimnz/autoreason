# Pulse — YC Seed Pitch (Revised)

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling toward their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. It's plumbing. Nobody wants to build it, but everyone does.

We're Pulse. We built the notification layer that engineering teams shouldn't have to build themselves.

The alternatives force a bad choice. AWS SNS is powerful but brutally low-level — you're still stitching together channels yourself. OneSignal is built for marketers. A new wave of developer-first tools like Courier and Knock are closer, but they've optimized for workflow orchestration rather than delivery reliability. That gap is where we live.

Delivery reliability is our technical core. The industry average for confirmed notification delivery — controlling for reachable devices with valid tokens — is around 94%. We're at 99.97% on that same basis. That gap comes from how we handle retry sequencing, token staleness detection, and carrier-level filtering in real time. For a transactional alert — a password reset, a payment confirmation, a time-sensitive update — that difference is the difference between a product that works and one that silently fails users. We can show any technical audience exactly what we measure and how.

We've been live for eight months. We're processing 180 million notifications a month across 47 paying customers, at $38K MRR. Average revenue per customer is around $800 — we know that means some accounts are near the free tier floor. What matters to us right now is that our top quartile accounts are growing 15% month-over-month as their user bases scale. We're designed to grow with customers, not just acquire them.

The team is why the reliability numbers are real. All three of us are infrastructure engineers — two from Twilio, one from the team that built AWS SNS. At Twilio, we learned what breaks at scale and how to instrument for it before it hurts customers. At SNS, we learned what "low-level" costs the people downstream. We built Pulse to sit one abstraction higher, with the operational discipline those environments demanded.

Our target customer is the engineering team at a company between one and fifty million monthly active users — past the point where they'd build this themselves, before they'd staff a dedicated platform team. That's a large band of the market, and every company that grows passes through it.

The $2M we're raising goes to two additional infrastructure engineers and SOC2 Type II certification. We're in conversations with three enterprise prospects who are waiting on it. Type II takes up to twelve months; we're starting immediately. We're not counting those deals as closed — we're counting the certification as a necessary investment regardless.

We're asking for $2M to become the most reliable notification infrastructure for growing engineering teams. That's a defensible, valuable position — and we're already building toward it.