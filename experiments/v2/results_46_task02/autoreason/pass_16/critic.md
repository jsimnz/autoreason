## Real Problems with This Proposal

### 1. The 17 notifications/DAU/day figure is doing enormous work with thin justification

The Braze 2023 benchmark is cited but not interrogated. "Social apps" is a broad category covering everything from dating apps to professional networks to meme platforms. The figure appears once in 1.1 and is then treated as a constant throughout all downstream arithmetic. There is no sensitivity table for this input despite it being multiplicatively equivalent in importance to the DAU/MAU ratio. The document explicitly acknowledges the DAU/MAU ratio as "the first multiplier in the sizing cascade" but the notifications-per-DAU figure multiplies the same cascade and receives no equivalent scrutiny.

### 2. The fan-out arithmetic in 1.4 is structurally broken

The viral spike calculation multiplies engagements by "fan-out per engagement" (200 notifications per engagement), then attributes 35% of the result to a cohort of 150,000 users. But a single viral post generates notifications primarily for one account (the creator) and potentially their followers — not 200 notifications per engagement across the platform. Likes notify the content creator (1 notification), not the liker's followers. The 200 fan-out figure is presented without derivation and conflates fundamentally different notification types. The per-user multiplier of 19× that flows from this arithmetic is therefore unreliable, and the "high case" infrastructure scenario is built on it.

### 3. The 35% cohort volume share is circular in a way the document does not fully resolve

The document claims this is "not circular" because the same assumption appears in two contexts. But the multiplier derivation uses the 35% figure to calculate the per-user spike rate, and the baseline rate derivation implicitly requires the same cohort definition to be consistent. There is no independent empirical basis for 35% cited anywhere. The document acknowledges it "should be measured at launch" — meaning the multiplier table and the high-case infrastructure scenario are both derived from an unvalidated structural assumption that the document itself flags as uncertain.

### 4. The 2FA SMS assumption is the most uncertain figure in 1.3, and the document knows it

The document states the 8% SMS-2FA selection rate "is the most uncertain figure here" and notes that defaulting to SMS could multiply volume by 5–7×. This is a product decision that may already be made or may be made after launch. The spend cap ($500/day) is calibrated against the 8% assumption. If the product ships with SMS as the default 2FA method, the spend cap is wrong by a factor of 4–5 on day one. The document defers this to a 30-day post-launch trigger, but the cap is enforced from day one.

### 5. The email latency range is cut off

The latency table in the final visible section ends mid-row with "**High**; see below" and there is no "below." This is a direct repeat of the problem that was supposedly fixed (item 4 in the revision table: "Section 1.3 cut off mid-sentence"). The document's own revision history makes this omission more damaging — it was identified as a problem, declared fixed, and recurs.

### 6. The concurrent session arithmetic in 1.2 is not connected to the in-app worker sizing

Section 1.2 derives that ~300K users are in-app at any moment using a 10% concurrent session rate. This figure is then dropped. The in-app worker sizing uses the 20% channel split against total inbound volume, not against the concurrent session population. These are different models of in-app notification volume and they are never reconciled. If concurrent sessions determine who receives in-app notifications, then the channel split model is wrong; if the channel split model is right, the concurrent session arithmetic is decorative.

### 7. The escalation ladder is referenced but not shown in this document

The executive summary states the escalation ladder follows "alert → scale → shed → incident" with thresholds "ordered so each tier fires before the next is needed." Item 5 in the revision table says the escalation ladder was "redesigned." But the ladder itself does not appear in the visible document. The reader is told it exists and that its problems were fixed, without being able to verify either claim.

### 8. The spare capacity redesign is described but not shown

Item 6 in the revision table states spare capacity was "redesigned by channel with explicit failure modes." The executive summary describes this as channel-specific. Neither the spare capacity figures nor the failure modes they address appear in the visible document sections. This is a description of a fix, not the fix.

### 9. The $500/day spend cap upper bound logic is weak

The cap is set at "35% above the long-code daily estimate." The 35% figure has no stated basis — it is not derived from historical variance in security event rates, not tied to the peak factor used elsewhere (12–15×), and not connected to the billing alert thresholds of the SMS provider. A security event spike at the 13× peak factor used in 1.3 would produce ~$4,800/day, nearly 10× the cap. The cap would trigger correctly in that scenario, but the document presents it as providing headroom for "legitimate security event spikes" — which it does not at the stated peak factors.

### 10. The revision table claims ten problems were fixed, creating a false completeness signal

The document opens with a table asserting disposition of ten prior problems. Several of those fixes are either not visible in the document, incomplete (the cut-off section), or introduce new problems (the fan-out arithmetic). A reader who trusts the revision table as a completeness signal will not look for the problems that remain. The table functions as an audit trail that discourages further auditing.