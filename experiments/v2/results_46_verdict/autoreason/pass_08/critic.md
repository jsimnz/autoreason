## Real Problems with This Proposal

### 1. The Coverage Gate Structure Creates Impossible Dependencies

The proposal requires Gate 1 (2 weeks before channel launch), Gate 2 (1 week before), and Gate 3 (first week of operation) — a minimum 3-week span before a channel is considered covered. But Month 1 delivers in-app notifications live, with E3 completing Gates 1–2 for in-app. This means Gate 1 must begin in week 2 of Month 1 at the latest, while E3 is simultaneously building the preference API skeleton and the in-app delivery system. The timeline doesn't have slack for a failed Gate 2 (which triggers a runbook update and second attempt) before Month 1 ends. A single gate failure collapses the entire Month 1 deliverable.

### 2. E1's Role Is Structurally Incoherent

E1 is defined as having no channel primary ownership — explicitly to make them the "natural backup for push." But E1 is also the owner of core pipeline and queue infrastructure, which is the most critical and complex component in the system. Then in Month 2, E1 spends weeks going through coverage gates for push. An engineer doing Gate 3 solo on-call for push while simultaneously being the primary owner of the production queue infrastructure during a period when push is newly launching is a serious operational conflict. If an infrastructure incident occurs during E1's Gate 3 solo push on-call, who handles infrastructure?

### 3. The SMS Budget Comparison Is Internally Inconsistent

The proposal states SMS is restricted to auth/security at ~50K/day (~$375/day, ~$11K/month), contrasted against the "existential" 1M/day cost of $225K/month. But 50K/day × $0.0075 = $375/day × 30 days = $11,250/month, not ~$11K/month as stated. More importantly, the proposal later introduces P0 push notifications routing to SMS fallback (Section 5.3, referenced but not included). If P0 events can trigger SMS fallback, the SMS volume is no longer bounded by the auth/security allowlist alone. The budget analysis doesn't account for this.

### 4. The FCM Mock in Test 1 Invalidates the Test's Stated Purpose

The proposal explicitly states Test 1 validates queue sizing, worker pool sizing, and priority logic at 6,375/sec — but FCM is mocked. Worker pool sizing for push workers is directly dependent on FCM response latency. A mocked FCM with sub-millisecond response times will show workers handling far more throughput than they would with real FCM latency. The worker pool sizing derived from Test 1 is therefore not valid for production conditions. The proposal acknowledges this limitation but presents it as acceptable honesty rather than a gap in the validation strategy.

### 5. The Coverage Partner Spot-Check Standard Is Weaker Than Initial Certification

Gate 2 requires the coverage partner to handle a simulated incident without contacting the primary owner, with a failed simulation being a blocking condition. The Month 4 and Month 6 spot-checks are described as re-executing the "Gate 2 simulation" but a failed spot-check is only treated as a "P2 operational issue" — not a channel freeze or escalation. A coverage partner who fails the spot-check remains the designated coverage partner while the P2 is worked. This is a weaker standard than initial certification despite the system having grown more complex by month 4.

### 6. The Opt-Out Model's "Permanent Audience Damage" Framing Is Unfalsifiable

The proposal criticizes multi-week statistical baselines for "accepting permanent audience damage as an interim condition" and claims its approach avoids this. But the day-one absolute limits (3 push/day, 1/hour, 1 per type/day) are asserted without any basis — they are not derived from research, comparable app benchmarks, or user research. If these limits are themselves too aggressive, the system will generate opt-outs from day one at the "safe" limits. There is no mechanism to discover this because the weekly 0.5% alert only fires at 35K opt-outs — a number that already represents meaningful permanent audience damage.

### 7. The Notification Type Taxonomy Is a Hard Launch Dependency With No Ownership

The proposal states the closed type taxonomy is a "hard prerequisite for month 1 launch" and must be defined as a closed enum in the schema. But no engineer is assigned to own the taxonomy, no time is allocated for it in Month 1's already-compressed schedule, and the process for adding types (two-engineer PR review + runbook entry) is defined without specifying who the two engineers must be. Given that all four engineers are fully allocated in Month 1, this prerequisite has no slack and no owner.

### 8. The Peak Throughput Model Double-Counts Concentration

The proposal calculates peak sustained throughput by taking 60% of daily volume over 4 hours, yielding ~2,125/sec. It then applies a 3× spike multiplier to get 6,375/sec. But the 60% concentration figure already represents a peak window — applying a 3× spike multiplier on top of an already-concentrated window means the design envelope assumes momentary spikes are 3× above an already-elevated baseline. There is no justification provided for why 3× is the right spike factor within a peak window rather than above the daily average. If the 3× is intended to capture spikes above the daily average (the conventional usage), the calculation is wrong. If it's intended to capture spikes within the peak window, the 3× factor needs empirical justification that isn't provided.

### 9. E4's Month 1 Scope Resolution Doesn't Actually Resolve the Conflict

The proposal addresses E4's workload conflict by separating weeks 1–2 (design/scaffolding) from weeks 3–4 (Gate 3 solo on-call). But E4's Gate 3 solo on-call in weeks 3–4 is for queue/in-app scope — not email/SMS. E4 is on-call for a system E3 primarily owns and E4 is secondarily covering. Meanwhile, the email/SMS scaffolding is paused. If an email/SMS design decision made in weeks 1–2 turns out to be wrong, E4 cannot revisit it during weeks 3–4 without violating the scope separation. The resolution defers the conflict rather than eliminating it.

### 10. The Document Ends Mid-Sentence

The proposal cuts off at the notification type taxonomy definition mid-sentence ("The enum is version-controlled... `social_interaction` (likes, comments, mentions), `follow_request`"). Section 5.3 is referenced multiple times (SMS fallback for P0 push) but never included. The coverage model references runbook processes for SMS in Month 3 that depend on SMS gate enforcement details described as being in Section 3.3, which is also absent. The document is incomplete in ways that affect load-bearing design decisions.