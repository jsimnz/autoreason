## Real Problems with This Proposal

### 1. The Opt-Out Violation Number Is Presented as If It's Derived, But It Isn't

Section 2.4 is referenced repeatedly in the executive summary as containing a derivation of "180–900 opt-out violations per day." That section doesn't appear in this document. The number is cited as if it exists and has been shown to stakeholders, but there's no basis visible here for evaluating it. Legal is being asked to sign off on a number that cannot be audited from this document.

### 2. The Email Peak Concentration Math Is Internally Inconsistent

The document states: "All channels use consistent concentration assumptions within a scenario." But the combined peak table shows Push+In-App at 2,344/sec and Email at 203/sec in the US-centric scenario. Working backward: 3.25M × 0.90 ÷ 14,400 = 203/sec for email. That's consistent. But the earlier SendGrid section calculates 181/sec using 0.80 concentration, not 0.90. The document uses two different concentration factors for email in two different places without acknowledging the discrepancy. The procurement target (250/sec headroom over 181/sec) is undersized if 203/sec is the correct peak.

### 3. The Viral Spike Model Silently Assumes Zero Concurrent Normal Traffic

The spike drain calculation assumes workers running at full 2,800/sec capacity are entirely available to drain the backlog. But the spike arrives on top of normal-use traffic, which at 90% concentration is already 2,344/sec. The actual excess capacity available to drain the backlog is 2,800 − 2,344 = 456/sec, not 2,800/sec. The stated drain time of ~70 seconds and maximum delay of ~11 minutes are wrong. The actual drain time is substantially longer.

### 4. The 35%/15 Scenario Is Mishandled by the Queue Logic Claim

The document states the 35%/15 scenario (3,498/sec) "is handled by viral-spike queue logic with an approximately 14-minute maximum delay." But viral-spike queue logic is defined as absorbing temporary excess arrival above the 2,800/sec sizing target. A sustained scenario where normal-use peak is 3,498/sec isn't a spike — it's a new baseline. The queue never drains. Calling this "handled by viral-spike queue logic" is incorrect; it would produce indefinite queue growth during every peak window.

### 5. The SendGrid Headroom Argument Has a Gap

The document says an enterprise contract for 250/sec provides "38% headroom" over the 181/sec planning basis. But the consistent-concentration table shows email at 203/sec in the same scenario. If 203/sec is correct, headroom is 23%, not 38%. More critically, the 35%/30 scenario shows email at 210/sec — the document says this is handled by a "SendGrid plan upgrade," but gives no indication what throughput that upgrade must support or whether it's achievable within the existing enterprise contract structure.

### 6. Worker Latency Derivation Is Circular

The normal operation average queue depth is calculated as 100ms + 150ms = 250ms, representing poll interval plus provider latency. This is then used to derive a queue depth of 700 entries. But this assumes workers spend all their time either polling or waiting for one provider response — it ignores batching, which is explicitly mentioned as occurring "at the queue level (see Section 2.2)." Section 2.2 also doesn't appear in this document. If batching is real, the queue depth and memory estimates are wrong.

### 7. The Flat Email Cost Insight Is Presented as a Constraint But Isn't Fully True

The document claims email volume is "nearly flat across DAU/MAU scenarios" and that improving retention won't reduce email costs. The sensitivity table shows 3.15M to 3.35M — a 6% range — which supports "nearly flat." But this holds only because the re-engagement send rate (30% of lapsed users daily) is held constant across scenarios. If improved retention also changes re-engagement send policy (e.g., fewer lapsed users means a less aggressive re-engagement cadence), the flat-cost claim breaks down. The document presents a modeling assumption as a structural insight about the product's cost structure.

### 8. Default C Cannot Be Reintroduced, But the Document Leaves It Visible

The executive summary explicitly states Default C "cannot exist as a placeholder bracket, as this creates a circular finalization dependency." Default C then appears in the document body still listed as an option with bracket text. Stakeholders reading only the body section — not the executive summary — will see three options, not two. This is a document control failure that could produce the exact circular dependency the document warns against.

### 9. The Month 2 Checkpoint Owner Assignment Creates a Single Point of Failure With No Backup

E4 owns instrumentation and produces the checkpoint report. E1 reviews for queue-level accuracy. There is no stated contingency if E4 is unavailable at the checkpoint. Given a 4-engineer team on a 6-month timeline, this is a real operational risk, not a theoretical one. The checkpoint is a decision gate — missing it has cascading consequences defined in the table, but the table has no row for "checkpoint not produced."

### 10. The Broadcast Pipeline Is Flagged as Out of Scope But Not Isolated

The document states that push-to-all-MAU broadcasts "require a dedicated broadcast pipeline, is out of scope for this design, and is flagged as a product decision gate." But nothing in the design prevents a product decision from triggering this pattern — there's no architectural guard, no API contract that would make the out-of-scope case fail gracefully, and no defined owner for the product decision gate. "Out of scope" with no enforcement mechanism means the first time a product manager requests a push-to-all notification, the system will attempt it and hit FCM/APNs rate limits silently.