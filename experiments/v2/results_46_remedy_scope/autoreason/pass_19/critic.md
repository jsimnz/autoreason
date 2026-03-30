## Real Problems

### 1. Document Cuts Off Mid-Sentence

Section 1.4 ends with "Load test push dispatch against a staging FC" — the document is incomplete. Critical spike analysis content is missing, including the sensitivity quantification and load test decision thresholds that are repeatedly referenced throughout the document as authoritative.

### 2. Self-Referential Dependency Loops Without Resolution

The document repeatedly cites sections that are missing or truncated. Section 1.4 is supposed to contain the sensitivity table for P1 delay figures under different FCM backoff assumptions, the load test decision thresholds, and the conservative fallback operating mode. All of these are cited by the executive summary, Section 1.3, and elsewhere as the definitive resolution. The document cannot stand on its own.

### 3. The "Named Humans" Gate Is Circular

Three deployment checklist fields require named humans to prevent a non-zero exit code. But the document never defines what those three decisions are. Section 7.1 is referenced for the gate mechanism but is not included in the document. A reader cannot determine which decisions require human sign-off, only that some do.

### 4. Section 7 Referenced Repeatedly But Not Present

The role-based fallback chain for unavailable named individuals is cited at least four times as the resolution for personnel gaps. Section 7 does not appear in this document. Every reference to it is a dead link.

### 5. The Starvation Claim Is Internally Contradictory

The executive summary states: "The token bucket rate-limits P0/P1 consumption but does not guarantee forward progress for P2/P3 under sustained P0/P1 saturation. The precise conditions under which starvation occurs despite the token bucket are specified in Section 3.2." A token bucket that rate-limits P0/P1 consumption should by definition create capacity for lower priorities. If starvation is still possible, the mechanism either doesn't work as described or the description is wrong. This contradiction is never resolved.

### 6. PostgreSQL Pool Exhaustion Arithmetic Is Promised But Absent

The executive summary states "PostgreSQL pool exhaustion risk is quantified with full arithmetic in Section 2.1." Section 2.1 is not in this document. The worst-case P1 delay figures (20–40 minutes, 50–80 minutes) are presented as derived step-by-step, but the derivation is in a missing section.

### 7. The Orphaned Processing Set Entries Problem Is Understated

The mitigation for crashed workers is described as "a cross-instance recovery sweep described fully in Section 2.1." That section is absent. But more critically: the document acknowledges that if the container is destroyed, processing set entries may be orphaned, then defers entirely to a missing section. The severity of this — messages silently lost or duplicated — is not addressed in any present section.

### 8. The Redis Provisioning Decision Creates a Real Gap Under Option B

The Option B annotation requires that "push and in-app workers will experience increased Redis latency" and that "writes queue locally in worker memory for up to 60 seconds." No bound is given on how many writes can queue in worker memory, what happens when that bound is exceeded, or whether the 60-second figure is a guarantee or an estimate. This is presented as an acceptable degraded state without supporting analysis.

### 9. Fanout Cap Behavior Is Underspecified in a Critical Way

Events exceeding 10,000 recipients are split into batched jobs processed over 5 minutes. The document does not address what happens when multiple viral events occur simultaneously, each generating fanout jobs. The 5-minute batching window could stack, producing unbounded queue depth growth during a viral spike — exactly the scenario the spike analysis is supposed to address.

### 10. The Month-1 Default Provisioning Is Operationally Risky

If the month-1 checkpoint is missed, the engineering lead is supposed to execute specific kubectl scale commands within 24 hours. But the document also states the runbook is a month-1 deliverable. If the checkpoint is missed because of an organizational failure, the runbook may not yet exist, meaning the engineer executing the default provisioning has no runbook to log actions against, contradicting step 4 of the procedure.

### 11. The 3× Peak Multiplier Is Applied to a Two-Hour Window But Used Inconsistently

The sensitivity table uses a 3× peak multiplier over a two-hour window to derive peak per-second rates. The traffic response matrix thresholds are in daily volume. These are not the same metric. A day with 45M total notifications but a 5× peak in one hour would show as "on plan" in the daily volume column of the matrix while actually triggering the "significantly above plan" response. The matrix doesn't account for intraday distribution.

### 12. The Auto-Scaling Claim Has No Implementation Path

The timing estimates in Section 1.3 reference "automated (auto-scaling, month 2 onward)" as a 2–3 minute response. No auto-scaling configuration, trigger metrics, or implementation plan appears anywhere in the document. This is presented as a concrete operational capability with a delivery date but has no backing detail.

### 13. The Deduplication Memory Bound Is Presented as Settled When It Is Not

The document states 128 bytes per ID, 10M retained IDs per channel, ~1.3 GB per channel at maximum retention. It does not state how many channels exist, whether this is per-instance or cluster-total, or what happens when the bound is reached — whether entries are evicted, writes are rejected, or the system degrades silently.