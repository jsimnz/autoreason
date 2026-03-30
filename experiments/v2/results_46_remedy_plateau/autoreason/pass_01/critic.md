## Real Problems with This Proposal

### 1. The Single Redis Sorted Set Is a Correctness Bug, Not Just a Scale Concern

The proposal acknowledges contention and claims a Lua script fixes it. But the dequeue logic shown uses a pipeline (not a Lua script), and those are not the same thing — a pipeline batches commands but doesn't execute them atomically. Under concurrent workers, multiple workers can read the same range before any of them removes it, causing duplicate deliveries. This is a correctness failure for OTPs and security alerts, not just a performance issue.

### 2. The Math on SMS Cost Is Wrong by an Order of Magnitude

The proposal states 1M SMS/day at $0.0075 = $7,500/day. That's $2.7M/year for a 2% channel on a 10M MAU app. No social app spends that. Either the volume estimate is wrong, the price is wrong, or the channel mix is wrong — but the proposal treats this number as given and moves on. At those numbers, SMS would dominate the infrastructure budget and the decision to build it in-house rather than use a managed platform becomes the most important financial decision in the document, not a footnote.

### 3. The 17 Notifications/User/Day Basis Is Fabricated

The table says "Industry avg for engaged social apps" with no citation. This single number drives the entire scale model. 17/day × 3M DAU = 51M/day, which is where all the queue sizing, worker pool sizing, and cost estimates come from. If the real number is 5 or 30, the architecture changes materially. There is no sensitivity analysis and no plan to validate this assumption before committing to infrastructure.

### 4. The Priority Scoring Formula Breaks Under Real Conditions

The score formula is `priority_weight - (timestamp / 1e10)`. At current Unix timestamps (~1.7×10⁹), dividing by 1e10 gives values between 0.1 and 0.2. The gap between P0 (weight 0) and P1 (weight 1,000,000) is enormous relative to the timestamp component. This means a P1 notification enqueued before a P0 notification will always lose — which is the intent — but it also means P0 notifications from 12 hours ago will be dequeued before P1 notifications from right now, even when the P0 has already expired. The TTL is stored separately but the queue score doesn't encode it. Expired P0 items will block P1 items.

### 5. Partition Strategy Creates a Maintenance Gap

The proposal says to partition `notifications` by `created_at` monthly and drop partitions older than 90 days. Monthly partitions at 10M rows/day means each partition has ~300M rows. Dropping a partition is fast, but the transition between partitions happens at midnight on the first of each month — at that moment, inserts go to the new partition while queries for recent notifications (created in the last few minutes of the previous month) cross a partition boundary. More critically, the index `idx_notifications_user_unread` is a local index on each partition, so queries for a user's unread notifications spanning a partition boundary require scanning two indexes. This is not mentioned.

### 6. The In-App WebSocket Architecture Has a Silent Failure Mode

The proposal says: "If the WebSocket message is missed, the client polls on reconnect." But there is no polling interval defined, no API for the client to fetch notifications since a given timestamp, and the only listed API endpoint is cursor-based with no time-based filter. A user who disconnects and reconnects will get the next page of their notification feed, not the notifications they missed during the gap. The cursor-based API cannot express "give me everything since I was last connected."

### 7. Digest Carry-Forward Logic Has No Termination Condition

The `build_daily_digest` function carries events forward if there are fewer than 3 grouped items. There is no maximum carry-forward period. A user who receives 2 notification events per day will never get a digest — their events accumulate indefinitely. This is both a storage problem and a user experience problem (notifications that are weeks old eventually appearing in a digest).

### 8. The APNs JWT Rotation Comment Is Wrong

The proposal says "rotate keys every 55 min." APNs JWT tokens expire after 1 hour, but the token is a signed JWT using a long-lived private key — you rotate the *token* (regenerate the JWT), not the *key*. Rotating the actual APNs Auth Key (the .p8 file) is a manual process in App Store Connect that would break all push delivery until clients receive the new key. This conflation suggests the person writing this section hasn't operated APNs at production scale.

### 9. The Team Allocation Has a Single Point of Failure on the Critical Path

E2 owns all four channel integrations: APNs, FCM, SendGrid, and Twilio. These are four separate external APIs with different authentication models, rate limits, error codes, webhook formats, and compliance requirements. The proposal allocates one engineer to all of them with no mention of what happens if E2 is unavailable. Given the 6-month timeline and no QA, any absence on E2 stalls the entire delivery layer.

### 10. TCPA Compliance Is Stated But Not Designed

The proposal says "no SMS between 9pm-8am in user's local timezone" for TCPA compliance. But user timezone is not a field in any schema shown in the document. The `push_tokens` table has `last_used_at` and `is_valid`. The `notifications` table has no timezone column. There is no described mechanism for determining or storing user timezone, which means the compliance requirement is stated but has no implementation path.