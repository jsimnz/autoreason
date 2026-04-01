I'll address each problem in turn, then present the revised document.

**Changes made and which problem each fixes:**

1. **Removed "most of which retried successfully within 2 hours of recovery" from Root Cause** — fixes the duplicate hedging language violation. The phrase is retained once in Summary (it is a base fact) but removed from Root Cause to eliminate the duplicate and reduce word count.

2. **Removed the "14:31 onward — 847 support tickets" timeline row** — fixes the fabricated timeline detail. The ticket count appears in Summary as an impact metric, which is where the base facts place it.

3. **Added a timeline entry noting the scaling attempt did not resolve the issue and the team attributed degradation to pre-Black Friday traffic** — fixes the omission of the wrong-diagnosis period from the timeline.

4. **Replaced the invented PagerDuty tier name "Latency-30min," removed "filed in the incident retrospective folder," and removed "an engineer other than the owner"** — fixes the three fabricated details and the falsifiability problem they caused. Verification is now inspectable against objective, real criteria.

5. **Rewrote "What Went Wrong" to remove restatement of Root Cause content** — fixes the structural overlap. Root Cause now owns the mechanical explanation; What Went Wrong focuses on the process failures that allowed the mechanical failure to occur and persist.

6. **Changed "read replicas" back to "replicas"** — fixes the addition of the word "read," which is not in the base facts.

7. **Trimmed language throughout to bring the document under 600 words** — fixes the word count violation.

---

# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped an index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across a 4-hour window on a service handling $2.3M/hour. 12,000 merchants experienced failed transactions totaling $9.2M, most of which retried successfully within 2 hours of recovery, and 847 support tickets were generated.

---

## Timeline

| Time (UTC) | Event |
| --- | --- |
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| 14:35 | On-call engineer scales up database replicas |
| ~14:35–17:52 | Scaling provides no relief; team attributes ongoing degradation to pre-Black Friday traffic spike; no query-level diagnostics run |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE`; missing index identified; rebuild initiated |
| 18:41 | Latency recovers to baseline |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it. Queries ran without index support, driving p99 latency from 12ms to 8,400ms and causing $9.2M in failed transactions. The staging environment held 1/1,000th of production data volume, so the missing index produced no noticeable degradation during pre-production testing and the defective migration reached production undetected.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed, so the defect passed through the deployment pipeline without detection.

**The wrong hypothesis persisted for over 3 hours.** The on-call engineer escalated to infrastructure scaling rather than query diagnostics. With Black Friday two days away, the team attributed ongoing degradation to a traffic spike. No query-level investigation ran until a senior engineer intervened at 17:52 — more than three hours into the incident.

**The on-call runbook did not require query diagnostics before infrastructure actions.** Nothing in the existing runbook directed engineers to examine query execution plans as a first step, which allowed the incorrect diagnosis to go unchallenged.

---

## What We're Changing

**1. Query diagnostics added to on-call runbook**
Owner: SRE On-Call Lead | Deadline: 7 days post-incident

The latency runbook must include `EXPLAIN ANALYZE` on the slowest active queries as a required numbered step that precedes any infrastructure scaling action. Verified by inspection of the published runbook confirming `EXPLAIN ANALYZE` appears as a discrete numbered step before any scaling step.

**2. Escalation policy for unresolved latency incidents**
Owner: SRE On-Call Lead | Deadline: 7 days post-incident

Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation. Verified by inspection of the PagerDuty escalation policy configuration confirming a 30-minute escalation tier exists and is active on latency alerts.

**3. Mandatory post-migration index verification**
Owner: Database Platform Lead | Deadline: 30 days post-incident

All migration scripts must include a post-execution step that queries the schema to confirm required indexes exist. A CI check must fail the migration pipeline if this verification step is absent. Verified by CI configuration showing the check is enforced on all database migration pull requests.

**4. Higher-volume environment for migration testing**
Owner: Infrastructure Lead | Deadline: 60 days post-incident

Provision a migration testing environment containing at least 10% of production data volume. All database migrations must be validated against this environment before production deployment. Verified by environment provisioning record and updated deployment runbook.