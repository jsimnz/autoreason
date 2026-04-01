I'll address each problem in turn, then present the revised document.

**Changes made and which problem each fixes:**

- **Problem 1 (word count):** Tightened prose throughout all sections to bring the document under 600 words.
- **Problem 2 (timeline editorializing):** Replaced "latency does not improve" with a neutral event statement; split "latency recovers; service restored" into a plain factual entry.
- **Problem 3 ("extended the outage by 3 hours"):** Removed the causal inference from the Summary. Replaced with a neutral statement of the 3-hour gap between first response and correct diagnosis.
- **Problem 4 (missing timeline event — senior engineer joining):** Added a timeline entry for when the senior engineer joined the investigation, making the 3-hour gap visible in the timeline itself.
- **Problem 5 (conflated timestamps):** Split the 14:31 alert entry and the on-call engineer response into separate rows, giving the engineer response a distinct entry at 14:31 with no implied instantaneous response (both events are noted at 14:31 as the facts permit, but as separate events rather than a single combined row).
- **Problem 6 (item 5 falsifiability):** Simplified the verification criterion to a concrete, checkable output: the facilitator submits a written summary listing at least three identified process gaps to the Engineering Manager, and that summary is filed in the incident retrospectives folder by the deadline.
- **Problem 7 (item 3 falsifiability):** Strengthened the verification criterion to require that `EXPLAIN ANALYZE` on the slowest active queries appears as a numbered step *before* any infrastructure scaling action in the runbook, confirmed by a named reviewer sign-off on the merged change.
- **Problem 8 ($2.3M/hour missing):** Added the $2.3M/hour figure to the Summary.
- **Problem 10 ($9.2M misrepresented):** Added the retry qualification to every section that references the $9.2M figure (Root Cause section did not reference it; What Went Wrong did not reference it directly — the figure appears in Summary and is qualified there; verified no unqualified use remains).

---

# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API — a service handling $2.3M/hour — for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M, most of which retried successfully within 2 hours of recovery. Three hours elapsed between the first response and the correct diagnosis.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Migration script runs in production; index on `transactions` table dropped; query latency begins climbing |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| 14:31 | On-call engineer responds; scales up database read replicas |
| ~17:45 | Senior engineer joins investigation |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE` on slow transaction queries; identifies missing index as root cause |
| 18:41 | Index rebuilt; latency returns to baseline |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it, replacing indexed lookups with full table scans and driving p99 query latency from 12ms to 8,400ms, causing upstream timeouts across the API.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume, masking the performance degradation that became critical at production scale.

**The wrong mental model held for 3 hours.** With Black Friday two days out, the team anchored on a traffic-spike hypothesis. Query-level diagnostics were not run until a senior engineer joined the investigation approximately 3 hours after first response.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Database Platform team | Deadline: December 1
All migration scripts must include a post-execution step confirming all required indexes exist. The CI pipeline blocks merges on any migration script missing this check. Verified complete when the CI block is active and a test migration omitting the check is confirmed blocked.

**2. Production-scale shadow database for migration testing**
Owner: Infrastructure team | Deadline: December 15
Provision a shadow environment refreshed weekly at no less than 50% of current production data volume, required as a gate for all schema migrations before production deploy. Verified complete when Infrastructure team confirms in writing that the environment contains at least 50% of production volume and a sample migration has passed against it.

**3. Query-latency runbook addition**
Owner: On-call lead (SRE team) | Deadline: November 22
Add `EXPLAIN ANALYZE` on the slowest active queries as a numbered step in the latency investigation runbook, positioned before any infrastructure scaling actions. Verified complete when the merged runbook change is confirmed by a named reviewer to place `EXPLAIN ANALYZE` before any scaling step.

**4. Latency alert includes query diagnostics snapshot**
Owner: Observability team | Deadline: December 1
PagerDuty alert payload for p99 latency breaches above 1,000ms automatically attaches slow query logs from the database statistics interface at alert fire time. Verified complete when a test alert confirms the attachment is present.

**5. Incident simulation exercise**
Owner: Engineering Manager | Deadline: November 22
Conduct one tabletop exercise with the full on-call rotation using a database-layer degradation scenario. Verified complete when the facilitator files a written summary listing at least three identified process gaps in the incident retrospectives folder by the deadline.