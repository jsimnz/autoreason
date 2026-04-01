# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API — a service handling $2.3M/hour — for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M (most retried successfully within 2 hours of recovery), generating 847 support tickets. Correct diagnosis did not occur until 3 hours and 21 minutes after first response.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage window opens; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| 14:31 | On-call engineer responds; scales up database read replicas |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE` on slow transaction queries; identifies missing index as root cause; index rebuild begins |
| 18:41 | Index rebuilt; latency returns to 12ms baseline |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it, replacing indexed lookups with full table scans and driving p99 query latency from 12ms to 8,400ms, causing upstream timeouts across the API.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume, masking the degradation that became critical at production scale.

**The initial responder runbook contained no query-level diagnostic step.** The on-call engineer followed the existing runbook and scaled database replicas without first running query diagnostics — a gap that allowed the wrong hypothesis to persist for 3 hours and 21 minutes.

**No escalation threshold existed for unresolved latency incidents.** With Black Friday two days out, the team anchored on a traffic-spike diagnosis. No policy required senior engineer involvement until 17:52, when one joined voluntarily.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Database Platform team | Deadline: December 1
All migration scripts must include a post-execution step confirming required indexes exist. CI blocks merges on any migration script missing this check. *Verified complete when a pull request omitting the check is rejected by CI, with that rejection visible in the pipeline dashboard.*

**2. Production-scale shadow database for migration testing**
Owner: Infrastructure team | Deadline: December 15
Provision a shadow environment refreshed weekly at no less than 50% of current production data volume, required as a gate for all schema migrations before production deploy. *Verified complete when (a) a sample migration's passing run against this environment is recorded in the CI/CD pipeline dashboard showing row count at or above the 50% threshold, and (b) the automated weekly refresh job has executed successfully at least twice, confirmed by scheduler logs.*

**3. Query diagnostics step added to on-call runbook**
Owner: On-call lead (SRE team) | Deadline: November 22
The latency incident runbook must require `EXPLAIN ANALYZE` on the slowest active queries as a numbered step before any infrastructure scaling action. *Verified complete when the merged runbook contains `EXPLAIN ANALYZE` as a numbered step preceding any scaling action, and a synthetic latency incident drill confirms the on-call engineer executed that step first, with results posted to the incident retrospectives wiki.*

**4. Escalation threshold for unresolved latency incidents**
Owner: On-call lead (SRE team) | Deadline: November 22
Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation via PagerDuty escalation policy. *Verified complete when the PagerDuty escalation policy is updated with the 30-minute rule and a test alert confirms the escalation fires to the senior engineer tier at the 30-minute mark.*

**5. Latency alert includes query diagnostics snapshot**
Owner: Observability team | Deadline: December 1
PagerDuty alert payload for p99 latency breaches above 1,000ms automatically attaches slow query logs at alert fire time. *Verified complete when the Observability team lead triggers a synthetic test alert and posts a screenshot of the resulting payload — including the slow query attachment — to the incident retrospectives wiki.*