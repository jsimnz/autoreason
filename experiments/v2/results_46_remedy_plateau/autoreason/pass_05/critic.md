## Real Problems with This Proposal

### 1. The Document Is Mostly Self-Congratulation

The executive summary spends the majority of its words describing what the *previous version* got wrong and how *this version* fixed it. A design document's audience doesn't have the previous version. This reads as a revision history, not a design. The actual architectural decisions are buried under defensive framing.

### 2. The Correlation Claim Is Asserted, Not Demonstrated

The document states that DAU/MAU ratio and notifications/DAU are correlated variables and criticizes the previous version for treating them independently. But the table it produces — 8 notifs/DAU at 20% DAU/MAU, 40 at 65% — is itself just another set of asserted numbers. No mechanism is provided for *how* engagement drives notification rate, no empirical fit to the cited benchmarks, and no confidence interval. The criticism of the previous approach applies equally here.

### 3. The Public Benchmarks Are Misused

Twitter 2013 data and Facebook engineering posts are cited to calibrate estimates for a social app in 2024. These are different products, different engagement models, different notification philosophies, and over a decade old. The document acknowledges the estimates are "not derived from them precisely" — which raises the question of what work the citations are actually doing.

### 4. Peak Provisioning Math Is Internally Inconsistent

The document calculates sustained primetime rate as ~2,360/sec, then sets sustained capacity at 5,000/sec (~2× primetime). But it also says the burst target is 10,000/sec with workers processing at 5,000/sec. A 10-minute spike at 10,000/sec generates 3M backlogged messages, which clears in "~10 minutes of spike end." That arithmetic requires workers processing the spike *plus* the backlog simultaneously — but workers are capped at 5,000/sec. The clearance time is wrong.

### 5. The Queue Depth Math Doesn't Hold

The document claims Redis sorted set operations at 5,000/sec are "well within" a single r6g.xlarge citing ">100K ops/sec for simple sorted set operations." Sorted set operations (ZADD, ZRANGEBYSCORE, ZREM) are O(log N), not O(1). At 51M messages/day with retention, the sorted set grows large. The 100K ops/sec figure applies to simple GET/SET. This is a meaningful difference at scale.

### 6. The Lua Script Has a Logical Error

The TTL is set only on `count == 1` to avoid "resetting TTL on subsequent calls." But if the key expires mid-day due to a TTL calculation error, the next INCR resets the count to 1 and sets a new TTL — silently restarting the cap. The script's own validation logic (checking TTL range) runs *after* INCR has already modified state. The key is incremented before the TTL is validated. If TTL is invalid, the count has already changed.

### 7. The "cap+5" Overshoot Bound Is Not Justified

The document replaces the previous "1–2" claim with "cap+5" but provides no derivation. It says overshoot equals the number of concurrent workers processing that user's notifications, then says for a viral burst "it could be higher," then asserts cap+5 as the "practical bound." This is the same problem as before — a number chosen for comfort, not analysis.

### 8. The Rollout Gates Have a Measurement Problem

The acceptance criteria table specifies metrics like "P99 end-to-end latency (enqueue to provider ACK)" measured at 5% rollout. At 5% of 51M/day, that's ~2.5M notifications/day. P99 latency requires accurate timestamping at enqueue and at provider ACK. The document never specifies how provider ACK timestamps are captured, stored, or joined to enqueue timestamps. This is the hardest part of the measurement, and it's absent.

### 9. The SMS Ownership Split Is Mentioned But Not Shown

The executive summary claims "the SMS ownership split between E3 and E4 has a defined interface contract and propagation SLA." The document ends mid-sentence in §1.2.3. This contract is never shown. The claim in the summary is unsubstantiated by the document's actual content.

### 10. The Document Ends Mid-Sentence

Section 1.2.3 ends with "| Week | Max Daily Volume | Cumulative" — the warming schedule table is incomplete. The document is unfinished. This is a submission problem, not a design problem, but it means the IP warming plan — explicitly called a "prerequisite to launch" — is absent from the document.

### 11. The Fallback Chain Has a Sequencing Problem

§1.2.2 states "a delivery event row is written *before* routing resolves." But the fallback channel (push or email) is determined *during* routing. The metadata written pre-routing includes `"fallback_channel": "push"` — but whether push is available isn't known until preference lookup completes. Either the write happens after routing (contradicting "before") or the fallback channel in the pre-routing write is speculative and may be wrong.

### 12. The In-App Bypass Is Unresolved

The executive summary states in-app notifications "bypass the queue for latency reasons but use a dedicated retry store with equivalent semantics. The mechanism is specified." Searching the visible document, the mechanism is not specified anywhere in the shown content. This is either missing from the truncated portion or a false claim in the summary.

### 13. Four Engineers, Six Months — No Capacity Analysis

The document claims to prioritize operational simplicity given team size, but never maps work to engineers with any rigor. E3 and E4 are mentioned by name in the executive summary, implying an allocation exists, but no staffing breakdown appears in the visible document. The executive summary claims "E3's workload is redistributed" — redistributed from what, to what, is never shown.