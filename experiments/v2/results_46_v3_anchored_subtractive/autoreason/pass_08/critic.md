## Real Problems

### 1. The WAF "step function" model is not actually a step function

The proposal states the attacker is "at full volume from the first second" and dismisses gradual-ramp modeling. But WAF propagation is acknowledged to take "≤ 1 minute." During that minute, 2,500/sec × 60 seconds = 150,000 SMS messages could be sent — exceeding the entire daily cap of 100,000 before the primary alarm at 200/sec has meaningfully constrained anything. The alarm gives "visibility before WAF automation takes over," but WAF automation may arrive after the damage is done. The proposal does not address this.

### 2. The authenticated-account attack path has no automated response

The proposal states that reaching 800/sec with authenticated accounts "requires 80 compromised accounts" and defers detection to "a separate system, not in scope here." But the Lambda fires at 800/sec regardless of whether the account anomaly system detected anything. Once the Lambda fires and lowers the SMS cap to 10K/day, legitimate SMS traffic (auth, security events) is also throttled. The proposal does not address what happens to legitimate users during a cap-lowering triggered by authenticated attackers — users who may need SMS OTP to log in during the very incident that caused the attack.

### 3. The document ends mid-sentence

The final sentence reads: "A second worker picks up the" — the document cuts off. Finding 9 from Revision 4 was described as "complete resolution provided," but the section containing that resolution is absent. The executive summary claims this was resolved. It was not.

### 4. E3 and E4 backup gaps are asserted as "None identified" without demonstration

The table states E3 has no gaps backing E4, and E4 has no gaps backing E3. This is the same logical error the proposal corrected for E2 backing E1 in Finding 7. No enumeration of what E3 must know to handle Email/SMS/Twilio/SendGrid failures is provided. No enumeration of what E4 must know to handle preference management or suppression logic is provided. "None identified" is not equivalent to "none exist."

### 5. APNs certificate rotation gap mitigation depends on E4's read-only portal access, but E4 cannot unblock E1

The honest gap states: if E2 is unavailable and the certificate has not been pre-staged, E1 cannot complete rotation. The mitigation offered is that E4 can confirm whether a pre-staged certificate exists. But if E4 confirms it does not exist, E1 still cannot proceed. E4's read-only access does not change the outcome — it only tells E1 faster that they are stuck. This is described as a mitigation when it is only earlier failure detection.

### 6. Pass criterion 3 for the Lambda test has a boundary condition ambiguity

The false-positive test injects a spike to 700/sec for 5 minutes. The Lambda fires at 800/sec. The pass criterion is that the Lambda does not fire. But the proposal does not specify whether the alarm evaluation window could aggregate the 700/sec spike in a way that crosses 800/sec depending on CloudWatch metric resolution or evaluation period. If the evaluation period is 10 seconds and the metric is a sum rather than a rate, the test may be testing the wrong thing.

### 7. Scenario B load test assigns 100% slow messages to groups 1–50, but "slow" is not defined

The correlated failure scenario states messages in groups 1–50 are slow, simulating APNs degradation. The pass criteria reference "visibility_timeout (15s)" as the maximum blocking duration. But the proposal does not define what "slow" means in the test — whether it means responses that arrive in 14.9 seconds, responses that hang indefinitely, or responses that return an error after a timeout. These produce different watchdog behaviors and different redelivery patterns. The test design is underspecified for the scenario it claims to validate.

### 8. The idempotency pass criterion conflates idempotency with read-before-write

The Lambda idempotency criterion requires that firing 5 times within 10 seconds results in the cap being written "exactly once." This requires the Lambda to read the current cap value before writing, compare it, and skip the write if already set. Whether the Lambda actually does this is not stated anywhere in the proposal. The pass criterion describes a desired behavior without establishing that the implementation produces it.

### 9. The "one message per worker" throughput cost is unquantified

The proposal acknowledges this architectural choice "costs throughput" but does not quantify it. At 1,750/sec peak and a dispatch budget of 8 seconds per message, the number of workers required to sustain peak throughput without queue growth is at least 14,000 concurrent workers. Whether ECS scaling can provision that, what it costs, and whether it has been validated are not addressed. The cost is acknowledged and then dropped.