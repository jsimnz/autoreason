## Real Problems With This Proposal

### 1. The Document Is Structurally Self-Defeating

The executive summary and status section spend extraordinary effort documenting what the document *doesn't* claim and what *can't* be known. This is intellectually honest but practically counterproductive. An on-call engineer at 3 AM who needs Sections 1.3, 4.3, and 6.2 will still encounter paragraphs of epistemic hedging before reaching actionable content. The claim that those sections are "self-contained" is undermined by the constant cross-references within them (Section 1.3 references 1.3a, 6.2, and 7.1–7.2 within the matrix itself).

### 2. The Traffic Response Matrix Has an Unresolved Decision Embedded In It

Section 1.3 describes the 45M–80M/day response as conditional on whether Redis is "Option A or Option B" — but Section 1.3a is cut off mid-sentence. The matrix is therefore incomplete. The document explicitly states this decision "cannot remain unresolved," then leaves it unresolved. An operator following the matrix during an incident hits a branch they cannot evaluate.

### 3. The Starvation "Prevention" Is Described as Non-Prevention

The document states the token bucket "does not guarantee forward progress for P2/P3 under sustained P0/P1 saturation" and defers the precise failure conditions to Section 3.2, which is not included. This means the document acknowledges a known starvation scenario exists but provides no way to evaluate its severity, frequency, or operational impact. For a system handling user-facing notifications, silent indefinite deferral of P2/P3 messages is a product problem, not just a technical footnote.

### 4. The Worst-Case Delay Figures Are Presented Without Their Derivation Being Verifiable

The document cites "20–40 minutes under a standard spike, 50–80 minutes if a DB issue outlasts the spike" as P1 delay under coincident failure, calling them "derived step-by-step in Section 1.4." Section 1.4 is included but does not actually contain the step-by-step derivation — it contains the sensitivity table and FCM assumptions. The derivation is referenced but absent. These figures govern architectural go/no-go decisions and cannot be evaluated.

### 5. The FCM Rate Limit Is Load-Test-Contingent But the Load Test Has No Owner or Date

Section 1.4 and the executive summary both state that if the actual FCM limit is below 2,000/sec, "the P1 protection claims in this document are materially wrong and the architecture requires re-evaluation before launch." The document specifies that a pre-production load test must occur with explicit decision thresholds. However, nowhere in the visible document is there a named owner for this test, a scheduled date, or a mechanism that blocks launch if the test hasn't been run. The deployment checklist gate (Section 7.1) is mentioned but not shown. The load test is the single most consequential prerequisite in the document and has no enforcement path visible here.

### 6. The Month-1 Default Provisioning Procedure Assumes Infrastructure That May Not Exist

The missed-checkpoint default specifies exact `kubectl scale` commands with specific replica counts (e.g., "push-worker --replicas=12 from 8 baseline"). This assumes the deployment names, baseline replica counts, and cluster access are stable and correct at the time of execution. There is no mechanism described to verify these are current. If a deployment was renamed, scaled differently, or migrated between month-1 and day 35, the procedure executes incorrect commands silently — scaling the wrong thing or failing with a non-obvious error at 3 AM.

### 7. The Fanout Cap Creates an Undocumented User-Visible Behavior

Fanout is capped at 10,000 recipients per event, with excess split into batched jobs over 5 minutes. This means followers beyond position 10,000 in a fanout receive notifications up to 5 minutes later than the first 10,000. For a social app, this is a product behavior with potential user-visible inconsistency (e.g., "why did I get this notification 4 minutes after my friend?"). The document treats this purely as a systems constraint with no discussion of whether product accepted this tradeoff or whether it was surfaced to them.

### 8. The Deduplication Memory Bound Arithmetic Is Inconsistent With the Architecture

Section 2.2 states deduplication uses 128 bytes per ID, 10M retained IDs per channel, yielding ~1.3 GB per channel. But the document also states the deduplication window is 60 seconds (from the power-user discussion in Section 1.1). If the window is 60 seconds, the number of retained IDs at any moment is bounded by 60 seconds of throughput, not 10M. At peak (1,575/sec for push), that's ~94,500 IDs — roughly 12 MB, not 1.3 GB. Either the 10M figure is wrong, the 60-second window is wrong, or the two sections are describing different deduplication mechanisms without saying so. This inconsistency is in the document's own arithmetic.

### 9. The Role-Based Fallback in Section 7.2 Is Referenced Repeatedly But Not Shown

Sections 1.1, 1.3, and the document header all invoke "Section 7.2's role-based fallback chain" as the resolution mechanism when named individuals are unavailable. Section 7.2 is not included in this document. Every accountability mechanism in the document ultimately depends on a section that doesn't exist here. If this document were used as-is, every departure or unavailability scenario would hit a dead reference.

### 10. The Per-User Rate Limit Is Stated as Non-Derived

The per-user rate limit of 20 notifications/hour with a burst of 5 is described as "not derived from average behavior" — but no derivation or source is given at all. It is an unexplained constant. For a social app where notification volume directly affects retention and spam perception, this is a product-consequential number. Stating it is not derived from averages without stating what it *is* derived from means there is no basis to evaluate whether it is correct, too restrictive, or too permissive.

### 11. The Auto-Scaling Trigger Threshold Has No Justification

The HPA triggers at `notification_queue_depth_p1 > 5,000 for > 2 minutes`. At the plan-rate peak of ~1,094 push notifications/sec, a queue depth of 5,000 represents roughly 4–5 seconds of backlog — an extremely shallow trigger that will cause frequent unnecessary scale-up events during normal traffic variation. Conversely, if workers are processing at near-peak capacity, a 5,000-deep queue may already represent meaningful latency before scaling begins. The threshold appears arbitrary, and the document provides no analysis of false-positive scale-up rate or the cost implications.