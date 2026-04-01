I'll address each problem, then produce the revised document.

**Changes made and why:**

1. **Problem 1** — Removed the entire meta-commentary preamble. The deliverable is the postmortem only.

2. **Problem 2** — Removed the duration-spanning timeline entry "14:31–17:52." The base facts provide no discrete events within this window. The gap is implicit from the surrounding timestamps and is explained in "What Went Wrong."

3. **Problems 3, 4, 5** — Removed all fabricated calendar dates. The base facts do not provide the incident's calendar date, only that Black Friday was two days away. Deadlines are now expressed as day-counts from the incident date (e.g., "within 7 days," "within 30 days," "within 60 days"), which are falsifiable and derivable.

4. **Problem 6** — With the preamble removed and dates simplified, word count is well within 600 words.

5. **Problem 7** — Removed the qualitative outcome criterion ("sufficient that a missing index produces measurable query degradation"). Item 2's falsifiable criteria are now only the checkable threshold (1/10th production data volume) and weekly refresh cadence.

6. **Problem 8** — Added the staging environment gap to the Root Cause section as a contributing condition that allowed the proximate cause to reach production.

---

# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API — a service handling $2.3M/hour — for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M, and 847 support tickets were generated; most failed transactions retried successfully within 2 hours of recovery.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms; on-call engineer scales up database read replicas, citing anticipated Black Friday traffic |
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
Provision a shadow environment at no less than 1/10th production data volume, refreshed weekly, required as a gate for all schema migrations before production deploy.