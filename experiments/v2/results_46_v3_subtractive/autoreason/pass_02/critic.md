## Real Problems with This Proposal

### 1. The Traffic Math Is Internally Inconsistent

The proposal states 3M DAU × 17 notifications/day = 50M total, then allocates 70% to push (35M/day) against a recipient base of 8M users with the app installed. That's 4.4 pushes per active push user per day — plausible. But in-app is 20% = 10M/day against 3M DAU = 3.3 per active user per day. The document then says "in-app notifications are lower-frequency per user than push, which is correct." 3.3 vs. 4.4 is barely lower, and in-app being nearly as frequent as push contradicts the stated rationale that in-app "surfaces a curated subset of events to users who are already in the app." The numbers don't support the narrative.

### 2. The SMS Budget Fix Creates a New Inconsistency

The proposal corrects the SMS volume from 1M/day to ~2,000/day to stay under $15,000/month. But the channel split table in Section 1 still shows SMS at "2% of Total" and "1M/day." The corrected operational cap appears only in the prose of Section 3.4, which isn't shown. The table is never updated. A reader following the table will still plan for 1M SMS/day.

### 3. The Digest Idempotency Logic Has a Race Condition

The code clears carried events before confirming the send succeeded, with a comment saying "if send fails, retry sends again (idempotent: digest_id prevents duplicate sends)." But `clear_carried_events` is called before the send attempt. If the process crashes after clearing but before sending, those events are gone — they're neither carried nor sent. The comment acknowledges retry but doesn't acknowledge this data loss window, which is exactly the silent data loss problem the revision claims to have fixed.

### 4. The Composite Primary Key Tradeoff Is Understated

The proposal says the only case requiring a bare `id` lookup is the mark-as-read endpoint, and the fix is to include `created_at` in the request payload. This means the client must store and transmit `created_at` for every notification it displays. This is a non-trivial API contract change that affects mobile clients, requires versioning, and creates a problem if clients built against an older API don't send `created_at`. This is described as a simple operational decision when it's actually a client-facing breaking change.

### 5. The WebSocket Scaling Section Is Incomplete — Literally

The document cuts off mid-sentence: "With 10 WebSocket servers, that's —" and ends. This is the section that was identified as an architectural gap in the previous revision. The revision claims to address it but doesn't. The most critical unresolved architectural problem from the prior review is still unresolved.

### 6. APNs Token Regeneration Ownership Is Fragile

E2 owns a background job that regenerates the JWT token every 45 minutes and updates it in a "shared credential store." If this job fails silently, all iOS push delivery fails after the current token expires. There is no mention of monitoring this job, alerting on failure, or what happens to in-flight APNs requests during token regeneration. For a component whose failure mode is complete iOS push outage, the operational design is described in one sentence.

### 7. The SendGrid Cost Comparison Is Wrong

The proposal says AWS SES would be "~$400/day less" than SendGrid. At SES pricing of $0.10/1,000 emails, 4M emails/day costs $400/day = $12,000/month. SendGrid Pro at scale for 4M emails/day is not $1,500/month — that tier handles roughly 100K-300K emails/month. The actual SendGrid cost at 4M/day (~120M/month) would be dramatically higher. The $1,500/month figure appears to be the entry-level plan price, not the price at the stated volume.

### 8. Cross-Cutting Ownership Assignments Conflict

E3 owns "deduplication across channels" and "feedback loop (bounces → suppression)." E2 owns "token/credential lifecycle." But APNs 410 responses (device unregistered) are both a token lifecycle event (E2's domain) and a suppression trigger (E3's domain). The proposal describes handling APNs 410 in Section 3.1 under push configuration, which is E2's area, but the suppression write is E3's feedback loop. The ownership boundary for this specific failure path is never resolved.

### 9. The Partition Maintenance Arithmetic Is Not Validated

The proposal states 10M notifications/day × 90 days = ~900M rows across 3 active partitions. Monthly partitions with 90-day retention means 3 months of partitions, which is correct. But 10M/day × 90 days = 900M rows total, distributed unevenly across months (not uniformly 300M per partition). More importantly, the proposal never addresses index size. A partial index on `(user_id, created_at DESC) WHERE is_read = FALSE` on 900M rows, where a large fraction may be unread for active users, could be very large. The claim that the architecture handles this is asserted, not demonstrated.

### 10. The "Proven Infrastructure" Framing Masks an Unproven Combination

The executive summary claims the design prioritizes "proven infrastructure over custom-built components." But the actual system combines Redis sorted sets with Lua atomicity, PostgreSQL declarative partitioning, Redis Pub/Sub WebSocket fan-out, a custom digest batching engine, a custom feedback loop, and custom APNs/FCM integrations — none of which is individually unproven, but the combination at 50M notifications/day with 4 engineers has never been operated by this team. The framing creates false confidence. The risks aren't in any single component; they're in the operational complexity of running all of them together.