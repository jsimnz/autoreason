## Real Problems with This Proposal

### 1. The Document Cuts Off Mid-Sentence

Section 2.1 ends abruptly in the middle of a table row. The SMS cost section, which is explicitly called out as requiring "explicit accounting," has no actual numbers. The document promises a formula and then provides no completed calculation. This is a critical gap in the one section that requires sign-off before production.

### 2. The Architectural Breakpoint Threshold Is Asserted, Not Justified

The document repeatedly stakes major decisions on the ~2,500/sec threshold but the justification given is circular: it's the threshold because above it, complexity rivals a partitioned design, which is defined as the threshold. The actual constraint — SQS `ReceiveMessage` polling overhead and consumer pool sizing — is gestured at but never quantified. A 4-person team cannot evaluate whether this threshold applies to their specific worker processing time and message size without actual numbers.

### 3. The Availability Calculation Is Wrong

The document states "end-to-end availability cannot exceed the product of component availabilities" and lists SQS (99.9%), ElastiCache (99.9%), RDS (99.95%), and FCM/APNs (no SLA), then concludes 99.5% is achievable. The product of just the three known SLAs is approximately 99.75%. The document never explains how FCM/APNs variance closes the gap from 99.75% to 99.5%, nor does it show the actual calculation. The 99.5% figure appears to be chosen rather than derived.

### 4. The Sign-Off Process References a Section That Doesn't Exist in the Visible Document

Section 2.1 repeatedly refers to "§10 Escalation Procedure" for the parallel dispatch sign-off process. The table of contents lists §10 as "Escalation Procedure," but no content from §10 appears in this document. The sign-off is described as blocking production deployment, but the actual process is missing.

### 5. The Burst Ceiling Multiplier Is Inconsistently Defined

Section 1.1.3 states the 3.0× burst multiplier "already accounts for geographic concentration and is not multiplied by the geographic peak multiplier separately." But §1.1 presents the geographic peak (2.0× average) and burst ceiling (3.0× average) as distinct values derived from average throughput, implying the 3.0× was chosen to be above the 2.0× geographic peak — not that it encodes geographic concentration. These are different claims. If 3.0× was chosen because 2.0× is the geographic peak and headroom is needed above that, the document should say so. If 3.0× independently accounts for geography, the 2.0× geographic peak multiplier is unexplained.

### 6. The Quiet Hours Behavior Is Referenced But Not Specified

Section 1.2 excludes ML-based send-time optimization in favor of "fixed quiet hours — behavior specified in §3.3." Section 3.3 is listed in the table of contents as "Priority and Batching Logic" but no content from that section appears in the document. For a system where delivery timing directly affects user experience and is a stated success criterion, this is a missing specification, not a deferred detail.

### 7. The Recalculation Procedure Points to a Section That Doesn't Fully Exist

Section 1.1.3 instructs: "substitute them into the burst ceiling formula and recalculate §7 directly." Section 7 is listed as "Capacity Planning" in the table of contents but no content from §7 appears in the document. Engineers are told to recalculate a section that hasn't been written.

### 8. The Governance Structure Has No Fallback if the Product Lead Is Unavailable

The parallel dispatch sign-off is explicitly blocking, requires Jordan Rivera specifically, and has no named alternate or escalation path if Rivera is unavailable, on leave, or leaves the company. For a decision that blocks a production deployment path, a single-person dependency with no fallback is an operational risk the document acknowledges in structure but ignores in practice.

### 9. The Events-Per-DAU Assumption Is Inconsistent Across Tables

Section 1.1.1 states its figures "assume 15 events/DAU/day." The combined sensitivity table in §1.1.3 shows the (15% DAU/MAU, 15 events/DAU) cell as ~780/sec burst ceiling. But using the formula given: (10M × 0.15 × 15 / 86,400) × 3.0 = approximately 782/sec, which rounds to ~780. The (30% DAU/MAU, 15 events/DAU) cell shows ~1,560/sec. The formula gives (10M × 0.30 × 15 / 86,400) × 3.0 ≈ 1,563/sec. These are consistent. However, §1.1.1's baseline row shows "~1,560/sec" burst ceiling, which matches. But the header of §1.1.1 says its figures assume 15 events/DAU/day and should match §1.1.3's middle column — they do, but this is only verifiable by cross-referencing three sections. A reader using §1.1.1 alone cannot detect if the tables diverge.

### 10. The 14-Day Resolution Target for §9 Has No Consequence Defined

The document states §9 open decisions must be resolved within 14 days, and no infrastructure should be provisioned until then. There is no stated consequence, escalation path, or decision owner if day 14 passes without resolution. The document identifies Priya Anand as Executive Sponsor but assigns no governance role to her in this specific failure mode.