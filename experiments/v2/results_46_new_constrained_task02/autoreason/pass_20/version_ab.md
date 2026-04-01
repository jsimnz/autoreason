# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped an index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures for 4 hours on a service handling $2.3M/hour. 12,000 merchants experienced failed transactions totaling $9.2M, and 847 support tickets were generated; most failed transactions retried successfully within 2 hours of recovery.

---

## Timeline

| Time (UTC) | Event |
| --- | --- |
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| 14:35 | On-call engineer scales up database read replicas |
| 14:35–17:52 | Team operates under traffic-spike hypothesis; no query-level diagnostics run |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE`; missing index identified; rebuild initiated |
| 18:20 | Index rebuild completes |
| 18:41 | Latency recovers to baseline |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it. Queries ran without index support, driving p99 latency from 12ms to 8,400ms and causing transaction failures. The staging environment held 1/1,000th of production data volume, so the missing index produced no noticeable degradation during pre-production testing and the defective migration reached production undetected.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** With 1/1,000th of production data volume, query degradation from the missing index was undetectable in staging.

**The wrong hypothesis persisted for over 3 hours.** The team attributed continued degradation to pre-Black Friday traffic volume. No query-level diagnostics ran until a senior engineer intervened at 17:52.

**No escalation threshold existed for unresolved latency incidents.** No policy required senior engineer involvement within a defined timeframe, allowing the misdiagnosis to continue unchecked.

---

## What We're Changing

**1. Query diagnostics added to on-call runbook**
Owner: SRE On-Call Lead | Deadline: 7 days post-incident

The latency runbook must include `EXPLAIN ANALYZE` on the slowest active queries as a required numbered step that must be completed before any infrastructure scaling action. Verified by the SRE On-Call Lead confirming in writing the specific step number and its position preceding any scaling step in the published runbook.

**2. Escalation policy for unresolved latency incidents**
Owner: SRE On-Call Lead | Deadline: 7 days post-incident

Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation via a PagerDuty escalation tier named "Latency-30min." Verified by inspection of the PagerDuty policy configuration and a test alert record — owned by the SRE On-Call Lead and filed in the incident retrospective folder — confirming the tier fires correctly.

**3. Mandatory post-migration index verification**
Owner: Database Platform Lead | Deadline: 30 days post-incident

All migration scripts must include a post-execution step that queries the schema to confirm required indexes exist. A CI check must fail the migration pipeline if this verification step is absent. Verified by CI configuration showing the check is enforced on all database migration pull requests.

**4. Higher-volume environment for migration testing**
Owner: Infrastructure Lead | Deadline: 60 days post-incident

Provision a migration testing environment containing at least 10% of production data volume. All database migrations must be validated against this environment before production deployment. Verified by environment provisioning record and updated deployment runbook.