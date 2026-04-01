# Payment API Outage — Tuesday, November 19 — 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the transactions table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M, most of which retried successfully within 2 hours of recovery. An incorrect initial diagnosis extended the outage by approximately 3 hours.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Migration script runs in production; index on `transactions` table dropped; query latency begins climbing |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms; on-call engineer responds and scales up database read replicas |
| 14:31–17:52 | Team investigates under traffic-spike hypothesis with Black Friday two days out; infrastructure-level remediation attempts continue without improvement |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE` on slow transaction queries; identifies missing index as root cause |
| 18:41 | Index rebuilt; latency recovers; service restored |

---

## Root Cause

The production migration script executed a schema change that dropped an index on the `transactions` table without recreating it. Without the index, full table scans replaced indexed lookups, driving p99 query latency from 12ms to 8,400ms and causing upstream timeouts across the API.

---

## What Went Wrong

**The migration script had no index verification step.** No pre- or post-migration check confirmed that required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume. The missing index went undetected on staging because the reduced data volume masked the performance degradation that became critical at production scale.

**The wrong mental model held for 3 hours.** With Black Friday two days out, the team anchored on a traffic-spike hypothesis. Query-level diagnostics were not run until a senior engineer joined the investigation 3 hours into the incident.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Database Platform team | Deadline: December 1
All migration scripts must include a post-execution step that confirms all required indexes exist after the script completes. The CI pipeline blocks merges on any migration script missing this check. Pass/fail results are logged per deployment.

**2. Production-scale shadow database for migration testing**
Owner: Infrastructure team | Deadline: December 15
Provision a shadow environment refreshed weekly at a data volume orders of magnitude closer to production than current staging, used as a required gate for all schema migrations before production deploy. Verified complete when the first migration is blocked from production until it passes the shadow gate.

**3. Query-latency runbook addition**
Owner: On-call lead (SRE team) | Deadline: November 22
Add `EXPLAIN ANALYZE` on the slowest active queries as an early step in the latency investigation runbook, executed before any infrastructure scaling actions. Verified complete when the updated runbook is merged to the internal wiki.

**4. Latency alert includes query diagnostics snapshot**
Owner: Observability team | Deadline: December 1
PagerDuty alert payload for p99 latency breaches above 1,000ms automatically attaches slow query logs from the database statistics interface at alert fire time. Verified complete when a test alert confirms the attachment is present.

**5. Incident simulation exercise**
Owner: Engineering Manager | Deadline: November 22
Conduct one tabletop exercise with the full on-call rotation using a database-layer degradation scenario. Verified complete when the facilitator submits a written summary to the Engineering Manager that includes a documented list of at least three identified process gaps.