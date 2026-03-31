Here are the real problems:

**Market and Competitive Positioning**

The claim that Knock and Novu's "core primitive is a workflow" while yours is a "delivery guarantee" is a product positioning assertion, not a verified structural difference. Knock in particular has documented retry and fallback logic. You're asking investors to take your word that competitors have a fundamental architectural ceiling, supported only by unnamed migration tickets.

**The Numbers Don't Hold Together**

$38K MRR across 47 customers averages $808/customer. You acknowledge this is low, but the proposed $2M raise against $38K MRR (~52x revenue multiple) is a significant ask with thin commercial validation. More specifically: 180 million notifications monthly across 47 customers is ~3.8M notifications per customer per month. If pricing is usage-based, either your pricing is extremely low per notification, or a small number of customers are generating most of the volume. The deck doesn't address this concentration risk.

**The 0.03% Failure Rate Claim**

You spend a paragraph carefully hedging what this number means, which is the right instinct, but it undermines the claim itself. "Gateway acceptance plus confirmed downstream delivery where carriers return signals" is not the same metric customers care about — end-user receipt. Competitors measure differently, so the comparison isn't meaningful, and sophisticated investors will notice you're preemptively disclaiming the metric while still leaning on it.

**The "60,000 fewer dropped notifications" Calculation**

This math assumes your improvement applies uniformly across a million-user app's entire send volume, which is almost never how notification systems work. Volume is spiky, channel-dependent, and varies by notification type. The number feels precise but is actually illustrative fiction.

**Team Concentration**

Two founders, both infrastructure-oriented by their own admission. You explicitly say you "built like infrastructure engineers and assumed product quality would pull customers in." The proposed fix is a sales hire, but sales hires at seed stage without founder-led sales validation frequently fail. There's no evidence in the deck that either founder can close enterprise deals, which is what the Series A bar requires.

**The SOC2 Problem Is Larger Than Stated**

Three enterprise deals stalled on SOC2 means you've been selling into enterprise without SOC2 for eight months. This isn't just a self-inflicted mistake — it suggests a sales motion that was misaligned with your stated target segment from the start. It also raises the question of what other compliance gaps exist that you haven't discovered yet because you haven't been asked.

**Series A Bar Is Internally Inconsistent**

You set $300K MRR as the target, roughly 8x growth in 18 months, while also saying expansion revenue from current cohort should exceed new logo revenue. If expansion is the primary revenue driver, reaching $300K MRR from $38K requires the current 47 customers to expand dramatically — but their average spend is already low, and you have no enterprise contracts yet. The math path to $300K MRR isn't shown, and the two criteria may work against each other.

**Switching Cost Argument Is Asserted, Not Demonstrated**

"Companies that grow past our band don't rip out backend infrastructure that works" is a general infrastructure truism, not evidence specific to Pulse. You have zero churn in 12 customers over 8 months — that's not switching cost data, that's early customer tenure. The retention moat claim is premature.

**The Competitor Dismissals Are Thin**

"AWS SNS is a single channel" ignores that most teams using SNS are using it alongside SES, Pinpoint, and third-party SMS — i.e., they've already solved the stitching problem even if imperfectly. Dismissing it as a single-channel product may be technically accurate but misrepresents the actual competitive situation for your prospects.