# Pulse — YC Seed Pitch (Revised)

---

Every engineering team building a consumer app hits the same wall. Somewhere between shipping their core product and scaling to their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. Nobody wants to build it. Everyone does anyway.

We're Pulse. We built the notification layer engineering teams shouldn't have to build themselves.

The real competitive situation for our prospects isn't a single alternative — it's a stitched stack. AWS SNS plus SES plus Pinpoint plus a third-party SMS provider. That combination works until it doesn't: when one leg degrades, there's no coordinated fallback, no unified delivery signal, and debugging spans four dashboards. OneSignal solves a different problem — campaign delivery for marketers, not transactional reliability for engineers. The custom build is what teams do when neither fits. That's still the most common answer, which is why the problem is worth solving.

Marcus and Jen spent six years at Twilio building carrier retry logic and four years at AWS SNS running delivery pipelines at scale. We're not claiming an architectural moat — we're saying our retry and fallback logic was designed first, not bolted on, because the people who built it spent a decade on the failure modes specifically. Whether that's a durable advantage is something you can assess once you talk to our customers.

On delivery reliability: we measure gateway acceptance plus confirmed downstream delivery where carriers return confirmation signals. That is not the same as end-user receipt — no provider can claim that across all platforms, and we won't. What we can say precisely: our confirmed failure rate is 0.03%. The industry figure of 6% aggregates differently and the comparison isn't apples-to-apples. We'll show you raw methodology and let you assess it. What we don't hedge: customers migrating to us report fewer missed transactional alerts, and we can show you specific before-and-after data from three of them.

Eight months in: 47 paying customers, $38K MRR, 180 million notifications monthly. We'll be direct about the shape of that. Volume is concentrated — our top five customers account for roughly 60% of notifications, which is a concentration risk we're aware of. Average revenue per customer is $808, which is low, and reflects a real failure: we built like infrastructure engineers and assumed product quality would pull customers in. It doesn't, without someone whose job is to go get them. What the data does show: our first twelve customers have expanded spend as their user bases grew, none have churned, and the usage-based model means revenue scales with their growth. That's eight months of early signal on the expansion logic, not proof of a moat.

Three enterprise deals are stalled on SOC2. That's not just a certification gap — it means we've been running a sales motion misaligned with our target segment for eight months. We should have gotten SOC2 earlier. The ask accounts for that correction first.

We're raising $2M. Sequencing: SOC2 immediately, which closes known revenue and is table stakes for the segment we're targeting. Then one senior infrastructure engineer. Then one enterprise sales hire — specifically someone with a track record selling developer infrastructure, not a growth generalist, because the motion for selling to engineering teams is different and we've already seen what happens without that background. One of us will lead sales directly until we have evidence we can close enterprise deals; we're not outsourcing that validation to a hire.

Our Series A bar: $300K MRR, two enterprise contracts above $5K monthly. Getting there from $38K in 18 months requires both expansion from the current cohort and new logo growth — we're not projecting that expansion alone carries it. The path runs through closing the three stalled enterprise deals post-SOC2, converting the pipeline we have, and building the sales motion we haven't had. That's an honest account of what has to go right.

We're asking for $2M to find out whether we can become the default.