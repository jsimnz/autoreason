## Real Problems Found

### 1. The "Final" Sections Depend on the Open Decisions Too

The document declares Sections 2, 4, and 6 "final and implementation-ready," but Section 2's WebSocket sizing calculation (§2.3) uses the 3M DAU figure directly — the number that is explicitly unvalidated. The peak concurrent connection estimate of 62,500 and the resulting server count of 6–8 instances are both downstream of the contested DAU/MAU ratio. The same is true of the SMS cost note in §2.1, which uses 10M MAU and a 1% assumption to produce a monthly cost figure. These sections cannot be implementation-ready in any meaningful sense while the first multiplier in every calculation is unresolved.

### 2. The Document Is Cut Off

Section 3.2 ends mid-sentence: "the user's" — and then nothing. This is not a minor formatting issue. Batching logic is one of the most consequential behavioral decisions in the system, affecting user experience, database write volume, and push provider costs. The conditions under which the batch window is skipped are incomplete, and whatever follows "the user's" is missing entirely. Any engineer implementing this from the document will have to guess or escalate.

### 3. The Peak Multiplier Table Is Internally Inconsistent with the Baseline

Section 1.1.2 defines three geographic cases. The US-only case uses a 2.0× multiplier on the average throughput of 520 events/second, which yields ~1,040/second sustained peak. The document then states burst headroom is at 3× average, producing ~1,560/second. But the table in §1.1 already lists 1,560 as the "peak throughput" before any burst headroom discussion. The document is using "peak" to mean two different things — the geographic concentration peak and the burst headroom ceiling — and conflating them in the summary table. Infrastructure provisioned from §1.1 without reading §1.1.2 carefully will be sized incorrectly.

### 4. Parallel Critical Delivery Creates Duplicate Notification UX Problem Without Resolution

Section 2.1 explicitly states that for Critical notifications, users may receive the same notification via both push and email simultaneously, and calls this "acceptable and expected." No product decision is cited for this. For security events like 2FA codes or login alerts, receiving the same alert via three channels simultaneously is not obviously acceptable — it creates user anxiety and potential confusion about which action to take. The document acknowledges the problem and then closes it with an assertion rather than a decision. There is no reference to product sign-off on this behavior.

### 5. The Audit Log for Priority Overrides Has No Defined Consumer

Section 3.1 describes a runtime override mechanism with logging to an audit table. The override allowlist, the privileged service account, and the 403 rejection are all specified. But there is no definition of who reads the audit log, at what frequency, or what action is taken on anomalous entries. An audit log with no defined consumer is not an audit control — it is a table that will accumulate rows until someone asks why storage costs are rising.

### 6. SES Switching Cost Warning Contradicts the "Simple" Framing

Section 2.4 correctly documents that migrating away from SES is a 4–6 week degraded-deliverability process. This is presented as a caution, but the underlying implication is that SES may be the wrong choice for a team of four who "cannot afford deliverability debugging" — the exact phrase used to justify Twilio over cheaper SMS alternatives. The same logic applied to email would argue against SES, but the document applies it inconsistently. The tension is named but not resolved.

### 7. The 90-Day Token Staleness Threshold Has No Stated Basis

Section 2.2 states that device tokens not refreshed in 90 days are soft-deleted. This is presented as a design decision with no supporting rationale. Ninety days is longer than typical app store update cycles and could mean a significant fraction of tokens are for users who have uninstalled the app. More importantly, FCM and APNs will return invalid-token errors for uninstalled apps, which the document handles via hard-delete on error response — making the 90-day soft-delete a redundant mechanism that still allows push attempts to uninstalled apps for up to 90 days. The interaction between these two token invalidation paths is not analyzed.

### 8. WebSocket Sticky Sessions Are Disabled But the Rationale Creates a New Problem

Section 2.3 disables sticky sessions because "connection state is in Redis, not local." But Redis pub/sub is also cited as the delivery mechanism — each WebSocket server subscribes to active user channels. Without sticky sessions, when a notification is published to `notifications:{user_id}`, every WebSocket server that has any subscriber for that channel receives the message. If a user has one active connection across N servers, N-1 servers receive a message they cannot deliver. At 62,500 concurrent connections across 6–8 servers, this is constant unnecessary pub/sub fan-out. The document does not acknowledge this.

### 9. Re-engagement Email Frequency Cap Is Not Tied to a Definition of "Inactive"

Section 2.4 defines re-engagement emails as triggered when a "user inactive > 7 days," capped at once per week. A user who is inactive for exactly 8 days and then becomes active again could receive a re-engagement email and then receive another one 7 days later if they become inactive again briefly. The interaction between the inactivity trigger and the frequency cap is not specified. More critically, "inactive" is not defined — no session, no push open, no app open, or no any-event are all plausible definitions with different behavioral outcomes.

### 10. The 99.9% Availability Target References a Section That Isn't Visible

Section 1.3 states availability is 99.9% with "Analysis in §6.4," but Section 6 is listed as "Failure Handling" and §6.4 is referenced as where RTO and RPO are defined. Readers cannot verify whether the 99.9% target is derived from the failure analysis or asserted independently of it, because the document does not include enough of Section 6 to evaluate the claim. For a metric that determines acceptable downtime for a 10M MAU product, this is not a minor gap.