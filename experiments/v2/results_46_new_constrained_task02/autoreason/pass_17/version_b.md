I'll address each identified problem, then provide the revised document.

**Changes made and problems addressed:**

1. **Word count violation** — Tightened prose throughout, primarily in Root Cause, What Went Wrong, and What We're Changing, to bring the document under 600 words.

2. **Timeline 3-hour gap / factual omission** — Added an entry at ~14:35 noting the replica scaling produced no improvement, and an entry capturing the sustained wrong-diagnosis period. This addresses the omission of the wrong-diagnosis period without editorializing (stating facts, not judgments).

3. **Scaling action not noted as ineffective in What Went Wrong** — Added an explicit statement that scaling replicas did not resolve latency, and that this wrong hypothesis persisted for over 3 hours.

4. **Remediation #4: invented "1/10th" threshold and "refreshed weekly" cadence** — Removed the specific 1/10th threshold and weekly refresh cadence, replacing with language derivable from the base facts: that the environment must hold sufficient data volume to surface index-dependent query degradation.

5. **Remediation #3: invented CI mechanism** — Removed the specific claim about CI blocking merges, replacing with a falsifiable but facts-derivable requirement: that the verification step must exist in the script and be confirmed in a migration review checklist.

6. **Owner names vs. team names** — Replaced team-level owners with specific role titles (e.g., "SRE On-Call Lead," "Database Platform Lead," "Infrastructure Lead") to assign individual accountability and strengthen falsifiability.

7. **Escalation enforcement falsifiability** — Replaced vague "enforced by a configured escalation policy" with a specific, checkable artifact: a named PagerDuty escalation policy with a documented 30-minute threshold, testable by inspection.

8. **"Across the API" characterization in Summary** — Removed the phrase; replaced with language that stays within the base facts.

---

# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped an index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures for 4 hours and 18 minutes on a service handling $2.3M/hour. 12,000 merchants experienced failed transactions totaling $9.2M, and 847 support tickets were generated; most failed transactions retried successfully within 2 hours of recovery.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| 14:35 | On-call engineer scales up database read replicas; latency does not improve |
| 14:35–17:52 | Team diagnoses elevated traffic as cause; Black Friday proximity reinforces this hypothesis; no schema investigation initiated |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE`; identifies missing index; rebuild initiated |
| 18:41 | Latency recovers to baseline |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it. Queries executed without index support, driving p99 latency from 12ms to 8,400ms and causing transaction failures. The staging environment held 1/1,000th of production data volume, so the missing index produced no noticeable degradation during pre-production testing and the defective migration reached production undetected.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** With 1/1,000th of production data volume, query degradation from the missing index was not detectable in staging.

**The scaling action did not resolve latency, and the wrong hypothesis persisted for over 3 hours.** The on-call engineer scaled replicas per the existing runbook; latency did not improve. The team attributed the continued degradation to pre-Black Friday traffic rather than a schema change, and no query-level diagnostics were run until a senior engineer intervened at 17:52.

**No escalation threshold existed for unresolved latency incidents.** No policy required senior engineer involvement within a defined timeframe, allowing the misdiagnosis to continue unchecked.

---

## What We're Changing

**1. Query diagnostics step added to on-call runbook**
Owner: SRE On-Call Lead | Deadline: 7 days post-incident

The latency incident runbook must include `EXPLAIN ANALYZE` on the slowest active queries as a required numbered step before any infrastructure scaling action. Completion verified by runbook diff in version control.

**2. Escalation policy for unresolved latency incidents**
Owner: SRE On-Call Lead | Deadline: 7 days post-incident

Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation. A PagerDuty escalation tier named "Latency-30min" with a documented 30-minute threshold is created and active. Verified by inspection of the PagerDuty policy configuration.

**3. Mandatory post-migration index verification**
Owner: Database Platform Lead | Deadline: 30 days post-incident

All migration scripts must include a post-execution step that queries the schema to confirm required indexes exist. A migration review checklist item requiring this step is added to the pull request template for all database migrations. Verified by checklist presence in the template and in the next five merged migration PRs.

**4. Higher-volume environment for migration testing**
Owner: Infrastructure Lead | Deadline: 60 days post-incident

Provision a migration testing environment with sufficient data volume to produce measurable query latency differences when indexes are absent. All database migrations must be validated against this environment before production deployment. Verified by environment provisioning record and updated deployment runbook.