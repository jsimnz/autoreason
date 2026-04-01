I'll address each valid problem in turn, then present the revised document.

**Changes made and which problem each fixes:**

- **Problem 3:** Removed "no query-level investigation runs" from the 14:31–17:52 timeline entry, as it characterizes an absence of action rather than a chronological event.
- **Problem 2:** Removed "causing $9.2M in failed transactions, most of which retried successfully within 2 hours of recovery" from the Root Cause section, as it duplicates the Summary verbatim.
- **Problem 5:** Replaced the PagerDuty configuration inspection check with a test-trigger verification (submit a synthetic latency alert and confirm escalation fires within 30 minutes), making the falsifiability check behavioral rather than configurational.
- **Problem 6:** Replaced "at least 10% of production data volume" with language derivable from the base facts: "a data volume sufficient to reproduce query performance degradation caused by missing indexes, validated by running the defective migration against this environment and confirming measurable latency impact."
- **Problem 7:** Rebalanced the "What Went Wrong" section so the wrong-hypothesis paragraph is trimmed and the staging paragraph is not subordinated to it. The three-hour delay is kept as context but no longer framed as a parallel contributing factor alongside the two base-fact contributing factors.
- **Problem 8:** Replaced "attributed" with "assumed," matching the base facts directly and removing the psychological inference.
- **Problem 1:** The above cuts reduce the word count to within the 600-word limit.

---

# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped an index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across a 4-hour window on a service handling $2.3M/hour. 12,000 merchants experienced failed transactions totaling $9.2M; most retried successfully within 2 hours of recovery, and 847 support tickets were generated.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms |
| 14:31–17:52 | On-call engineer scales up database replicas; team assumes traffic spike with Black Friday two days away |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE`; missing index identified; rebuild initiated |
| 18:41 | Latency recovers to baseline |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it. Queries ran without index support, driving p99 latency from 12ms to 8,400ms. The staging environment held 1/1,000th of production data volume, so the missing index produced no noticeable degradation during pre-production testing, and the defective migration reached production undetected.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed, so the defect passed through the deployment pipeline without detection.

**Staging did not surface the problem.** With 1/1,000th of production data volume, query degradation from the missing index was undetectable before deployment. Three hours passed before a senior engineer ran query-level diagnostics and identified the root cause, because the team assumed the degradation was a traffic spike.

---

## What We're Changing

**1. Escalation policy for unresolved latency incidents**
Owner: SRE On-Call Lead | Deadline: 7 days post-incident

Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation. Verified at 30 days by firing a synthetic latency alert in staging and confirming the escalation reaches a senior engineer within 30 minutes.

**2. Mandatory post-migration index verification**
Owner: Database Platform Lead | Deadline: 30 days post-incident

All migration scripts must include a post-execution step that queries the schema to confirm required indexes exist. A CI check must fail the migration pipeline if this verification step is absent. Verified at 30 days by: (a) submitting a test migration pull request without the verification step and confirming the CI pipeline rejects it; and (b) auditing the migrations directory to confirm all existing migration scripts include the verification step.

**3. Higher-volume environment for migration testing**
Owner: Infrastructure Lead | Deadline: 30 days post-incident

Provision a migration testing environment with data volume sufficient to reproduce query performance degradation caused by missing indexes, validated by running the defective migration from this incident against the environment and confirming measurable latency impact. All database migrations must be validated against this environment before production deployment. Verified at 30 days by environment provisioning record, results of the validation run, and an updated deployment runbook requiring sign-off on migration test results from this environment.