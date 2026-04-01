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

---

**Synthesis rationale by dimension:**

- **Summary:** Identical across both versions; retained as written.
- **Timeline:** Version Y's four-row table is stronger. The spanning entry "14:31–17:52" in Version X editorializes a gap rather than recording discrete events; that gap is correctly explained in What Went Wrong. Version Y's cleaner structure is adopted.
- **Root Cause:** Version Y is stronger. It integrates the staging environment gap as a contributing condition within the root cause itself, which is the correct analytical placement — it explains how the proximate cause reached production. Version X defers this entirely to What Went Wrong, creating mild redundancy without analytical gain.
- **What Went Wrong:** Identical across both versions; retained as written.
- **Remediation ordering:** Version Y's ordering is stronger. Items 1 and 2 (runbook and escalation policy) are the fastest to implement and directly address the 3-hour diagnostic delay — the most operationally acute failure. Structural fixes (index verification, shadow environment) follow by complexity and lead time. Version X's ordering placed the longer-lead infrastructure items first without a clear rationale.
- **Deadlines:** Version Y's relative day-counts ("within 7 days," "within 30 days," "within 60 days") are adopted. They are falsifiable, derivable from the base facts, and avoid fabricating calendar dates not present in the source material — the central integrity problem with Version X's approach.
- **Item 2 shadow environment spec:** Version X's qualitative criterion ("sufficient that a missing index produces measurable query degradation") was correctly flagged by Version Y as non-falsifiable. Version Y's checkable threshold (1/10th production volume, weekly refresh) is retained. The qualitative language is dropped.