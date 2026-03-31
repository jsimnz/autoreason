## Real Problems with This Proposal

### 1. The 180–900 Opt-Out Violation Estimate Has No Derivation

Section 2.4 states the preference cache produces 180–900 violations per day, but the document never shows how this number was calculated. What cache TTL produces this range? What assumption about opt-out event frequency? What user population is the denominator? The number is presented as if it were derived, but no derivation appears anywhere in the document. A legal team being asked to make a binary architectural decision based on this figure cannot evaluate whether it is plausible, conservative, or wildly optimistic.

### 2. The Spike Model Acknowledges It Is Not Conservative, Then Proceeds As If It Is

The document explicitly states "The planning basis spike model is therefore not conservative" after showing the 8%/5min scenario produces a 3+ hour delay. It then continues to use the 5%/10min planning basis anyway. The stated mitigation — monitor from Month 2, revisit if wrong — means the system launches with a known inadequate model and no defined response timeline. "Revisit worker sizing" is not a contingency plan; it is deferral.

### 3. The SMS Budget Problem Is Understated in Its Own Framing

The document calls $67.5K/month the "realistic worst-case under aggressive authentication policy." But OTP-on-every-login is not an unusual policy — it is standard for apps with any security posture. Framing this as a worst case implies a more lenient authentication policy is the expected baseline, which is never justified. If the planning basis of ~$17K/month assumes infrequent SMS OTP usage, the document needs to state what authentication frequency that assumes. Without that, the $17K figure is not a planning basis — it is a hope.

### 4. The Self-Hosted Email Fallback Cost Arithmetic Is Wrong

The document states SES pricing at ~$0.10/1K emails = ~$325/day, then states SendGrid enterprise is "$3,250–6,500/day." This makes SES appear 10–20× cheaper. But $0.10/1K = $0.0001/email. At 3.25M emails/day: 3,250,000 × $0.0001 = $325/day. SendGrid at $0.001–0.002/email at volume: 3,250,000 × $0.001 = $3,250/day. The arithmetic is correct but the framing presents this as a cost advantage for self-hosting without accounting for the engineering labor to maintain deliverability operations indefinitely — not just the 6–8 week build cost. The ongoing operational cost of owning deliverability (bounce handling, IP reputation, blocklist monitoring, DMARC reporting) is not quantified anywhere.

### 5. The Month 2 Calibration Checkpoint Is Incomplete — The Document Cuts Off

The checkpoint section defines what is measured and begins listing thresholds, then ends mid-sentence: "Peak arrival rate ≥ 2,500/sec sustained over 3" — over 3 what? Minutes? Days? The threshold is undefined. This is the primary mechanism cited for detecting sustained overload before it becomes catastrophic, and it is literally truncated. Whatever follows that sentence — the response protocol, escalation path, and worker-scaling trigger — is absent from the document.

### 6. The Broadcast Cap Enforcement Creates an Unresolved Governance Gap

The document states the 100K recipient cap is enforced at the API validation layer and that a named product owner is required as the decision gate for exceptions. It also states that without a named owner, the cap is policy with no exceptions. This creates a situation where a legitimate business need (a 500K recipient promotional push, for example) has no defined path to approval or architectural support — it simply cannot happen. The document treats "no exceptions" as a safe default, but it is actually an undisclosed product constraint that product stakeholders may not realize they are accepting when they sign off on this document.

### 7. The DAU/MAU Sensitivity Table Obscures a Real Risk With Its Own Logic

The document notes that email volume varies only 6% across DAU/MAU scenarios, then correctly explains this is an artifact of holding the 30% re-engagement send rate constant. But it does not note the inverse problem: if the app grows faster than expected and the team reduces re-engagement cadence (as the document suggests they might want to), the cost structure changes in a way this table cannot represent. The table is presented as a sensitivity analysis, but it only varies one input (DAU/MAU) while holding the more consequential input (re-engagement send rate) fixed. It does not analyze sensitivity to the variable that actually drives email cost at scale.

### 8. E2 Owns the SendGrid Contract Negotiation With No Fallback Owner

The document assigns SendGrid contract negotiation to E2 with a hard Month 1 deadline, and assigns E1 the responsibility of presenting the self-hosted tradeoff if the contract is not executed. This means if E2 is unavailable, sick, or leaves the team in Month 1, there is no named backup. For a procurement dependency described as a "Day 1 requirement," assigning it to a single engineer with no redundancy is an organizational single point of failure the document does not acknowledge.

### 9. The Legal Compliance Flags for International SMS Are Raised and Then Abandoned

Section 1.1 correctly notes that TCPA applies to US numbers and that different rules apply in the EU, UK, India, and other markets, stating "the SMS architecture must account for the user's country." This is accurate and important. The document then says this is out of scope and moves on. But the SMS architecture described elsewhere in the document (to the extent it is described) does not appear to include any country-of-origin routing or per-country compliance logic. The flag is raised and the problem is explicitly not addressed, leaving the system as designed potentially non-compliant for any non-US SMS recipient.