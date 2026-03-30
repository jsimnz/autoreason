# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses ten structural problems identified in the prior draft. The table below records each problem, the resolution adopted, and its location.

| # | Problem | Resolution | Location |
|---|---------|------------|----------|
| 1 | NSTL coordination burden unverified; §5.1 reference is circular | NSTL duties enumerated and timed; total estimated at 18–22% with explicit caveat that this is an estimate, not a budget | §0.2 |
| 2 | Deputy EM row confirmed by EM, who may be the non-performer | Deputy EM row confirmed by oversight body representative, same as EM row | §0.3 |
| 3 | Oversight body contact depends entirely on EM volunteering it | Oversight body contact obtained from two independent sources at kickoff; procedure specified | §0.4, Gate 0 |
| 4 | Gate 3 two-source check uses arbitrary band around arbitrary number; vendor benchmarks treated as independent data | [1.5, 6] range acknowledged as heuristic, not a confidence interval; vendor benchmark limitations stated; internal proxy given priority; fallback is blocking, not vendor data | §0.4, Gate 3 |
| 5 | Gate 2 fallback rationale claims 25/day is "stable" but it isn't | Stability claim removed; 25/day described as expensive and wrong-in-a-known-direction, which is preferable to wrong-in-an-unknown-direction | §0.4, Gate 2 |
| 6 | NSTL cannot unilaterally grant repository write access within 48 hours | Repository access grant requires named infrastructure admin; 48-hour commitment is contingent on admin response; NSTL owns the request, not the approval | §0.1 |
| 7 | Gate 4 tiebreak default assumes Security Lead is correct | Default rationale revised: Configuration B is chosen because it is recoverable in both directions, not because the Security Lead is right | §0.4, Gate 4 |
| 8 | Canonical filename is fragile across document revisions | Document versioning procedure defined; gate resolutions reference document hash, not filename | §0.1 |
| 9 | Concurrent Product Owner failure across Gates 1, 2, 4 noted but not resolved | Concurrent failure scenario given explicit consequence logic | §0.5 |
| 10 | "Engineering Manager's duties are outside the engineering budget" unexplained | Statement replaced with explicit analysis of whether EM is a contributing engineer and what that means for schedule accounting | §0.2 |

Prior drafts are archived at `eng/runbooks/notification-system/drafts/`.

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification system runbook repository** (`eng/runbooks/notification-system/`, read access for all engineering staff, write access to `gates/` subdirectory granted to gate owners as specified below), referencing this document by its **SHA-256 hash** (see §0.1a), with a timestamp.

Verbal commitments, Slack messages, and meeting notes do not resolve gates.

---

#### 0.1a Document Versioning and Hash Reference

The canonical reference for this document is its SHA-256 hash, not its filename. The filename (`notification-system-design-v3.md` at time of initial publication) may change as the document is revised. The hash of the version in force at any gate resolution is what matters.

**Procedure:**
- The NSTL computes the SHA-256 hash of the document at each revision and records it in `gates/document-versions.md` with the date, a short description of what changed, and the previous hash.
- Gate resolution commits must include the hash of the document version in force at the time of resolution, not the filename.
- If a gate was resolved against a prior version and the document has since been revised, the NSTL reviews whether the revision materially affects the gate's scope. If it does, the gate owner is notified and must re-confirm. If it does not, the prior resolution stands and the NSTL documents this determination in `gates/document-versions.md`.

This means a gate resolution is valid against the document version it referenced, even if the filename has changed. The hash chain in `gates/document-versions.md` is the authoritative record.

---

#### 0.1b Repository Access

Write access to the `gates/` subdirectory is controlled by the **infrastructure admin**, a named role in §0.3. The NSTL does not have unilateral authority to grant or revoke write access.

**Procedure for granting access:**
1. When a gate owner is confirmed in §0.3, the NSTL files a repository access request with the infrastructure admin, specifying the gate owner's name, email, and the `gates/` subdirectory.
2. The infrastructure admin grants access within **two business days** of the request.
3. The NSTL tracks outstanding access requests in the tracker. If access is not granted within two business days, the NSTL escalates to the Engineering Manager.
4. Until access is granted, the gate owner uses the proxy path (§0.1c).

The 48-hour proxy-to-direct-access transition in prior drafts is replaced by this procedure. The NSTL owns the request; the infrastructure admin owns the approval. The NSTL cannot commit to a timeline they do not control.

---

#### 0.1c Proxy Acknowledgment — Restricted Path

If a gate owner cannot access the repository at the time of resolution:

1. The gate owner sends written confirmation of their decision to the NSTL via email, with the Engineering Manager cc'd.
2. The NSTL attaches that email to the repository commit as `gates/attachments/gate-[N]-owner-confirmation-[date].eml`.
3. The commit message marks the resolution `[proxy]` and references the attachment filename and the document hash in force at resolution.
4. The NSTL files a repository access request per §0.1b if one is not already outstanding.

A proxy resolution without the attached written confirmation from the gate owner is not valid. The `[proxy]` marker documents the mechanism; the attached email is the evidentiary standard.

---

### 0.2 Enforcement: Honest Account

**The core problem:** On a four-person team over six months, any enforcement mechanism that depends on a single person performing their duties without independent verification is a single point of failure. This section defines two independent failure modes — NSTL non-performance and Engineering Manager non-performance — and provides distinct escalation paths for each.

---

#### NSTL Duty Enumeration and Time Estimate

The prior draft claimed NSTL coordination duties consume "approximately 10–15% of one engineer's time" and stated this was accounted for in §5.1. §5.1 was not shown. This section replaces that claim with an enumerated list of duties and explicit time estimates. These estimates are approximations, not guarantees. They are provided so the Engineering Manager can make an informed decision about whether to assign NSTL duties to a single engineer or distribute them.

| Duty | Frequency | Estimated time per instance | Estimated monthly total |
|------|-----------|-----------------------------|-------------------------|
| Weekly tracker update and gate status verification | Weekly | 30–45 min | 2–3 hrs |
| Pre-deadline check with gate owners | Per gate, per month | 30 min | 1–2 hrs |
| Proxy commit execution (if needed) | Occasional | 20 min | 0–1 hr |
| Escalation to EM after missed deadline | Per missed gate | 30 min | 0–1 hr |
| Deputy EM notification of EM non-performance | Rare | 30 min | 0–0.5 hr |
| Oversight body escalation | Rare | 1 hr | 0–1 hr |
| Gate 3 two-source check | Once (Month 2) | 2–4 hrs | 0.5–1 hr amortized |
| Document hash computation and version logging | Per revision | 15 min | 0.5 hr |
| Repository access request filing | Per new gate owner | 15 min | 0.5 hr |
| **Total estimate** | | | **5–10 hrs/month** |

At a 160-hour work month, this is approximately **3–6% of one engineer's time in a typical month**, rising to **8–12% in months with multiple gate deadlines** (Month 1, Month 2). The prior 10–15% figure was too high as a sustained average and too low as a peak. The honest range is 3–12% depending on the month.

**This estimate will be wrong.** The NSTL should track actual hours spent on coordination duties monthly and report them to the Engineering Manager. If actual hours exceed 12% in any two consecutive months, the Engineering Manager evaluates whether to redistribute duties or adjust scope.

**The NSTL is one of four backend engineers with a full technical workload.** NSTL coordination duties are in addition to, not instead of, engineering work. The Engineering Manager must account for this when assigning technical tasks to the NSTL.

---

#### Division of Responsibilities

**The NSTL is responsible for:**
- Verifying gate status each Monday morning and updating the tracker to reflect actual state
- Confirming that gate resolutions meet the written-acknowledgment standard (§0.1)
- Escalating to the Engineering Manager within 48 hours if a gate owner is unresponsive at a deadline
- Notifying the Deputy EM in writing if the Engineering Manager misses a defined duty
- Filing repository access requests per §0.1b
- Computing document hashes and maintaining `gates/document-versions.md`

**The Engineering Manager is responsible for:**
- Initiating contact with unresponsive gate owners after NSTL escalation
- Recalculating and presenting the revised project schedule within two business days of any gate slip
- Making the final call on Gate 4 tiebreaks (§0.4, Gate 4)
- Activating scope reductions when slip thresholds are crossed (§0.5)
- Deciding within 24 hours when Gate 3 sources fall outside the [1.5, 6] range

---

#### Whether the Engineering Manager Is a Contributing Engineer

The prior draft stated "the Engineering Manager's duties are outside the engineering budget" without explanation. This is only true if the Engineering Manager is a dedicated manager who does not contribute to the engineering workload. On a four-person team, this may not be the case.

**Two scenarios:**

**Scenario A — Dedicated EM (not a contributing engineer):** The Engineering Manager's duties (schedule revisions, escalation responses, Gate 4 tiebreaks, Gate 3 decisions) consume management time that does not reduce the engineering capacity of the four backend engineers. In this case, the prior statement is accurate, and engineering capacity is the full output of four engineers minus NSTL coordination overhead.

**Scenario B — Player-coach EM (contributing engineer):** The Engineering Manager is also one of the four backend engineers. In this case, the schedule-revision duty (two business days after any slip), the Gate 4 tiebreak (48-hour window), and the Gate 3 escalation response (24 hours) all consume engineering time. These are not large in isolation — perhaps 2–4 hours each — but they cluster around the same events (gate slips) that already compress the schedule. A gate slip triggers both a schedule revision and a scope-reduction decision at the same time the team is absorbing the impact of the slip.

**The document does not specify which scenario applies because this depends on the actual team structure.** The Engineering Manager must declare which scenario applies at Gate 0, and the project schedule in §5.1 must reflect it. If the Engineering Manager is a contributing engineer and this is not reflected in the schedule, the schedule is wrong.

---

#### If the Engineering Manager Does Not Perform Their Duties

The **Deputy Engineering Manager (Deputy EM)** is a named individual (row in §0.3) with a standing, specific trigger: if the Engineering Manager misses any defined duty, the NSTL notifies the Deputy EM in writing. The Deputy EM then:

1. Performs the missed duty within 24 hours of notification.
2. Notifies the oversight body that the substitution occurred, within one business day.

The Deputy EM does not replace the Engineering Manager on an ongoing basis. If the Engineering Manager is temporarily unavailable (illness, travel), they designate the Deputy EM proactively; in that case, the Deputy EM acts with full authority and no oversight body notification is required.

**If both the Engineering Manager and Deputy EM are non-performing:** The NSTL escalates directly to the oversight body using the contact information obtained at kickoff (§0.4, Gate 0). This path is always open.

---

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** Gate 0 requires this table to be filled before any other gate can be assigned to an owner.

| Role | Name | Email | Confirmed by | Date Confirmed |
|------|------|-------|--------------|----------------|
| Notification System Technical Lead (NSTL) | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |
| Deputy Engineering Manager (Deputy EM) | [FILL BEFORE ACTIVE] | | **Oversight body representative signature** | |
| Product Owner (Gates 1, 2, 4) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Analytics Owner (Gate 3) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Security Lead (Gates 4, 5) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Infrastructure Admin (repository access) | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |
| Engineering Manager (escalation target; Gate 4 tiebreak) | [FILL BEFORE ACTIVE] | | **Oversight body representative signature** | |
| Oversight Body Representative | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |

**Confirmation logic:**

- The **oversight body representative** confirms both the Engineering Manager row and the Deputy EM row. This eliminates the structural problem in the prior draft: the Deputy EM exists to act when the Engineering Manager fails, so the Engineering Manager cannot be the sole authority confirming the Deputy EM's participation. Both the EM and Deputy EM are confirmed by an independent party.
- The Engineering Manager confirms the NSTL, infrastructure admin, and oversight body representative rows.
- The NSTL confirms the Product Owner, Analytics Owner, and Security Lead rows after verifying each person's acceptance of their role.
- No gate beyond Gate 0 has a valid owner until the corresponding row is signed and dated.

---

### 0.4 Gate Register

#### Gate 0 — Owner Assignment (Meta-Gate)

| Field | Value |
|-------|-------|
| Decision | Named individuals table (§0.3) is complete and confirmed |
| Owner Role | Engineering Manager |
| Hard Deadline | End of Week 2, Month 1 |
| Dependent Work | All other gates. Gates 1–5 have no valid owner until Gate 0 resolves. |

**Pre-Gate 0 requirement — oversight body contact from two independent sources:**

The NSTL must obtain the oversight body representative's contact information before Gate 0 resolves, because the Gate 0 slip escalation path cannot depend on Gate 0 having resolved. The prior draft obtained this contact from the Engineering Manager at kickoff. This creates a single point of failure: if the Engineering Manager provides incorrect, outdated, or deliberately unhelpful contact information, the escalation path is compromised before any accountability structure is in place.

**Revised procedure:** The NSTL obtains the oversight body representative's contact information from **two independent sources** at project kickoff:

1. **Source 1 — Engineering Manager:** The NSTL asks the Engineering Manager for the oversight body representative's name, email, and any relevant context at the kickoff meeting. This is recorded in the tracker.
2. **Source 2 — Organizational directory or HR system:** The NSTL independently verifies the contact information against the company's organizational directory, HR system, or equivalent. If the two sources conflict, the NSTL uses the directory/HR source and documents the discrepancy.

The oversight body contact is stored in plaintext in the tracker, accessible to all team members. It is not gated on Gate 0 resolution. The NSTL confirms the contact is reachable (e.g., sends a brief introductory email) within the first week of the project.

**Why two sources:** The Engineering Manager is the party most likely to be in the non-performance scenario that requires oversight body escalation. Relying solely on the Engineering Manager to provide accurate contact information for their own escalation target is a structural weakness. The organizational directory provides an independent check.

**Consequence if Gate 0 is missed:**
- The Engineering Manager initiates daily check-ins with whoever is blocking table completion.
- The Engineering Manager presents a revised project schedule to the full team within two business days of the missed deadline.
- If Gate 0 is not resolved by end of Week 4, Month