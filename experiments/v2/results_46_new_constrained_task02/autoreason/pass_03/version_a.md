# Payment API Outage — Tuesday, November 19 — 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the transactions table, causing query latency to spike from 12ms to 8,400ms and causing widespread transaction failures across the payment processing API for 4 hours and 18 minutes. The service processes $2.3M per hour in transactions; 12,000 merchants experienced failed transactions totaling $9.2M, most of which retried successfully within 2 hours of recovery. An incorrect initial diagnosis extended the outage by 3 hours.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Migration script runs in production; index on `transactions` table dropped; query latency begins climbing |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms (8 minutes after onset) |
| 14:31–17:52 | On-call engineer responds; attributes degradation to pre–Black Friday traffic surge; scales up database read replicas; latency does not improve |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE` on a slow transaction query; identifies missing index as root cause |
| 18:41 | p99 latency returns to 12ms baseline; all merchants restored |

---

## Root Cause

The production migration script executed a schema change that dropped an index on the `transactions` table without recreating it. Without the index, full table scans replaced indexed lookups, driving p99 query latency from 12ms to 8,400ms and causing upstream timeouts across the API.

---

## What Went Wrong

**The migration script had no index verification step.** No pre- or post-migration check confirmed that required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume. A full table scan on staging completed fast enough to stay below alert thresholds; the same scan on production was slow enough to cause timeouts.

**The wrong mental model held for 3 hours.** With Black Friday 2 days out, the team anchored on a traffic spike hypothesis. Query-level diagnostics (`EXPLAIN ANALYZE`) were not run until a senior engineer joined the investigation 3 hours and 21 minutes into the incident.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Database Platform team | Deadline: December 1
All migration scripts must include a post-execution step that queries `pg_indexes` and fails the deployment if any index listed in a required-indexes manifest is absent. CI pipeline blocks merges without this check.

**2. Production-scale shadow database for migration testing**
Owner: Infrastructure team | Deadline: December 15
Provision a continuously refreshed shadow environment at ≥10% of production data volume, used as a required gate for all schema migrations before production deploy.

**3. Query-latency runbook update**
Owner: On-call lead (SRE team) | Deadline: November 22
Add `EXPLAIN ANALYZE` on the top-5 slowest queries as step 2 in the latency investigation runbook, executed before any infrastructure scaling actions.

**4. Latency alert includes query diagnostics snapshot**
Owner: Observability team | Deadline: December 1
PagerDuty alert payload for p99 latency breaches above 1,000ms automatically attaches the top 10 slow query logs from `pg_stat_statements` at alert fire time.

**5. Incident simulation exercise**
Owner: Engineering Manager | Deadline: November 22
Run one tabletop exercise with full on-call rotation attendance using a database-layer degradation scenario. Exercise is complete when all participants have correctly identified a missing index as root cause using query diagnostics before attempting any infrastructure scaling action, as confirmed by the facilitator's written summary.