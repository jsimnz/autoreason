# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API — a service handling $2.3M/hour — for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M, and 847 support tickets were generated; most failed transactions retried successfully within 2 hours of recovery. Correct diagnosis did not occur until over 3 hours after first response.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms; on-call engineer diagnoses traffic spike (Black Friday 2 days away) and scales up database read replicas |
| 14:31–17:52 | Replica scaling does not resolve latency; traffic spike hypothesis persists |
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
Owner: Database Platform team | Deadline: December 1
All migration scripts must include a post-execution step confirming required indexes exist; CI blocks merges on any migration missing this check, confirmed in the pipeline dashboard.

**2. Production-representative shadow environment for migration testing**
Owner: Infrastructure team | Deadline: 60 days from incident date
Provision a shadow environment at sufficient data volume that a missing index on the `transactions` table produces measurable query degradation, refreshed weekly, required as a gate for all schema migrations before production deploy. Verified when the CI/CD pipeline shows a sample migration executed against this environment and the weekly refresh job has run successfully at least twice, confirmed by scheduler logs.

**3. Query diagnostics step added to on-call runbook**
Owner: On-call lead (SRE team) | Deadline: November 22
The latency incident runbook must require `EXPLAIN ANALYZE` on the slowest active queries as a numbered step before any infrastructure scaling action. Verified when the merged runbook pull request, approved by November 22, contains `EXPLAIN ANALYZE` as a numbered step preceding any scaling action.

**4. Escalation threshold for unresolved latency incidents**
Owner: On-call lead (SRE team) | Deadline: November 22
Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation via PagerDuty. Verified when the PagerDuty escalation policy reflects the 30-minute rule and a test alert confirms escalation fires to the senior engineer tier at the 30-minute mark.