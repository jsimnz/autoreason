## Real Problems with This Proposal

### 1. The Gate Items Register Has No Enforcement Mechanism

The register states that unresolved gates block launch, but the document also says "the team lead is responsible for filling each role slot before Week 2 of Month 1." There is no stated consequence if the team lead fails to do this. The gate system depends entirely on a single unnamed person voluntarily completing an assignment with no accountability structure above them. This is not a process; it is a wish.

### 2. The ⚠ Flag on the Working Assumption Is Presented as a Feature

The document explicitly acknowledges the working assumption cell (30% DAU/MAU, 15/day) is flagged ⚠, then characterizes this as "honest." A working assumption that immediately triggers a re-sizing review flag is not a conservative working assumption — it is an already-stressed baseline. The document presents this as intellectual honesty rather than treating it as a problem requiring resolution before the design proceeds.

### 3. The Peak Factor Derivation Is Promised but Not Present

The executive summary states the 6× peak factor is "derived from first principles using diurnal load distribution in Section 1.4." Section 1.4 does not appear anywhere in the document. This is a critical missing section — the provisioned floor of 4,200/sec is entirely dependent on this factor, and the derivation is simply absent.

### 4. The Sensitivity Table Contains an Internal Inconsistency

The ⚠ threshold is defined as sustained average exceeding 490/sec. The table shows 20% DAU/MAU at 20/day as ~463/sec flagged ⚠, but 30% DAU/MAU at 10/day as ~347/sec flagged ✓. That is consistent. However, 20% DAU/MAU at 25/day is shown as ~579/sec flagged ⚠, when by the stated criterion (above 700/sec = ✗) it should be ⚠. That particular cell appears correct. But 40% DAU/MAU at 15/day is shown as ~694/sec flagged ⚠ — this is below 700/sec so ⚠ is correct — yet this is 99% of the threshold. The table creates the impression of analytical precision while several cells sit within rounding error of the flag boundary, and the document provides no guidance on how to handle borderline cases.

### 5. Email Volume Section Is Truncated Mid-Sentence

The document ends abruptly: "Using DAU as the base understates email volume by" — the sentence is incomplete. This is not a minor formatting issue. Email volume feeds directly into provider contract sizing, IP warm-up scheduling, and the GATE-1 consequence path. The entire email cost and capacity model is missing.

### 6. The SMS Spend Cap Calculation for Configuration C Is Not Present

The revision notes claim "(5) Configuration C SMS spend cap at launch is calculated and stated." It is not stated anywhere in the visible document. The executive summary says "Configuration C requires a two-phase cap covering launch period and steady state" and Section 1.3b is titled to cover SMS spend caps, but Section 1.3b ends before reaching any SMS spend figures. The revision note is false.

### 7. The In-App Fraction Correction Is Asserted, Not Derived

The document argues that notification events correlate with user activity, which is structurally plausible. But the correction from ~2.5% (naive) to 6.5% (working figure) is not derived — it is justified by citing a range from external reports and picking a midpoint. The structural argument explains why the naive model is wrong in direction, not in magnitude. The 6.5% figure could be 4% or 9% under the same argument, and the document provides no basis for preferring 6.5% over any other value in the 5–8% range.

### 8. The Citation Fix for Airship Is Not Verifiable as Described

The document states the Airship "Notification Benchmarks Report 2022" reports in-session delivery rates across app categories. Airship's published reports under that title do not straightforwardly report in-app delivery rates broken out by channel substitution behavior in the way the document implies. The document explicitly criticized a prior citation for being unverifiable, then replaced it with a citation that makes a specific empirical claim without sufficient detail to locate or verify the finding. The problem identified in review is reproduced, not solved.

### 9. Six Months for Four Engineers Is Never Stress-Tested Against the Scope

The document is described as a design for a 10M MAU system built by 4 engineers in 6 months. The gate items alone — five separate decisions requiring named owners, runbook entries, and recorded sign-offs — consume coordination overhead that is never accounted for. Separate APNs and FCM worker tiers, a phased SMS cap system, email provider procurement with IP warm-up, and a sensitivity monitoring regime are described as if implementation time is unconstrained. The staffing constraint is stated once and then ignored throughout.

### 10. The Escalation Threshold Creates a False Precision Problem

The single 80% capacity threshold is presented as an improvement over multiple thresholds because it "eliminates operator ambiguity." But 80% of provisioned capacity is only unambiguous if provisioned capacity is a fixed number. The document explicitly describes provisioned capacity as subject to revision based on gate resolutions and sensitivity flag triggers. An operator monitoring at 80% of a number that the design says may need to change has no clear reference point. The simplification solves the wrong problem.

### 11. GATE-2 and GATE-3 Have the Same Deadline But Sequential Dependencies

GATE-2 (app type confirmation) must resolve before the notifications-per-user figure is locked. GATE-3 (session time data) affects in-app fraction, which also depends on app type. Both are due Week 4 of Month 1. If GATE-2 resolves at the deadline and the answer is messaging-primary, GATE-3's session time data needs to be reinterpreted under a different app model — but there is no time built in for that reanalysis before downstream sizing must proceed. The deadlines assume parallel resolution of sequentially dependent questions.