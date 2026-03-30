# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This synthesis resolves structural problems identified across two prior drafts. The table below records each problem, the resolution adopted, and its location. Prior drafts are archived at `eng/runbooks/notification-system/drafts/`.

| Problem | Resolution | Location |
|---------|------------|----------|
| Engineering Manager is a single point of failure | Deputy EM role defined with specific triggers; oversight body escalation path extended to EM non-performance | §0.2 |
| Gate 0 self-confirmation is structurally compromised | EM row confirmed by oversight body representative, not self-confirming | §0.3 |
| NSTL makes underdefined judgment on R=3 validity | Replaced with explicit numeric criteria, two-source verification, and appeal path to Engineering Manager | §0.4, Gate 3 |
| Proxy acknowledgment undermines written-acknowledgment standard | Proxy requires attached written confirmation from gate owner; unverified proxies are not valid | §0.1 |
| Gate 3 consequence clause contradicts its own caveat | If R=3 reliability is in doubt, Gate 3 is a blocking dependency with no sizing fallback | §0.4, Gate 3 |
| Four-day compression buffer treated as earned planning asset | Buffer removed from slip scenario tables; conditions required to unlock it defined explicitly | §0.5 |
| Gate 4 tiebreak default ignores security exposure | Default changed to Configuration B; preserves optionality without security regression of A | §0.4, Gate 4 |
| Gate 4 tiebreak has no Deputy EM backstop | Deputy EM performs tiebreak if Engineering Manager misses 48-hour window | §0.4, Gate 4 |
| Slip analysis assumes independent gate failures | Concurrent failure scenario added for Product Owner holding Gates 1, 2, and 4 | §0.5 |
| Gate 1 consequence ignored unknown intent as a third state | Unknown re-engagement intent defaults to conservative upper-bound sizing, not deferral | §0.4, Gate 1 |
| Gate 0 escalation path depends on Gate 0 resolving | NSTL obtains oversight body contact at project kickoff, before Gate 0, stored in plaintext in tracker | §0.4, Gate 0 |
| Named individuals not named | Named individuals table is a prerequisite; gate system explicitly inert until filled | §0.3 |
| Provisioned floor arithmetic used inconsistent headroom framings | Single formula used throughout; figures reconciled in one table | §1.4 |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification-system runbook repository** (`eng/runbooks/notification-system/`, read access for all engineering staff, write access to `gates/` subdirectory granted to gate owners upon Gate 0 resolution), referencing this document by its canonical filename `notification-system-design-v3.md`, with a timestamp.

Verbal commitments, Slack messages, and meeting notes do not resolve gates.

**Proxy acknowledgment — restricted path:** If a gate owner cannot access the repository at the time of resolution:

1. The gate owner sends written confirmation of their decision to the NSTL via email, with the Engineering Manager cc'd.
2. The NSTL attaches that email to the repository commit as `gates/attachments/gate-[N]-owner-confirmation-[date].eml`.
3. The commit message marks the resolution `[proxy]` and references the attachment filename.
4. The NSTL grants the gate owner direct write access within 48 hours so future resolutions do not require this path.

A proxy resolution without the attached written confirmation from the gate owner is not valid. The `[proxy]` marker documents the mechanism used; the attached email is the evidentiary standard. This path prevents repository access from becoming a bureaucratic barrier. It does not lower the evidentiary standard.

---

### 0.2 Enforcement: Honest Account

**The core problem:** On a four-person team over six months, any enforcement mechanism that depends on a single person performing their duties without independent verification is a single point of failure. This section defines two independent failure modes — NSTL non-performance and Engineering Manager non-performance — and provides distinct escalation paths for each.

**Division of responsibilities:**

**The NSTL (one of four backend engineers) is responsible for:**
- Verifying gate status each Monday morning and updating the tracker to reflect actual state
- Confirming that gate resolutions meet the written-acknowledgment standard (§0.1)
- Escalating to the Engineering Manager within 48 hours if a gate owner is unresponsive at a deadline
- Notifying the Deputy EM in writing if the Engineering Manager misses a defined duty

**The Engineering Manager is responsible for:**
- Initiating contact with unresponsive gate owners after NSTL escalation
- Recalculating and presenting the revised project schedule within two business days of any gate slip
- Making the final call on Gate 4 tiebreaks (§0.4, Gate 4)
- Activating scope reductions when slip thresholds are crossed (§5.3)

**Engineering budget impact:** NSTL coordination duties consume approximately 10–15% of one engineer's time across the project. This is accounted for in §5.1. The Engineering Manager's duties are outside the engineering budget.

**If the Engineering Manager does not perform their duties:**

The **Deputy Engineering Manager (Deputy EM)** is a named individual (row in §0.3) with a standing, specific trigger: if the Engineering Manager misses any defined duty — presenting a revised schedule within two business days of a slip, initiating contact within 48 hours of NSTL escalation, deciding a Gate 4 tiebreak within the 48-hour window — the NSTL notifies the Deputy EM in writing. The Deputy EM then:

1. Performs the missed duty within 24 hours of notification.
2. Notifies the oversight body that the substitution occurred, within one business day.

The Deputy EM does not replace the Engineering Manager on an ongoing basis. The trigger is specific missed duties. If the Engineering Manager is temporarily unavailable (illness, travel), they designate the Deputy EM proactively; in that case, the Deputy EM acts with full authority and no oversight body notification is required.

**If both the Engineering Manager and Deputy EM are non-performing:** The NSTL escalates directly to the oversight body. The NSTL's escalation path to the oversight body is always open, regardless of Engineering Manager or Deputy EM status. The oversight body representative's contact information is obtained at project kickoff (§0.4, Gate 0) and stored in plaintext in the tracker, accessible to all team members.

**The limit of this mechanism:** Concurrent departure of both the Engineering Manager and Deputy EM would compromise the gate system. This is an unlikely but real scenario. The direct NSTL-to-oversight-body path is the final backstop.

---

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** Gate 0 requires this table to be filled before any other gate can be assigned to an owner.

| Role | Name | Email | Confirmed by | Date Confirmed |
|------|------|-------|--------------|----------------|
| Notification System Technical Lead (NSTL) | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |
| Deputy Engineering Manager (Deputy EM) | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |
| Product Owner (Gates 1, 2, 4) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Analytics Owner (Gate 3) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Security Lead (Gates 4, 5) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Engineering Manager (escalation target; Gate 4 tiebreak) | [FILL BEFORE ACTIVE] | | **Oversight body representative signature** | |
| Oversight Body Representative | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |

**Instructions:**
- The oversight body representative fills in the Engineering Manager row. This eliminates self-confirmation: the Engineering Manager cannot be the sole authority confirming their own participation in a system they are responsible for enforcing.
- The Engineering Manager fills in the NSTL row, the Deputy EM row, and the oversight body representative row.
- The NSTL fills in the Product Owner, Analytics Owner, and Security Lead rows after confirming each person's acceptance of their role.
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

**Pre-Gate 0 requirement:** The NSTL obtains the oversight body representative's contact information from the Engineering Manager at project kickoff. This information is stored in the tracker in plaintext, accessible to all team members. It is not gated on Gate 0 resolution. This is necessary because the Gate 0 slip escalation path cannot depend on Gate 0 having resolved.

**Consequence if missed:**
- The Engineering Manager initiates daily check-ins with whoever is blocking table completion.
- The Engineering Manager presents a revised project schedule to the full team within two business days of the missed deadline.
- If Gate 0 is not resolved by end of Week 4, Month 1, the NSTL escalates directly to the oversight body representative using the contact information obtained at kickoff. The NSTL documents this escalation in the tracker.

**Why Gate 0 exists:** A gate system with no named subjects is inert. Gate 0 is owned by the Engineering Manager rather than the NSTL because the Engineering Manager has organizational authority to assign roles; the NSTL does not.

---

#### Gate 1 — Email Opt-In Posture

| Field | Value |
|-------|-------|
| Decision | Default-on vs. default-off for marketing email |
| Owner Role | Product Owner |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | Email worker sizing; provider contract; IP warm-up schedule |

**Pre-deadline check:** At or before the Gate 1 deadline, the NSTL confirms with the Product Owner: *Is email part of the re-engagement strategy for dormant users?* This question must be answered before the deadline, not after it is missed. The NSTL documents the answer in the tracker regardless of Gate 1's resolution status.

**Consequence if missed:**

- **If email is confirmed as a re-engagement mechanism:** Gate 1 is escalated immediately to the Engineering Manager. Email channel work begins provisionally sized for the messaging-primary upper bound (§1.3b) to avoid blocking provider contracts and IP warm-up. This provisional sizing carries documented cost uncertainty.
- **If email is confirmed as not a re-engagement mechanism:** Email channel is deferred to post-launch v1.1. Push, in-app, and SMS launch without email. The deferral is logged with the explicit note that the Product Owner confirmed email is not a re-engagement mechanism on [date]. This claim is treated as conditional on this app's confirmed strategy, not a universal assumption.
- **If the pre-deadline check was not completed (intent unknown):** Gate 1 is treated as if email is a re-engagement mechanism. Provisional upper-bound sizing proceeds. Unknown intent defaults to the conservative path, not deferral.

---

#### Gate 2 — App Orientation

| Field | Value |
|-------|-------|
| Decision | Messaging-primary vs. content-discovery |
| Owner Role | Product Owner |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | Notifications-per-user figure lock; all worker sizing dependent on that figure; Gate 3 deadline shifts by the same duration if Gate 2 slips |

**Consequence if missed:** System is provisioned for the messaging-primary upper bound (25/day). The Product Owner receives a written statement that the over-provisioning cost is a direct consequence of the unresolved decision, with the cost differential from §1.3b attached. The Engineering Manager activates scope reductions (§5.3) on the day of the missed deadline, not after integration testing reveals problems.

**Why 25/day and not 20/day as fallback:** 20/day at 30% DAU/MAU produces a sustained average in the warning band, which itself triggers a re-sizing review. A fallback that generates a downstream review moves the uncertainty rather than resolving it. 25/day is expensive and stable. This is not a safe default — it is an expensive one, made visible.

---

#### Gate 3 — Session Time Data

| Field | Value |
|-------|-------|
| Decision | Average session minutes per DAU per day |
| Owner Role | Analytics Owner |
| Hard Deadline | End of Week 2, Month 2 (shifts by the same duration as any Gate 2 slip) |
| Dependent Work | In-app worker sizing (final); in-app fraction lock |

**The R=3 problem:** The in-app fraction model uses R=3 (notifications per session per active user) as a working assumption. R=3 is unvalidated. If it is wrong by more than a factor of approximately 2, the sensitivity range derived from it is unreliable, and sizing for the upper bound of that range is not a meaningful conservative estimate — it is an arbitrary number. Gate 3 exists to replace R=3 with a measured value before worker sizing is finalized.

**Consequence if missed — structured determination, not NSTL discretion:**

The NSTL applies a two-source check at the Gate 3 deadline.

**Source 1 — Internal proxy:** Pull the 30-day average of in-app notification interactions per DAU per day from the existing analytics pipeline. If unavailable, document why and treat Source 1 as inconclusive.

**Source 2 — Industry benchmark:** Reference the most recent mobile engagement benchmark report available to the team (e.g., Leanplum, Braze, or Airship annual benchmark). Record the reported notifications-per-session figure for the app category closest to this app's orientation.

**Decision rule:**

- If both sources suggest a value within [1.5, 6] (within a factor of 2 of R=3), proceed with upper-bound sizing from the sensitivity range. Document both sources and their values in the gate log.
- If either source suggests a value outside [1.5, 6], or if both sources are inconclusive, Gate 3 is a **blocking dependency**. In-app worker sizing is not finalized. The Engineering Manager is notified immediately. The NSTL presents both sources to the Engineering Manager, who decides within 24 hours whether to proceed with a revised R value, commission an expedited data pull, or escalate to the Analytics Owner for accelerated resolution.

**Appeal path:** If the NSTL's source-check conclusion is disputed by any team member, the Engineering Manager reviews both sources and makes a binding determination within 24 hours. This is documented in the gate log.

**Why this replaces NSTL discretion:** The previous version gave the NSTL a judgment call with no criteria and no appeal. This version gives the NSTL a lookup task with explicit numeric thresholds. The judgment call — what to do when sources are outside the range — belongs to the Engineering Manager, who has the authority to act on it.

---

#### Gate 4 — SMS 2FA Configuration

| Field | Value |
|-------|-------|
| Decision | Configuration A (SMS-only), B (SMS + authenticator app, SMS default), or C (SMS + authenticator app, authenticator default with nudge) |
| Owner Role | Product Owner + Security Lead (both must sign) |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | SMS spend cap; SMS worker sizing; authenticator app integration scope (if C) |

**Tiebreak procedure:** If both parties are actively engaged but in disagreement at the deadline:

1. Both parties document their positions in writing in the runbook repository within 24 hours of the deadline.
2. The Engineering Manager has 48 hours from the deadline to review both positions and make a binding decision.
3. If the Engineering Manager does not decide within 48 hours, the NSTL notifies the Deputy EM, who performs the tiebreak within 24 hours.
4. If neither decides, the system defaults to **Configuration B**.

**Why Configuration B as the tiebreak default, not Configuration A:** Configuration A is SMS-only. If the tiebreak arose because the Security Lead opposed Configuration A on security grounds, defaulting to A means a security regression occurs precisely because the process failed. Configuration B (SMS + authenticator app, SMS default) preserves optionality without that regression. It is more expensive than A and less operationally complex than C. A tiebreak default should not punish the party with the stronger security argument