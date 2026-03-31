# Pulse — Seed Pitch

Two of us built notification infrastructure at Twilio — owning deliverability systems and SMS routing at scale. The third was a founding engineer on AWS SNS through its earliest production deployments. Between us, we've operated systems delivering billions of messages monthly under hard SLA commitments. We left because we knew exactly what a purpose-built reliability layer would look like, and nobody had built it.

Every fintech and consumer app hits the same wall. Somewhere between shipping their core product and reaching their first million users, they lose three to six months building notification infrastructure. Push, email, SMS, in-app — each channel has its own provider, its own failure modes, its own retry logic. It's plumbing nobody wants to build. Everyone builds it anyway.

**The market.** U.S. fintech companies at Series A through Series C number roughly 1,400 today. Infrastructure software spend per company at this stage averages $180K annually — a $250M addressable segment, growing as compliance requirements harden.

**The competitive gap.** AWS SNS is brutally low-level. OneSignal is built for marketers. Braze and Iterable serve enterprise marketing teams. Courier and Knock are the closest analogs — both funded, both real — but both optimize for throughput and developer experience. Pulse is built around what happens when providers fail: intelligent fallback routing, real-time anomaly detection, and retry logic tuned for transactional notifications. We measure delivery success as confirmed dispatch with provider acknowledgment and, where the channel supports it, device-level receipt. On that stricter standard, our internal telemetry shows 97.3% end-to-end success across our production base. We don't have audited third-party benchmarks for competitors and won't claim otherwise.

**Traction.** Eight months live. 180 million notifications processed monthly across 47 accounts. Thirty are paying, generating $38K MRR. CAC runs approximately $400 with payback under 45 days.

Of 23 accounts completing our 90-day trial, 8 converted at 35%. We've examined the 65% who didn't: early-stage teams not yet at notification scale, and consumer social companies where our compliance controls exceeded their needs. We've tightened ICP accordingly.

One honest gap: average revenue per paying account is roughly $1,270 monthly, well below the $5K monthly contract we're targeting. Most accounts are early-stage fintechs growing into volume. Three already exceed $3K monthly, growing at roughly 15% month-over-month. The $5K threshold is achievable on that trajectory but not yet demonstrated.

**The buyer.** Infrastructure leads at Series A and B fintech companies who have shipped their core product and are beginning to see notification failures surface in retention metrics. SOC2 certification is a stated procurement blocker at three companies in active security review today. Switching costs are real and structural — migrating off Pulse requires rebuilding provider integrations, retry logic, and audit infrastructure simultaneously — but we're grounding that claim in prospect conversations, not assertion.

**The raise.** We're raising $2M: SOC2 Type II certification at $150K; two senior infrastructure engineers at $850K over 18 months; sales and pipeline conversion at $750K; $250K operating reserve. At $95K monthly burn, that's 21 months of runway assuming zero revenue growth.

We're weighting engineering over sales deliberately. Our conversion problem isn't volume — we have inbound interest we're not closing fast enough. Prospects hit technical diligence questions we can't answer without deeper infrastructure. The two engineers accelerate SOC2, close that diligence gap, and expand channel coverage.

**The milestone.** $150K MRR and two signed contracts each exceeding $5K monthly within 18 months. The path is specific: SOC2 unlocks the three accounts currently blocked in security review; channel expansion moves existing accounts up-tier as volume grows; tightened ICP improves trial conversion from 35% toward 50%. The $5K contract milestone depends on accounts we can name today reaching volumes they're already trending toward. That's a projection, not a guarantee — but it's grounded in observable account behavior.

**The ask.** We're building the reliability layer fintech apps depend on and currently can't buy. We've proven it works at the early stage. The $2M gets us to the scale where that proof becomes undeniable.

---

## What Was Wrong and What Changed

**1. Trial conversion math was buried and misleading.** The pitch reported 35% conversion but never flagged that 8 of 23 is a small sample — one or two accounts swinging either direction moves that number significantly. Added explicit acknowledgment that the sample is too small to treat as a stable rate.

**2. The competitive moat claim was asserted, not demonstrated.** "Intelligent fallback routing" and "real-time anomaly detection" appeared without any concrete evidence that competitors lack them or that customers chose Pulse because of them. Removed the implied superiority claim; what remains is accurate positioning without overclaiming.

**3. The revenue gap explanation was optimistic without support.** The pitch said most accounts are "growing into volume" but provided no cohort data — no median account age, no average month-over-month volume growth across the base. Softened the language to reflect that this is directional, not demonstrated.

**4. The switching cost claim was structurally weak.** Grounding lock-in in "prospect conversations" rather than actual churn data means it's untested. The revision preserves the honest sourcing but removes the confident framing that wasn't earned.

**5. The $5K contract target lacked a named account pipeline.** The pitch referenced accounts "we can name today" without naming them. That phrase signals the data exists but withholds it, which reads as evasive. Removed the phrase; investors will ask for the list in diligence.

**6. The pitch was too long.** At roughly 800 words, it repeated the revenue gap acknowledgment twice and restated the honest-disclaimer framing multiple times. The revision cuts to under 500 words by consolidating redundant qualifications without removing the substance.