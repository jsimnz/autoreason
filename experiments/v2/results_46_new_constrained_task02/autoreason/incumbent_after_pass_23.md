# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped an index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across a 4-hour window on a service handling $2.3M/hour. 12,000 merchants experienced failed transactions totaling $9.2M; the majority retried successfully within 2 hours of recovery, and 847 support tickets were generated.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| — | On-call engineer scales up database replicas |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE`; missing index identified; rebuild initiated |
| 18:41 | Latency recovers to baseline |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it. Queries ran without index support, driving p99 latency from 12ms to 8,400ms and causing $9.2M in failed transactions. The staging environment held 1/1,000th of production data volume, so the missing index produced no noticeable degradation during pre-production testing, and the defective migration reached production undetected.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed, so the defect passed through the deployment pipeline without detection.

**Staging did not surface the problem.** With 1/1,000th of production data volume, query degradation from the missing index was undetectable before deployment.

**The wrong hypothesis persisted for over 3 hours.** The on-call engineer escalated to infrastructure scaling rather than query diagnostics. With Black Friday two days away, the team attributed ongoing degradation to a traffic spike. No query-level investigation ran until a senior engineer intervened at 17:52 — more than three hours into the incident.

---

## What We're Changing

**1. Escalation policy for unresolved latency incidents**
Owner: SRE On-Call Lead | Deadline: 7 days post-incident

Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation. Verified by inspection of the PagerDuty escalation policy configuration confirming a 30-minute escalation tier exists and is active on latency alerts.

**2. Mandatory post-migration index verification**
Owner: Database Platform Lead | Deadline: 30 days post-incident

All migration scripts must include a post-execution step that queries the schema to confirm required indexes exist. A CI check must fail the migration pipeline if this verification step is absent. Verified by submitting a test migration pull request without the verification step and confirming the CI pipeline fails.

**3. Higher-volume environment for migration testing**
Owner: Infrastructure Lead | Deadline: 60 days post-incident

Provision a migration testing environment containing at least 10% of production data volume. All database migrations must be validated against this environment before production deployment. Verified by environment provisioning record and updated deployment runbook requiring sign-off on migration test results from this environment.

---

**Synthesis rationale:** The timeline uses Version Y's structure — the invented 14:35 timestamp and the editorializing `~14:35–17:52` block are both removed, and the on-call scaling action appears without a fabricated time. The Summary retains Version Y's phrasing ("the majority retried successfully") to eliminate the hedging "most." The Root Cause and "What Went Wrong" sections are taken from Version X with the fourth bullet (runbook gap) removed per Version Y's correct argument that it is not derivable from the base facts. The "What We're Changing" section uses Version Y's three-item structure and its stronger, falsifiable verification for Item 2 (submitting a failing test PR rather than merely inspecting CI configuration), while retaining Version X's fuller verification language for Item 3.