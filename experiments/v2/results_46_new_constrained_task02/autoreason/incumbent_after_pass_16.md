# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped an index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API — a service handling $2.3M/hour — for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M, and 847 support tickets were generated; most failed transactions retried successfully within 2 hours of recovery.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| 14:31 | On-call engineer scales up database read replicas |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE`; identifies missing index; rebuild initiated |
| 18:41 | Latency recovers |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it. Queries against the table executed without index support, driving p99 latency from 12ms to 8,400ms and causing transaction failures across the API. The staging environment held 1/1,000th of production data volume, so the missing index produced no noticeable degradation during pre-production testing, allowing the defective migration to reach production undetected.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume, masking degradation that only became critical at production scale.

**The runbook contained no query-level diagnostic step.** The on-call engineer followed the existing runbook and scaled replicas without running query diagnostics.

**Black Friday proximity caused misdiagnosis.** With Black Friday two days away, the team attributed elevated latency to a traffic spike rather than a schema change, allowing the wrong hypothesis to persist for over 3 hours.

**No escalation threshold existed for unresolved latency incidents.** No policy required senior engineer involvement within a defined timeframe.

---

## What We're Changing

**1. Query diagnostics step added to on-call runbook**
Owner: On-call lead (SRE team) | Deadline: Within 7 days of incident
The latency incident runbook must require `EXPLAIN ANALYZE` on the slowest active queries as a numbered step before any infrastructure scaling action.

**2. Escalation threshold for unresolved latency incidents**
Owner: On-call lead (SRE team) | Deadline: Within 7 days of incident
Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation via PagerDuty, enforced by a configured escalation policy.

**3. Mandatory post-migration index verification**
Owner: Database Platform team | Deadline: Within 30 days of incident
All migration scripts must include a post-execution step confirming required indexes exist. CI blocks merges on any migration missing this check.

**4. Production-scale shadow environment for migration testing**
Owner: Infrastructure team | Deadline: Within 60 days of incident
Provision a shadow environment at no less than 1/10th production data volume, refreshed weekly. The CI pipeline blocks production migration deploys for any migration not run against the shadow environment.