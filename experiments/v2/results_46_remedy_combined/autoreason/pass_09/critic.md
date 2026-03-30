## Real Problems with This Proposal

### 1. The Suppression Flag Synchronous Write Is Asserted, Not Designed

The executive summary states opt-outs are "enforced by writing a suppression flag to the database synchronously on receipt" as if this resolves the compliance concern. But the proposal never specifies what system receives the opt-out, what database is written to, whether workers check this flag before every send or only on cache miss, what happens if the synchronous write fails, or how the flag propagates to third-party delivery providers who may have their own send queues already populated. The assertion is architectural hand-waving dressed as a solved problem.

### 2. The 15-Minute Unattributed Volume Diagnostic Has No Specified Mechanism

Section 1.3 states that if excess digest volume "cannot be attributed to a verified opt-in population within 15 minutes of automated diagnostic," sending halts. The proposal never describes what this automated diagnostic actually does, what data it queries, who built it, or how it distinguishes a legitimate opt-in surge from an instrumentation error. A 15-minute window for a compliance-critical decision with no specified implementation is a deadline attached to nothing.

### 3. The Stability Criterion for Baseline Promotion Is Circularly Defined

Section 1.4 states the live baseline promotes when "no single day exceeds 1.8× the rolling average." But the rolling average is computed from the same live traffic that contains the spike. A single large spike raises the rolling average, which raises the threshold, which makes future spikes less likely to trigger the stability failure condition. The criterion does not reliably detect an unstable baseline — it partially absorbs instability into the average it is supposed to protect.

### 4. WAND Is Used for Provisioning Decisions Before It Can Be Measured

The proposal correctly acknowledges WAND cannot be measured until Week 4, then provisions infrastructure based on three WAND scenarios (conservative 1M, base 2M, aggressive 3M). The $160/month insurance argument is presented as independent of the proxy metric, but the scenario range itself — the thing being insured against — is derived entirely from the unmeasured WAND estimate. The cost-of-insurance framing does not escape the dependency; it just stops acknowledging it.

### 5. The Compliance Review Triggered by Path A Has No Enforcement Mechanism

Path A of the digest volume diagnostic allows sending to continue and schedules "a compliance review within 5 business days." There is no specified owner for this review, no consequence if it does not occur, no criterion for what the review must conclude, and no action required if the review finds the opt-in mechanism was not functioning correctly. A scheduled review with no owner, no teeth, and no defined outcome is not a compliance control.

### 6. The Four-Engineer Scope Problem Is Acknowledged but the Phased Proposal Is Not Present

Problem 12 in the executive summary states "a phased scope reduction with explicit tradeoffs is proposed" and references Section 8. The document as provided does not contain Section 8. The most operationally significant finding in the proposal — that the stated scope is not deliverable — is deferred to a section that does not exist in this document.

### 7. The OTP Email Fallback Correction Is Incomplete

Problem 7 states the fallback conversion rate is "modeled at 40% of blocked SMS attempts" and a "cost ceiling derived and included in the cost table." The cost table in Section 1.3 lists OTP email fallback volume as "Variable; modeled in Section 3.4." Section 3.4 is not present in this document. The correction claimed in the executive summary is not actually present in the document body.

### 8. The Peak Factor Sensitivity Analysis Is Referenced but Not Present

Problem 8 states a sensitivity table covering 3×, 5×, 8×, and 10× peak factors "appears in Section 2.5." Section 2.5 is not present in this document. This is the second instance of a correction claimed in the executive summary that does not exist in the document as provided.

### 9. The SQS Cost Arithmetic Correction Is Also Missing

Problem 9 states "Section 5.2 shows the full API call derivation." Section 5.2 is not present in this document. Three of the twelve claimed corrections reference sections that do not exist.

### 10. The Credential Breach Row Cost Figure Is Not Operationally Bounded

The SMS cost table shows a full credential breach at $79,000/day for 10M accounts. The proposal does not specify who has authority to authorize this spend, whether there is a per-incident budget ceiling, what happens if the cost is not pre-approved, or how the engineering team is expected to execute a 10M-message SMS blast operationally. The number is presented as a planning figure with no operational or financial governance attached to it.

### 11. The 55% Blended Opt-In Rate Mixes Incompatible Source Methodologies

The three cited sources use different measurement methodologies: Airship measures opt-in rate at the app level, OneSignal measures it at the notification permission prompt, and AppsFlyer measures the effect of prompt timing on conversion. Blending these into a single 55% figure treats them as measuring the same thing. The honest uncertainty range of 40–70% acknowledged in the text is not a correction for this problem — it is a wider band around a number that may not be methodologically coherent in the first place.

### 12. The Resumption SLA for Digest Halt Has an Ambiguous Escalation Path

Section addressing Problem 3 states resumption requires compliance owner sign-off within 4 business hours, escalating to a "designated backup" and then to "engineering lead with authority to unblock at 8 hours." Giving an engineering lead authority to unblock a compliance-halted email send — absent compliance sign-off — contradicts the premise that the halt exists for compliance reasons. The escalation path terminates in a person whose role is explicitly not compliance.