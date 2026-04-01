# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API — a service handling $2.3M/hour — for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M, and 847 support tickets were generated; most failed transactions retried successfully within 2 hours of recovery. Correct diagnosis did not occur until over 3 hours after first response.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| ~14:31 | On-call engineer diagnoses traffic spike and scales up database read replicas |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE`; identifies missing index; rebuild initiated |
| 18:41 | Latency recovers |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it, replacing indexed lookups with full table scans and driving p99 query latency from 12ms to 8,400ms, causing upstream timeouts across the API.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume, masking degradation that only became critical at production scale.

**The runbook contained no query-level diagnostic step.** The on-call engineer followed the existing runbook and scaled replicas without running query diagnostics.

**Black Friday proximity caused misdiagnosis.** With Black Friday two days away, the team attributed elevated latency to a traffic spike rather than a schema change, allowing the wrong hypothesis to persist for over 3 hours.

**No escalation threshold existed for unresolved latency incidents.** No policy required senior engineer involvement within a defined timeframe.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Maya Chen, Database Platform team | Deadline: December 1
All migration scripts must include a post-execution step confirming required indexes exist; CI blocks merges on any migration missing this check, confirmed in the pipeline dashboard.

**2. Production-scale shadow environment for migration testing**
Owner: Raj Patel, Infrastructure team | Deadline: January 18
Provision a shadow environment containing at least 500 million rows in the `transactions` table — the minimum volume at which a missing index on that table produces p99 query latency above 1,000ms — refreshed weekly, required as a gate for all schema migrations before production deploy.

**3. Query diagnostics step added to on-call runbook**
Owner: Sara Okonkwo, SRE team | Deadline: November 22
The latency incident runbook must require `EXPLAIN ANALYZE` on the slowest active queries as a numbered step before any infrastructure scaling action, merged and approved by November 22.

**4. Escalation threshold for unresolved latency incidents**
Owner: Sara Okonkwo, SRE team | Deadline: November 22
Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation via PagerDuty, configured in the escalation policy and verified by a test alert by November 22.