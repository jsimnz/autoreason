## Real Problems with This Proposal

### 1. The Viral Inbound Derivation Is Self-Contradicting and Wrong

The document states the viral inbound ceiling is 8,000/sec, then derives approximately 1,290/sec from its own explicit assumptions, then says "we use 8,000/sec as the planning ceiling." No arithmetic connects 1,290 to 8,000. The document acknowledges Version Y's 14,000/sec was unjustified, then substitutes an equally unjustified number while claiming epistemic rigor. The phrase "the high end of what a larger or more aggressive spike could produce" is not a derivation. The central claim of the executive summary — "every number is derived with visible arithmetic" — is false for the most consequential capacity figure in the document.

### 2. The Worker Throughput Arithmetic Is Internally Inconsistent

The document states one P1 push worker sustains 15,600 notifications/second in isolation (500 notifications / 0.032 seconds). It then allocates 14 P1 push workers to 2 APNs connections rated at 800/sec each, yielding a ceiling of 1,600/sec. At 14 workers × 15,600/sec per worker, the workers can theoretically process 218,400/sec — over 100× the APNs constraint. The worker pool is not sized by any meaningful analysis; the workers are essentially idle placeholders waiting on APNs. The document never acknowledges this, which means the worker count justification is circular.

### 3. The P0 Push Allocation Is Arithmetically Incoherent

The worker table shows P0 with "8 push/SMS combined" workers and "1 dedicated APNs connection" at 800/sec. But P1 has 14 push workers on 2 connections (1,600/sec ceiling) and P2 has 6 workers "sharing P1 connections during low P1 load." This means P2 has no dedicated connection and its throughput is undefined except as a function of P1 load — which is exactly the isolation failure the P0/P1/P2 separation is supposed to prevent. The aggregate throughput table then lists P2 push at "~800/sec," which requires a third APNs connection that does not appear anywhere in the connection accounting.

### 4. The Receipt Decoupling Tradeoff Is Understated to the Point of Misrepresentation

The document says "APNs and FCM handle duplicate delivery gracefully via notification ID deduplication on the device." This is false. APNs does not deduplicate on-device; it delivers whatever the server sends. The `apns-collapse-id` header collapses notifications of the same type, but this is not general deduplication and does not apply to arbitrary notification IDs. FCM has a `collapse_key` mechanism with similar limitations. The document presents a false technical guarantee to justify a real consistency risk.

### 5. The In-App Write Throughput Claim Is Unsupported

The document states the in-app store PostgreSQL primary handles "~5,000/sec" write capacity. It previously stated a c5.2xlarge with PgBouncer handles "15,000–20,000 simple inserts/second." The in-app figure is 25–33% of the push receipt figure on presumably identical hardware, with no explanation. The 9 in-app workers are then said to achieve "~2,000/sec" — 40% of the stated capacity ceiling — also without derivation. These numbers are not connected to each other or to the hardware specification.

### 6. The SMS Volume Derivation Is Not Shown

The executive summary claims SMS volume is "derived from auth event rate (~360K/day)" and criticizes Version Y for lacking derivation. Section 1.3 is referenced but the document is cut off before it appears. The derivation — the specific claimed improvement over Version Y — is not present. This is the same problem the document criticizes, applied to itself.

### 7. The Redis Memory Model Uses an Inconsistent Entry Size

The queue depth table uses "50–80 bytes per sorted set entry" to estimate Redis memory. A Redis sorted set entry consists of the member string plus score (8 bytes) plus per-entry overhead (approximately 64 bytes for the skiplist and hash table structures). If notification IDs are UUIDs (36 bytes as strings) or 64-bit integers (8 bytes), the per-entry overhead dominates and the 50–80 byte figure may be reasonable — but the document never specifies what form notification IDs take. If IDs are UUID strings, actual Redis overhead per entry is closer to 150–200 bytes under production conditions, which would cut the stated memory runway by roughly half, moving the Redis OOM risk from 60 minutes to approximately 30 minutes.

### 8. The Alerting Backup Path Has an Unstated Dependency Loop

The document specifies SES as the tertiary alerting path "to personal email." Personal email delivery depends on the recipient's email provider being reachable, which is not a dependency the team controls. More importantly, if the primary incident involves AWS infrastructure degradation (a plausible scenario given the system runs on AWS), SES — an AWS service — is directly in the failure domain being alerted about. The document claims "structural independence eliminates single-vendor failure modes" but the tertiary path reintroduces AWS as a dependency.

### 9. The Document Is Incomplete and Was Published Incomplete

The P1 SLA table is cut off mid-row ("10,000–100"). This is not a minor formatting issue — the table contains the operational thresholds that on-call engineers are supposed to use during incidents. Publishing an incomplete SLA table in a design document that will be referenced during incidents is a process failure, not a document formatting issue. The document's claim to be a complete synthesis cannot be true if a core operational table is missing.

### 10. The Spend Cap Mechanism Is Named but Not Defined

The executive summary states SMS has a "spend cap $35K/month" mechanism. No section of the visible document describes how this cap is enforced — whether it is a Twilio account limit, an application-layer counter, a billing alert with manual intervention, or something else. A spend cap that is not mechanically enforced is not a cap; it is a target. The distinction matters because SMS costs are per-message and a bug in the auth event rate calculation could exhaust the cap in hours.