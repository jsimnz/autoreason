I'll address each problem systematically, then produce the revised document.

**Changes made and which problem each fixes:**

1. **Removed "November 19"** — fixes "date not derivable from base facts"
2. **Removed "approximately"** — fixes hedging language constraint violation
3. **Split the 14:31–17:52 range into discrete timestamped rows** — fixes timeline editorializing and missing timestamped first-response row
4. **Removed "Black Friday two days out" from Timeline** (it remains only in What Went Wrong) — fixes unnecessary repetition contributing to word count
5. **Trimmed Root Cause to remove duplication with What Went Wrong** — fixes redundant content and reduces word count
6. **Replaced "orders of magnitude closer to production" with a specific measurable target** — fixes vague, non-falsifiable remediation item #2
7. **Rewrote remediation item #2's verification condition** to confirm provisioning at the specified volume, not just gate behavior — fixes conflation of deployment gate with provisioning
8. **Rewrote remediation item #5's verification condition** to add an independent check — fixes self-reporting loop
9. **Cut words throughout to reach ≤600** — fixes word count violation

---

# Payment API Outage — Tuesday [date redacted pending confirmation] — 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the transactions table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M, most of which retried successfully within 2 hours of recovery. An incorrect initial diagnosis extended the outage by 3 hours.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Migration script runs in production; index on `transactions` table dropped; query latency begins climbing |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| 14:31 | On-call engineer responds; scales up database read replicas; latency does not improve |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE` on slow transaction queries; identifies missing index as root cause |
| 18:41 | Index rebuilt; latency recovers; service restored |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it, replacing indexed lookups with full table scans and driving p99 query latency from 12ms to 8,400ms.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume, masking the performance degradation that became critical at production scale.

**The wrong mental model held for 3 hours.** With Black Friday two days out, the team anchored on a traffic-spike hypothesis. Query-level diagnostics were not run until a senior engineer joined the investigation 3 hours into the incident.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Database Platform team | Deadline: December 1
All migration scripts must include a post-execution step confirming all required indexes exist. The CI pipeline blocks merges on any migration script missing this check. Verified complete when the CI block is active and blocking a test migration that omits the check.

**2. Production-scale shadow database for migration testing**
Owner: Infrastructure team | Deadline: December 15
Provision a shadow environment refreshed weekly at no less than 50% of current production data volume, required as a gate for all schema migrations before production deploy. Verified complete when Infrastructure team confirms in writing that the environment contains at least 50% of production volume and a sample migration has been run and passed against it.

**3. Query-latency runbook addition**
Owner: On-call lead (SRE team) | Deadline: November 22
Add `EXPLAIN ANALYZE` on the slowest active queries as an early step in the latency investigation runbook, executed before any infrastructure scaling actions. Verified complete when the updated runbook is merged to the internal wiki.

**4. Latency alert includes query diagnostics snapshot**
Owner: Observability team | Deadline: December 1
PagerDuty alert payload for p99 latency breaches above 1,000ms automatically attaches slow query logs at alert fire time. Verified complete when a test alert confirms the attachment is present.

**5. Incident simulation exercise**
Owner: Engineering Manager | Deadline: November 22
Conduct one tabletop exercise with the full on-call rotation using a database-layer degradation scenario. Verified complete when the facilitator submits a written summary to a VP-level stakeholder outside the on-call rotation, including a documented list of at least three identified process gaps, and that stakeholder confirms receipt in writing.