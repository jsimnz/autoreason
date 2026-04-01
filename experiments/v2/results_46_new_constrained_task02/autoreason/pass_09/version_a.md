# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API — a service handling $2.3M/hour — for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M (most retried successfully within 2 hours of recovery), generating 847 support tickets. Three hours and 21 minutes elapsed between first response and correct diagnosis.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Migration script runs in production; index on `transactions` table dropped; query latency begins climbing |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| 14:31 | On-call engineer responds; scales up database read replicas; latency does not improve |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE` on slow transaction queries; identifies missing index as root cause |
| 18:41 | Index rebuilt; latency returns to baseline |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it, replacing indexed lookups with full table scans and driving p99 query latency from 12ms to 8,400ms, causing upstream timeouts across the API.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume, masking the degradation that became critical at production scale.

**The wrong hypothesis held for 3 hours and 21 minutes.** With Black Friday two days out, the team anchored on a traffic-spike diagnosis. Query-level diagnostics were not run until a senior engineer joined the investigation 3 hours and 21 minutes after first response. No escalation threshold existed to trigger earlier senior involvement.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Database Platform team | Deadline: December 1
All migration scripts must include a post-execution step confirming required indexes exist. CI blocks merges on any migration script missing this check. Verified complete when a pull request omitting the check is confirmed rejected by CI, with that rejection visible in the pipeline dashboard.

**2. Production-scale shadow database for migration testing**
Owner: Infrastructure team | Deadline: December 15
Provision a shadow environment refreshed weekly at no less than 50% of current production data volume, required as a gate for all schema migrations before production deploy. Verified complete when a sample migration's passing run against this environment is recorded in the CI/CD pipeline dashboard showing the environment's row count at or above the 50% threshold.

**3. Escalation threshold for unresolved latency incidents**
Owner: On-call lead (SRE team) | Deadline: November 22
Any p99 latency incident unresolved after 30 minutes requires immediate senior engineer escalation and mandates `EXPLAIN ANALYZE` on the slowest active queries before any further infrastructure scaling. Verified complete when the merged runbook contains both the 30-minute escalation rule and `EXPLAIN ANALYZE` as a numbered step preceding any scaling action.

**4. Latency alert includes query diagnostics snapshot**
Owner: Observability team | Deadline: December 1
PagerDuty alert payload for p99 latency breaches above 1,000ms automatically attaches slow query logs at alert fire time. Verified complete when the Observability team lead triggers a synthetic test alert in the staging PagerDuty environment and posts a screenshot of the resulting payload, including the slow query attachment, to the team's incident retrospectives wiki page.

**5. Incident simulation exercise**
Owner: Engineering Manager | Deadline: November 22
Conduct one tabletop exercise with the full on-call rotation using a database-layer degradation scenario. Verified complete when the facilitator posts a written summary with a concrete action-item list to the team's incident retrospectives wiki page by the deadline.