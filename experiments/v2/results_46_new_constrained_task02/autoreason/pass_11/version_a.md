# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API — a service handling $2.3M/hour — for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M, with transactions retrying successfully within 2 hours of recovery, generating 847 support tickets. Correct diagnosis did not occur until 3 hours after first response.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms; on-call engineer scales up database read replicas |
| ~14:31–17:52 | Team diagnoses incident as traffic spike with Black Friday two days out; infrastructure scaling actions continue without improvement |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE`; identifies missing index; index rebuild begins |
| 18:41 | Index rebuilt; latency returns to 12ms baseline |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it, replacing indexed lookups with full table scans and driving p99 query latency from 12ms to 8,400ms, causing upstream timeouts across the API.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume, masking degradation that became critical at production scale.

**The runbook contained no query-level diagnostic step.** The on-call engineer followed the existing runbook and scaled replicas without running query diagnostics, allowing the wrong hypothesis to persist for 3 hours.

**No escalation threshold existed for unresolved latency incidents.** No policy required senior engineer involvement; escalation at 17:52 was voluntary.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Database Platform team | Deadline: December 1
All migration scripts must include a post-execution step confirming required indexes exist. CI blocks merges on any migration script missing this check. *Verified complete when a pull request omitting the check is rejected by CI, visible in the pipeline dashboard.*

**2. Production-scale shadow database for migration testing**
Owner: Infrastructure team | Deadline: December 15
Provision a shadow environment at no less than 50% of production data volume, refreshed weekly starting December 1, required as a gate for all schema migrations before production deploy. *Verified complete when (a) the CI/CD pipeline shows a sample migration run against this environment with row count at or above the 50% threshold, and (b) the weekly refresh job has executed successfully at least twice by December 15, confirmed by scheduler logs.*

**3. Query diagnostics step added to on-call runbook**
Owner: On-call lead (SRE team) | Deadline: November 22
The latency incident runbook must require `EXPLAIN ANALYZE` on the slowest active queries as a numbered step before any infrastructure scaling action. *Verified complete when the merged runbook contains `EXPLAIN ANALYZE` as a numbered step preceding any scaling action, and a synthetic drill conducted by December 22 confirms the on-call engineer executed that step first, with results posted to the incident retrospectives wiki.*

**4. Escalation threshold for unresolved latency incidents**
Owner: On-call lead (SRE team) | Deadline: November 22
Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation via PagerDuty. *Verified complete when the PagerDuty escalation policy is updated with the 30-minute rule and a test alert confirms escalation fires to the senior engineer tier at the 30-minute mark.*

**5. Latency alert includes query diagnostics snapshot**
Owner: Observability team | Deadline: December 1
PagerDuty alerts for p99 latency above 1,000ms automatically attach slow query logs at fire time. *Verified complete when the Observability team lead triggers a synthetic test alert and posts the resulting payload — including the slow query attachment — to the incident retrospectives wiki.*