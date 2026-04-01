# Payment API Outage — November (Tuesday) 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the transactions table, causing query latency to spike 700x and rendering the payment processing API unavailable for 4 hours. Twelve thousand merchants experienced failed transactions totaling $9.2M in gross volume, most of which retried successfully within 2 hours of service restoration. An incorrect initial diagnosis extended the outage by approximately 3 hours.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Migration script runs in production; index on `transactions` table dropped; query latency begins climbing |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms (8 minutes after onset) |
| 14:35 | On-call engineer begins investigation; attributes degradation to pre–Black Friday traffic surge |
| 14:50 | On-call engineer scales up database read replicas; no latency improvement observed |
| 15:10–17:45 | Team continues investigating under traffic spike assumption; infrastructure-level responses attempted; no improvement observed |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE` on a slow transaction query; identifies missing index as root cause; index rebuild initiated |
| 18:41 | p99 latency returns to baseline (12ms); all merchants restored |

---

## Root Cause

The production migration script executed a schema change that dropped an index on the `transactions` table without recreating it. Without the index, full table scans replaced indexed lookups, driving p99 query latency from 12ms to 8,400ms and causing upstream timeouts across the API.

---

## What Went Wrong

**The migration script had no index verification step.** No pre- or post-migration check confirmed that required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume. A full table scan on staging completed fast enough to stay below alert thresholds; the same scan on production was catastrophically slow.

**The wrong mental model held for 3 hours.** With Black Friday 2 days out, the team anchored on a traffic spike hypothesis. No one ran query-level diagnostics (`EXPLAIN ANALYZE`) until a senior engineer intervened 3 hours and 29 minutes into the incident.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Database Platform team
Deadline: December 1
Action: All migration scripts must include a post-execution step that queries `pg_indexes` and fails the deployment if any index listed in a required-indexes manifest is absent. CI pipeline blocks merges without this check.

**2. Production-scale shadow database for migration testing**
Owner: Infrastructure team
Deadline: December 15
Action: Provision a continuously refreshed shadow environment at ≥10% of production data volume, used as a required gate for all schema migrations before production deploy.

**3. Query-latency runbook update**
Owner: On-call lead (SRE team)
Deadline: November 22
Action: Add `EXPLAIN ANALYZE` on the top-5 slowest queries as step 2 in the latency investigation runbook, executed before any infrastructure scaling actions.

**4. Latency alert includes query diagnostics snapshot**
Owner: Observability team
Deadline: December 1
Action: PagerDuty alert payload for p99 latency breaches above 1,000ms automatically attaches the top 10 slow query logs from `pg_stat_statements` at alert fire time.

**5. Incident simulation exercise**
Owner: Engineering Manager
Deadline: November 22
Action: Run one tabletop exercise with the on-call rotation using a database-layer degradation scenario to practice query-level diagnosis before scaling responses.