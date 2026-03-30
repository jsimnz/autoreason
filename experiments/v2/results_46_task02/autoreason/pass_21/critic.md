## Real Problems with This Proposal

### 1. The document cuts off mid-sentence

Section 1.3b SMS Cost Modeling ends abruptly: "Twilio and—". Whatever follows is missing. This is a complete design document that explicitly claims to handle SMS geographic rate variation, which it identifies as a material cost driver (6–20× variation). That section is unfinished.

### 2. The sensitivity table flags are mathematically inconsistent with their own stated boundary

The document states: "The 700/sec sustained average threshold (4,200/sec ÷ 6× peak factor) is the boundary between ✓ and ⚠/✗ designations." But the table marks 40% DAU/MAU at 15/day (~694/sec) as ✓, which is below 700. That's fine. However, 30% DAU/MAU at 20/day (~694/sec) is also marked ✓, yet 40% at 15/day (~694/sec) gets ✓ too — these are the same number. Meanwhile 40% at 20/day (~926/sec) gets ⚠, which is correct. The inconsistency is that ~868/sec at 30%/25/day gets ⚠ but the flag description says ⚠ triggers when "sustained avg × 6 exceeds 70% of provisioned floor" — 70% of 4,200 is 2,940/sec peak, meaning 490/sec sustained average. By that definition, nearly every scenario should be ⚠, not just the ones marked. The stated threshold criterion and the actual flag assignments do not match.

### 3. The peak factor selection is asserted without derivation

The document says "4× is unsupported by diurnal data. Published comparable-platform data yields 5–8×; working figure is 6×" and promises a derivation in Section 1.4. Section 1.4 does not appear in this document. The provisioned floor of 4,200/sec — the single most consequential capacity number — rests on a derivation that is referenced but absent.

### 4. The in-app fraction correction cites sources that don't straightforwardly support the claim

The document cites "Localytics 2022, Adjust 2023" as reporting 5–8% in-app notification delivery rates for social apps. Localytics was acquired and its research publication effectively ceased before 2022. Citing a 2022 Localytics report is suspect. This undermines the specific empirical grounding claimed for rejecting the naive model.

### 5. The Configuration C SMS spend cap problem is identified but not resolved

The document correctly notes that a spend cap sized against steady-state volume "will be triggered routinely during the first 6–12 months" for Configuration C. It then provides no spend cap figure for Configuration C at launch. The corrected working estimate (~42,500/day) is given, but the spend cap — which was explicitly identified as the actionable output — is absent. The problem is named without being addressed.

### 6. The email volume model double-counts

The channel allocation table lists email as "separate budget" with a volume range of ~530K–4.53M/day. The email section then derives that range from MAU opt-in population. But the push and in-app volumes are derived from DAU-based notification events. If a DAU user receives a social notification via push, do they also receive a digest email that day? The model never specifies whether email volume is additive to push/in-app events or whether digest emails represent aggregated social events that would otherwise be push notifications. This ambiguity means total daily notification volume cannot actually be calculated from the numbers provided.

### 7. The "product decision required" gate for email opt-in posture is a launch blocker with no owner or deadline

The document states this "must be recorded in writing from a named product owner before the email tier is sized" and calls it "a launch gate item." No owner is named, no deadline is given, and no consequence path is described if it isn't resolved. For a 6-month timeline with 4 engineers, an unresolved gate item that changes email volume by 4–7× and affects provider procurement and IP warm-up timelines is a schedule risk that is identified but not managed.

### 8. The Braze citation is used selectively in a way that may misrepresent the source

The document cites "Braze 2023 Mobile Marketing Report" as reporting 15–20 notifications/day for active users of social apps, then argues this conflates messaging-heavy and content-discovery apps and selects 15 as the working figure. The Braze report does not actually segment by app type in the way described — it reports aggregate medians across categories. The document treats a single aggregate figure as if it were two distinct category figures and then chooses the lower one, which is not what the source supports.

### 9. The runbook sign-off mechanism is specified for SMS 2FA but not for other launch gate items

The document specifies that runbook sign-off requires "a named engineer's recorded acknowledgment in the team's runbook repository." This mechanism is mentioned in the preamble summary but only in the context of SMS 2FA default. The email opt-in posture gate, the DM-vs-content-discovery product question affecting notifications-per-user, and the session time confirmation for in-app fraction are all identified as decisions that must be resolved before sizing. None of them have the same sign-off mechanism applied. The sign-off process is inconsistently scoped.