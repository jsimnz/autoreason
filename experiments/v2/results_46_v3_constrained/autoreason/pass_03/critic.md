Here are the real problems I see:

**The reliability claim is suspicious.**
99.97% vs 94% industry average is an extraordinary claim. "Confirmed receipt" for push notifications is not a well-defined standard — iOS and Android don't reliably return delivery confirmation at the device level, only acceptance at the platform gateway. If they're measuring gateway acceptance and calling it "confirmed receipt," the comparison is misleading. If they've actually solved device-level confirmation, that's a technically novel claim that needs far more explanation than one sentence.

**The unit economics don't support the raise.**
$38K MRR across 47 paying customers at ~$800 average. They're raising $2M, hiring two senior infrastructure engineers plus a growth head, pursuing SOC2, and claiming 18 months of runway. Senior infrastructure engineers in this market cost $200-300K+ each. The math is tight to the point of being implausible unless current burn is very low, which would suggest the team is underpaid or the company is operating on fumes.

**The competitive moat is asserted, not demonstrated.**
"Active carrier relationship management" and "real-time fallback routing" are described as differentiators, but these are known techniques. Twilio, Vonage, and others do this at massive scale. The claim that two former Twilio/AWS engineers can maintain carrier relationships that produce meaningfully better outcomes than Twilio itself is not argued — it's assumed.

**The TAM framing is weak.**
"8,000 companies between 1M and 50M MAU" is a ceiling, not a market size. It doesn't address pricing power, sales cycle length, churn risk as companies exit that band, or the fact that many of those companies already have a solution in place and switching costs are real.

**The SOC2 admission cuts both ways.**
Framing the SOC2 gap as transparency is smart, but three enterprise prospects currently blocked means there's pipeline stalled right now. For a company at $38K MRR, losing even one of those deals is material. The pitch treats this as a minor operational item when it may be the most important near-term revenue event.

**Developer-led growth at this price point is a structural tension.**
The average paid customer at $800 MRR is not an enterprise account. Developer-led adoption typically produces high volume, low ACV customers. The pitch gestures at enterprise (SOC2, waiting prospects) while describing a motion that produces SMB economics. These are different sales, different contracts, different support burdens, and different retention profiles. The pitch doesn't reconcile them.

**The founding team risk is acknowledged but minimized.**
Three infrastructure engineers is named as a distribution risk, and the response is "we'll hire a growth head." But the deeper problem is that notification infrastructure is increasingly commoditized by the cloud providers themselves. AWS, GCP, and Azure are all expanding their messaging primitives. The team's answer to competitive moat is reliability and developer experience — both of which require ongoing product and go-to-market judgment that the current team hasn't demonstrated.