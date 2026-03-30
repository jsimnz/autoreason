Here are the real problems with this proposal:

**1. The 60-second staleness bound for opt-out is legally insufficient in some jurisdictions.**
GDPR and some CCPA interpretations require "without undue delay" processing of opt-outs, which regulators have interpreted as immediate or near-immediate for certain data processing activities. A 60-second cache TTL is presented as a compliance solution, but the proposal never cites the specific regulatory text or a legal opinion supporting this claim. It's an engineering team asserting a legal conclusion.

**2. The Week 1 baseline calibration creates a circular dependency.**
Multiplier-based alarms are calibrated to a Week 1 measured baseline, but Week 1 is precisely when you're most likely to have abnormal traffic — press coverage, invited beta users, coordinated launches. A credential stuffing attack or a viral moment during Week 1 becomes the "normal" baseline, and all subsequent thresholds are miscalibrated. The proposal doesn't address this.

**3. The digest email halt mechanism has no defined resumption SLA.**
The proposal states resumption requires sign-off from a compliance owner, but Section 7 is cut off. There's no deadline on that sign-off. A compliance owner who is unavailable for two weeks creates an indefinite halt of a product feature with no escalation path defined.

**4. The "aggressive scenario ceiling" for digest email conflates two different failure modes.**
Volume above 1.3M/day could mean opt-in data is corrupted and non-opted-in users are being emailed (a compliance emergency) or it could mean the WAND estimate was simply wrong and there are legitimately more opted-in users than modeled. The proposal treats both as identical and triggers the same halt-and-review response. This means a correct but underestimated opt-in population causes a product outage.

**5. The full breach row using MAU is internally inconsistent with the rest of the SMS model.**
The proposal explicitly states DAU is used for SMS OTP modeling because it "requires active login session." But in a full credential breach scenario, you're sending password reset messages — which also go to users based on account existence, not session activity. The justification for switching to MAU in that row ("resetting all accounts regardless of session activity") applies equally to security alerts and new device login events, which are modeled on DAU. The boundary is not principled.

**6. The proxy metric for WAND during Days 1–7 is described as a "leading indicator" but is used to justify provisioning decisions.**
The proposal says users with exactly one session in the trailing 24 hours are "a rough proxy" — then immediately uses the aggressive scenario ceiling to justify a specific provisioning cost ($80/month overage). If the proxy is acknowledged as invalid for forecasting, it cannot simultaneously justify the provisioning choice. The $80/month figure has no derivation shown.

**7. The OTP email fallback volume is listed as "variable" with no upper bound or cost model.**
When SMS is rate-limited, OTP falls back to email. The rate-limiting triggers are defined (the 4× and 7× multipliers), but there's no model for what fraction of blocked SMS attempts convert to email, what the email delivery latency is for OTP (a security-sensitive path), or what the cost ceiling is. This is a gap in both the cost table and the security model.

**8. The peak factor sensitivity analysis (3×, 5×, 8×, 10×) is mentioned in the executive summary but never appears in the document.**
The executive summary claims peak factor analysis "covers 3×, 5×, 8×, and 10×" with "explicit arithmetic." None of this appears in Sections 1 or 2. The document is incomplete and the executive summary is making claims the body doesn't support.

**9. The SQS cost model almost certainly underestimates API call volume.**
The $1,100–$2,800/month SQS estimate is stated without showing the calculation. SQS pricing is per API call, including long-poll receives that return empty. Workers continuously polling empty queues during off-peak hours generate substantial API call costs that are frequently overlooked. At 210M messages/day with batching, the send cost alone is 21M API calls/day, but the receive and delete calls double or triple that figure before accounting for empty polls.

**10. The proposal never defines what "durable" means for in-app notifications.**
In-app notifications are described as "stored, not pushed" with volume modeled as read/write load. But there's no retention policy, no definition of what happens to unread notifications when a user is inactive for 30 days, and no model for storage growth. For a system with 10M MAU and potentially 15–30 notifications per active user per day, unbounded storage growth is a real operational and cost problem within the 6-month window.

**11. Four engineers for this scope in six months is not examined anywhere.**
The proposal sizes infrastructure, defines compliance owners, names escalation paths, and designs multiple queue families with DLQs and alarm sets — but never maps any of this to the four-engineer team. There's no acknowledgment that operating this system after launch, handling the defined incident response procedures, and building it simultaneously may be beyond the team's capacity.