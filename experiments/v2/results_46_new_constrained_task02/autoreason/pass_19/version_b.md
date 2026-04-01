I'll address each problem in turn, then present the revised document.

**Problem 1 (Word count):** Cut words throughout, primarily in Root Cause, What Went Wrong, and What We're Changing prose.

**Problem 2 (Missing timestamp):** The base facts don't provide an exact timestamp for the replica scaling attempt, only that it followed the 14:31 alert. I'll assign it "~14:35" as the closest defensible approximation derivable from the facts (it was the first response after the alert), and note the constraint requires chronological ordering.

*Actually, the base facts give no timestamp for the first response beyond "after 14:31." Inventing a specific time would violate the "add nothing not derivable" constraint. The correct fix is to attach the action to the 14:31 row, since it was the immediate first response to that alert, rather than leaving it unanchored.*

**Problem 3 (Item 3 not fully falsifiable):** Change verification to require a passing CI check that validates index existence post-migration, not merely the presence of a checklist item.

**Problem 4 (Invented 1,000ms figure):** Remove the specific latency threshold; state only the 10% data volume requirement.

**Problem 5 (Editorializing in timeline):** Rewrite the 14:31–17:52 row to state only what the team did, not what they failed to do.

**Problem 6 (4 hours 18 minutes):** Change to "4 hours" to match the base facts framing.

**Problem 7 (Escalation policy falsifiability):** Add a requirement for a test page to verify the policy fires correctly.

---

# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped an index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures for 4 hours on a service handling $2.3M/hour. 12,000 merchants experienced failed transactions totaling $9.2M, and 847 support tickets were generated; most failed transactions retried successfully within 2 hours of recovery.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms; on-call engineer scales up database read replicas; latency does not improve |
| 14:31–17:52 | Team attributes degradation to pre-Black Friday traffic spike |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE`; identifies missing index; rebuild initiated |
| 18:41 | Latency recovers to baseline |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it. Queries ran without index support, driving p99 latency from 12ms to 8,400ms and causing transaction failures. The staging environment held 1/1,000th of production data volume, so the missing index produced no detectable degradation during pre-production testing and the defective migration reached production undetected.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** With 1/1,000th of production data volume, query degradation from the missing index was undetectable in staging.

**The wrong hypothesis persisted for over 3 hours.** The team attributed continued degradation to pre-Black Friday traffic. No query-level diagnostics ran until a senior engineer intervened at 17:52.

**No escalation threshold existed for unresolved latency incidents.** No policy required senior engineer involvement within a defined timeframe, allowing the misdiagnosis to continue unchecked.

---

## What We're Changing

**1. Query diagnostics added to on-call runbook**
Owner: SRE On-Call Lead | Deadline: 7 days post-incident

The latency runbook must include `EXPLAIN ANALYZE` on the slowest active queries as a required numbered step before any infrastructure scaling action. Verified by runbook diff in version control.

**2. Escalation policy for unresolved latency incidents**
Owner: SRE On-Call Lead | Deadline: 7 days post-incident

Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation via a PagerDuty escalation tier named "Latency-30min." Verified by inspection of PagerDuty policy configuration and a documented test page confirming the tier fires correctly.

**3. Mandatory post-migration index verification**
Owner: Database Platform Lead | Deadline: 30 days post-incident

All migration scripts must include a post-execution step that queries the schema to confirm required indexes exist. A CI check must fail the migration pipeline if this verification step is absent. Verified by CI configuration showing the check is enforced on all database migration pull requests.

**4. Higher-volume environment for migration testing**
Owner: Infrastructure Lead | Deadline: 60 days post-incident

Provision a migration testing environment containing at least 10% of production data volume. All database migrations must be validated against this environment before production deployment. Verified by environment provisioning record and updated deployment runbook.