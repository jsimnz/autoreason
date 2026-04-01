I'll address each problem systematically before presenting the revised document.

**Changes made and which problem each fixes:**

1. **Timeline editorializing — "Team attributes degradation to pre-Black Friday traffic spike"**: Replaced with a discrete, observable event: the on-call engineer's wrong-hypothesis action (traffic spike assumed, no query diagnostics run). Fixes: timeline editorializing constraint violation.

2. **Timeline editorializing — "Latency does not improve"**: Removed. The scaling attempt is recorded as an event; the outcome characterization is dropped. Fixes: "latency does not improve" editorial violation.

3. **First response collapsed into alert row**: Separated into two rows — 14:31 for the alert, and a distinct row for the scaling attempt. Fixes: timeline omits first response as discrete event.

4. **Missing intermediate resolution event**: Added a row between 17:52 and 18:41 noting index rebuild completion, since a 49-minute gap during the resolution phase is a meaningful omission. Fixes: imprecise fix timeline.

5. **"No detectable degradation" soft hedge**: Changed to "the missing index produced no noticeable degradation during pre-production testing" — matching the base facts' direct language ("wasn't noticeable"). Fixes: hedging language in Root Cause.

6. **"What Went Wrong" fifth item (no escalation threshold)**: Removed. This item is an inference not present in the base facts' contributing factors. Fixes: constraint violation — adding content not derivable from base facts.

7. **"Migration review process" item**: Removed as a standalone item — it is an inference not separately stated in the base facts. Its substance is absorbed into the existing "migration script had no index verification step" item. Fixes: same constraint violation.

8. **Remediation item 1 verification method**: Strengthened from "runbook diff in version control" to specifying that the runbook must show `EXPLAIN ANALYZE` as a numbered step explicitly preceding any scaling action, verified by the SRE On-Call Lead signing off on the specific step number in the published runbook. Fixes: weak falsifiability of item 1.

9. **Remediation item 2 verification**: Replaced "a documented test page confirming the tier fires correctly" with a specific, located artifact: a PagerDuty test alert record stored in the incident retrospective folder, with the SRE On-Call Lead as named owner of that record. Fixes: partially unfalsifiable verification in item 2.

10. **Word count**: With the structural removals (two "What Went Wrong" items) and tightened verification language, the document is brought under 600 words. Fixes: word count constraint violation.

11. **Table formatting**: Changed `|---|---|` to `| --- | --- |` for more consistent Markdown rendering. Fixes: non-standard em-dash table formatting.

---

# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped an index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across 4 hours on a service handling $2.3M/hour. 12,000 merchants experienced failed transactions totaling $9.2M, and 847 support tickets were generated; most failed transactions retried successfully within 2 hours of recovery.

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