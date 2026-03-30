# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preliminary Note on Scope

This document has a structural problem that should be named before proceeding: the majority of its content addresses gate system governance rather than notification system design. A reader who came here for guidance on push delivery, batching logic, or infrastructure choices will not find it until they have read through an extensive process framework.

This is a real tradeoff. The gate system exists because design decisions on a six-month, four-person project have a documented failure mode: decisions get made informally, accountability diffuses, and the project drifts. The gate system is an attempt to prevent that. But a governance framework that crowds out the technical content it is meant to protect has inverted its own purpose.

**How this document is organized to address that:**

- §1–6 contain the notification system design. A reader who wants only the technical content can read those sections independently.
- §0 contains the gate system. It is placed first because gates reference technical sections, not the reverse.
- The gate system is proportionate to the decisions it governs. It does not attempt to govern implementation details, only the decisions that, if made wrong or not made at all, would cause the project to fail.

---

## Revision Notes

This synthesis resolves problems identified across two prior drafts. Each problem, its resolution, and its location are recorded below.

| # | Problem | Resolution | Location |
|---|---------|------------|----------|
| 1 | Gate resolutions reference canonical filename; version change breaks references | Gate resolutions reference document SHA-256 hash, pinned at Gate 0 Phase 1; hash is the stable identifier | §0.1 |
| 2 | NSTL has sole custody of proxy commit with no independent verification | 48-hour gate owner email confirmation required; `[proxy-provisional]` status blocks dependent work until confirmed | §0.1 |
| 3 | NSTL may lack authority to grant repository write access unilaterally | Write access granted by named infrastructure owner; NSTL initiates request, does not grant | §0.1 |
| 4 | Two tiers of record-keeping exist without acknowledgment | Gate-resolution standard (repository commit) and operational-record standard (dated tracker entry) defined explicitly and separately | §0.1 |
| 5 | NSTL non-performance has no backstop | Tracker readable by all engineers; any team member may escalate; EM performs independent Monday spot-check; NSTL Backup role defined | §0.2 |
| 6 | Deputy EM activation depends on NSTL acting under potential EM pressure | Any team member may notify Deputy EM directly; NSTL notification is one path, not the only path | §0.2 |
| 7 | EM Monday spot-check timing creates false independence or sequencing problem | NSTL updates tracker by 9 AM Monday; EM spot-check after 1 PM Monday; both timestamped; independence defined as temporal separation and separate authorship | §0.2 |
| 8 | Engineering Manager is a single point of failure | Deputy EM role defined with specific triggers; any team member may activate; oversight body escalation always open | §0.2 |
| 9 | 10–15% NSTL burden estimate had no derivation | Enumerated task list with explicit frequency assumptions and time allocations; Month 2 spike broken out separately | §0.2 |
| 10 | Overrun threshold described inconsistently | Threshold set at 12 hours with explicit derivation from 5-hour average estimate | §0.2 |
| 11 | Deputy EM notification logged only in email | Deputy EM notification must be posted as dated tracker entry; email alone insufficient | §0.2 |
| 12 | Gate 0 bootstrapping problem: EM row confirmed by oversight body rep who may not yet be named | Gate 0 split into Phase 1 (pre-existing contact info, no table dependency) and Phase 2 (table completion); EM row confirmation deferred to Phase 2 | §0.4, Gate 0 |
| 13 | Oversight body representative row: EM names their own confirmer | NSTL independently verifies named individual holds the role against org directory; verification documented in tracker | §0.3 |
| 14 | NSTL Backup confirmed only by EM | NSTL Backup requires oversight body representative countersignature, same as Deputy EM | §0.3 |
| 15 | Sequencing dependency between oversight body rep row and Deputy EM row unaddressed | Mandatory fill order defined; bootstrapping sequence documented | §0.3 |
| 16 | Deputy EM appointment entirely within EM's control | Deputy EM requires oversight body representative countersignature | §0.3 |
| 17 | Gate 0 self-confirmation structurally compromised | EM row confirmed by oversight body representative; residual limitation documented | §0.3 |
| 18 | Named individuals not named; gate system inert | Named individuals table is a prerequisite; gate system explicitly inert until filled | §0.3 |
| 19 | Gate 1 unknown intent treated as deferral | Unknown re-engagement intent defaults to conservative upper-bound sizing | §0.4, Gate 1 |
| 20 | Gate 3 consequence clause contradicted its caveat | If R=3 reliability in doubt, Gate 3 is a blocking dependency with no sizing fallback | §0.4, Gate 3 |
| 21 | Gate 3 R=3 validity determination was underdefined | Explicit numeric criteria, two named benchmark sources, app category determination before Gate 3; appeal path to EM | §0.4, Gate 3 |
| 22 | Gate 2 miss triggered upper-bound sizing and delayed Gate 3 simultaneously | Gate 3 deadline does not shift on Gate 2 miss; proceeds on original deadline using provisional upper-bound figure | §0.4, Gates 2–3 |
| 23 | Gate 4 tiebreak default ignored security exposure | Default changed to Configuration B; Deputy EM performs tiebreak if EM misses 48-hour window | §0.4, Gate 4 |
| 24 | Four-day compression buffer treated as earned planning asset | Buffer removed from slip scenario tables; conditions to unlock it defined explicitly | §0.5 |
| 25 | Slip analysis assumed independent gate failures only | Concurrent failure scenario added for Product Owner holding Gates 1, 2, and 4 | §0.5 |
| 26 | Oversight body structurally undefined | Oversight body defined as named body with minimum two members; escalation produces defined action | §0.5 |
| 27 | Provisioned floor arithmetic used inconsistent headroom framings | Single formula used throughout; figures reconciled in one table | §1.4 |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification-system runbook repository** (`eng/runbooks/notification-system/`), referencing this document by its **SHA-256 hash**. The hash is pinned at Gate 0 Phase 1 resolution and recorded in the tracker. The hash, not the filename, is the stable identifier. If the document is revised, a new hash is pinned and recorded; prior gate resolutions remain valid against the hash they reference.

Verbal commitments, Slack messages, and meeting notes do not resolve gates. This is the **gate-resolution standard**.

**Two tiers of record-keeping:**

The gate-resolution standard requires a repository commit because gate resolutions unblock work and must be auditable against a specific document version. A second, lower tier — **operational records** — covers consequential actions that do not themselves resolve gates: Deputy EM notifications, overrun flags, escalation drafts, check-in outcomes. Operational records are posted as dated tracker entries by the person performing the action. The tracker is the authoritative log for operational records; email alone is not sufficient. This two-tier structure is intentional and explicit. The different standards reflect different audit requirements, not different levels of seriousness.

**Repository write access:** Write access to the `gates/` subdirectory is granted by the **infrastructure owner** (named in §0.3), not by the NSTL. The NSTL initiates access requests; the infrastructure owner fulfills them within 48 hours. If the infrastructure owner does not fulfill a request within 48 hours, the NSTL escalates to the Engineering Manager, who resolves it or designates an alternate with the necessary permissions.

**Proxy acknowledgment — restricted path:** If a gate owner cannot access the repository at the time of resolution:

1. The gate owner sends written confirmation of their decision to the NSTL via email, with the Engineering Manager cc'd.
2. The NSTL attaches that email to the repository commit as `gates/attachments/gate-[N]-owner-confirmation-[date].eml` and marks the commit `[proxy-provisional]`.
3. The repository's automated commit notification is sent to the gate owner at their registered email address. The gate owner must reply within 48 hours confirming that the attached document accurately represents what they sent.
4. Upon confirmed reply, the NSTL updates the commit status to `[proxy-confirmed]` and attaches the confirmation reply as `gates/attachments/gate-[N]-owner-confirmation-[date]-verified.eml`.
5. If the gate owner does not confirm within 48 hours, the commit remains `[proxy-provisional]`. A `[proxy-provisional]` resolution does not unblock dependent work. The NSTL posts a dated tracker entry noting the non-confirmation and notifies the Engineering Manager, who contacts the gate owner directly.
6. The NSTL requests repository write access for the gate owner from the infrastructure owner within 48 hours of any proxy resolution.

**Residual limitation:** A gate owner who does not check their email would not catch an inaccurate proxy commit. Direct repository access is the standard. This path is a restricted fallback, not a routine mechanism.

---

### 0.2 Enforcement

**The core problem:** On a four-person team over six months, any enforcement mechanism that depends on a single person performing their duties without independent verification is a single point of failure. This section addresses NSTL non-performance and EM non-performance with distinct escalation paths, and ensures that the Deputy EM activation path does not depend on the NSTL acting under potential EM pressure.

**Division of responsibilities:**

The NSTL is responsible for: updating the tracker by 9 AM each Monday; confirming gate resolutions meet the written-acknowledgment standard; escalating to the Engineering Manager within 48 hours of a gate owner being unresponsive at a deadline, documented as a dated tracker entry; posting a dated tracker entry when any defined EM duty is missed.

The Engineering Manager is responsible for: performing an independent spot-check of the tracker each Monday after 1 PM; initiating contact with unresponsive gate owners after NSTL escalation; presenting a revised project schedule within two business days of any gate slip; making the final call on Gate 4 tiebreaks; activating scope reductions when slip thresholds are crossed.

**Monday check timing and independence:** The NSTL updates the tracker by 9 AM Monday. The EM performs the spot-check after 1 PM Monday. Both are timestamped. Independence here means temporal separation and separate authorship — the EM's check is a verification of the NSTL's update, not a parallel update from a different data source. If the EM's spot-check finds the tracker inaccurate or the NSTL update absent, the EM documents the discrepancy as a dated tracker entry and contacts the NSTL directly.

**NSTL non-performance:** The tracker is readable by all four engineers. Any team member who observes that the NSTL has not updated the tracker by end of day Monday, or that a gate status appears inaccurate, may notify the Engineering Manager directly — no requirement to go through the NSTL. The EM's spot-check independently catches tracker staleness without depending on anyone reporting it.

If the EM determines the NSTL is not performing coordination duties: (1) document the specific missed duty as a dated tracker entry; (2) reassign coordination duties to the NSTL Backup; (3) post a dated tracker entry notifying the oversight body that reassignment occurred, and separately contact the oversight body representative directly.

**EM non-performance — activation path:** The Deputy EM path activates when the EM misses a defined duty. **Any team member** — including but not limited to the NSTL — who observes a missed EM duty may notify the Deputy EM directly. The notification must be posted as a dated tracker entry by the notifying team member. The NSTL has a specific obligation to post this notification, but any other team member may do so if the NSTL does not, or if the NSTL appears to be under pressure not to. This is a parallel path with equal standing, not a secondary option.

Defined EM duties with specific triggers: presenting a revised schedule within two business days of a gate slip; initiating contact within 48 hours of NSTL escalation; deciding a Gate 4 tiebreak within the 48-hour window; completing the Monday spot-check (verifiable by timestamp absence).

When the Deputy EM is notified of a missed duty: (1) perform the missed duty within 24 hours of notification; (2) post a dated tracker entry noting the substitution and contact the oversight body representative directly within one business day.

**If both EM and Deputy EM are non-performing:** Any team member may escalate directly to the oversight body. The oversight body representative's contact information is stored in the tracker in plaintext at project kickoff, before Gate 0 Phase 1 resolves, accessible to all team members without requiring any gate to have resolved first.

**Engineering budget — derived estimate:**

| Task | Frequency assumption | Per instance | Monthly total |
|------|---------------------|-------------|---------------|
| Monday tracker update and gate verification | 4× per month | 45 min | ~3.0 hours |
| Gate owner pre-deadline check-ins | 1 gate/month average across 6 gates over 6 months | 30 min | ~0.5 hours |
| Escalation drafting and tracker entry | 1 event per 2 months average; 6 gates, ~50% requiring follow-up, most resolved without formal escalation | 1–2 hours | ~0.75 hours |
| Proxy commit processing | 1 event across full project; most gate owners will have direct access | 1 hour | ~0.2 hours |
| Gate 3 two-source check | Once, Month 2 | 3–4 hours | ~0.5 hours averaged over 6 months |
| **Monthly average** | | | **~5 hours/month** |

**Month 2 exception:** The Gate 3 two-source check (3–4 hours) falls entirely in Month 2. Month 2 NSTL coordination burden is approximately 8–9 hours, not 5. The monthly average obscures this spike. Month 2 sprint planning should use 8–9 hours, not 5.

**Overrun threshold:** If NSTL coordination duties in any given month exceed 12 hours (approximately 2× the 5-hour average estimate), the NSTL posts a dated tracker entry flagging the overrun and raises it at the next weekly check-in. The EM decides whether to redistribute duties or adjust scope. This prevents silent budget erosion.

---

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** The fill order below is mandatory because some rows have sequencing dependencies.

**Mandatory fill order:**

1. **Oversight Body Representative** — filled by the Engineering Manager. The NSTL independently verifies that the named individual holds the oversight body role by checking the organizational directory (HR system, org chart, or equivalent) and documenting the verification method and source as a dated tracker entry. If the org directory is ambiguous or unavailable, the NSTL contacts the named individual directly to confirm their role and documents that confirmation. This verification exists because the document cannot check whether the EM has named someone who actually holds the role; the NSTL's independent check is the mechanism that does so.

2. **Engineering Manager** — filled by the oversight body representative (not the EM), after step 1 is complete.

3. **Deputy EM** — filled by the Engineering Manager after step 2 is complete, with oversight body representative countersignature. Cannot be completed without the oversight body representative's knowledge and assent.

4. **NSTL Backup** — filled by the Engineering Manager, with oversight body representative countersignature. Because the EM controls this appointment, the same countersignature requirement as the Deputy EM applies. An EM who is not performing their duties cannot unilaterally install a Backup who will fail to escalate against them.

5. **NSTL** — filled by the Engineering Manager after steps 1–4 are complete.

6. **Product Owner, Analytics Owner, Security Lead** — filled by the NSTL after confirming each person's acceptance of their role.

7. **Infrastructure Owner** — filled by the Engineering Manager; controls repository access grants (§0.1).

| Role | Name | Email | Confirmed