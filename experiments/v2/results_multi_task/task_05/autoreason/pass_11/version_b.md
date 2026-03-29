# Incident Response Process Design
## B2B SaaS Company - Strategic Implementation Guide

---

## 1. EXECUTIVE SUMMARY

This proposal establishes a robust incident response process designed to meet your 99.95% SLA commitment while managing realistic operational constraints. Given recent incidents and customer concerns, this framework prioritizes rapid response, clear communication, and sustainable operations that can actually be executed by your team.

**Key Commitments:**
- Response time targets based on business impact with honest coverage capabilities
- Clear decision authority eliminating approval bottlenecks
- Sustainable on-call model preventing burnout while maintaining coverage

---

## 2. BUSINESS-IMPACT DRIVEN SEVERITY CLASSIFICATION

### Clear Classification with Immediate Decision Authority

**Severity 1 (Critical) - ALL conditions must be met:**
**Response Time:** 30 minutes maximum during covered hours (see Section 3 for coverage definition)
**Authority:** On-call engineer classifies immediately; no approval required

**Platform-Wide Impact Required (ALL must be true):**
- Service affects multiple customers (>10 customers OR >25% of customer base)
- Core business functionality completely inaccessible through the platform
- Verified platform cause (not user error, network issues, or third-party services)

**Technical Criteria Examples:**
- Primary database completely inaccessible
- Authentication system completely down preventing login
- Core application servers completely down
- DNS/networking preventing platform access
- Security breach with confirmed platform compromise

*Fixes Problem 1: Requires multiple customers affected AND platform cause verification to prevent over-classification from individual user issues*

**Severity 2 (High)**
**Response Time:** 2 hours maximum during covered hours
**Authority:** On-call engineer classifies immediately

**Criteria (ALL must be true for platform performance issues):**
- Verified platform cause (monitoring data confirms platform degradation)
- Performance degradation affecting multiple customers
- Error rates >15% over 30-minute window on customer-facing operations (measured by platform monitoring)
- Non-core functionality unavailable affecting multiple customers (reporting, integrations, admin features)

**OR Single-Customer High-Impact:**
- Contract value >$50K annually AND written escalation from customer's technical team citing specific platform functionality failure

*Fixes Problem 1: Requires platform verification, longer measurement window to reduce false positives, and objective contract value threshold instead of subjective "contract implications"*

**Severity 3 (Medium)**
**Response Time:** Next business day
**Criteria:** All other reported issues

### Executive Escalation (Automatic Triggers)

**Engineering Manager Notification (automatic):**
- All Sev 1 incidents (immediate notification)
- Any incident where on-call engineer requests help
- Sev 1 >4 hours: Joins as consultant (IC retains command authority)

**VP Engineering Notification (automatic):**
- Sev 1 incidents lasting >8 hours
- Customer threatens contract termination with >$100K annual contract value: Available within 4 business hours

*Fixes Problem 1: Adds objective contract value threshold for escalation triggers*

---

## 3. REALISTIC COVERAGE MODEL

### Team Size Assessment and Sustainable Rotation Math

**Coverage Commitment Based on Available Team:**

**Option A: 10+ Engineers Available**
- 2-week rotations (20+ weeks between shifts accounting for vacation/sick leave)
- Business hours (08:00-18:00 company primary timezone): 30-minute response commitment
- After-hours: 2-hour response commitment

**Option B: 8-9 Engineers Available**
- 2-week rotations with Engineering Manager participating as backup consultant
- Business hours: 30-minute response commitment
- After-hours: 4-hour response commitment

**Option C: 6-7 Engineers Available**
- **3-week rotations to achieve 18-21 weeks between shifts**
- Business hours: 1-hour response commitment
- After-hours: Best effort response, may require next business day

**Option D: <6 Engineers Available**
- **Recommendation: Hire contractor or delay implementation**
- Current team size creates unsustainable rotation

*Fixes Problem 2: Response time commitments now match coverage capabilities, with explicit after-hours response times that account for realistic availability*

### Practical Coverage Schedule

**Covered Hours (Response Time Commitments Apply):**
- Business hours: 08:00-18:00 company primary timezone
- Engineering Manager available as backup consultant within 1 hour during business hours

**After-Hours Coverage:**
- Response times as defined above based on team size
- No coverage commitment during 02:00-08:00 primary timezone for teams <10 engineers

**Coverage Gaps (Explicitly Acknowledged to Customers):**
- Teams <10 engineers: 02:00-08:00 primary timezone has delayed response
- All team sizes: Response may be delayed during major holidays (defined list provided to customers annually)

*Fixes Problem 2: Eliminates contradictory commitments by matching response times to actual coverage capabilities*

### Sustainable Limits

**Individual Limits:**
- 2-3 week rotations depending on team size (see options above)
- Maximum 8 consecutive hours active incident response before mandatory handoff
- **On-call stipend: $200/week (verified legally compliant in all operating jurisdictions)**
- **Incident response work: Overtime pay per local employment law (no comp time system)**

*Fixes Problem 3: Reduces stipend to legally sustainable level and uses standard overtime pay instead of unsustainable comp time system*

---

## 4. STREAMLINED ESCALATION AND COMMUNICATION

### Communication Authority with Technical Competency

**Customer Communication Authority:**
- **Primary: On-call engineer (technical accuracy)**
- **Backup: Engineering Manager (if on-call engineer requests communication help)**
- **Templates provided for common scenarios to ensure consistent messaging**

*Fixes Problem 4: Places communication authority with technically competent person, eliminates unrealistic VP availability requirements*

**Incident Command:**
- On-call engineer becomes Incident Commander automatically
- IC authority: Technical decisions, resource requests, vendor engagement
- IC handoff: After 8 hours maximum OR when IC requests relief

### Security Incident Communication

**Security incidents require legal review for external communication:**
- **Legal counsel has 2 business days to respond with approved communication**
- **Until legal approval: No external communication beyond "We are investigating a technical issue and will provide updates when available"**
- **No technical details provided until legal clearance**

*Fixes Problem 4: Eliminates legal liability by preventing technical communications during security incidents until proper legal review*

---

## 5. INCIDENT-SPECIFIC COMMUNICATION APPROACH

### Detection and Initial Response

**Issue Detection Criteria:**
- Monitoring alert triggers automatic response
- Customer report verified by checking monitoring/logs
- Internal team identifies customer-affecting problem

#### Initial Response (Within defined response time based on coverage model)
**Subject: Service Issue - [Company] Platform**

```
We are investigating a service issue affecting [specific services/functionality].

Issue detected: [time]
Services affected: [specific list of what customers cannot do]
Current status: [investigating cause/implementing fix/monitoring resolution]

We will provide our next update within [4 hours for Sev 1, 8 hours for Sev 2].

Status page: [URL]
Support: [contact]
```

#### Progress Updates (Every 4 hours for Sev 1, every 8 hours for Sev 2 until resolved)

```
Service Issue Update - [time]

Current status: [specific progress made]
Services affected: [what customers still cannot do]
Estimated resolution: [only if confident in timeline, otherwise "continuing investigation"]

Next update: [time - 4 hours for Sev 1, 8 hours for Sev 2]
```

### Resolution Communication

```
Service Issue Resolved - [time]

Issue resolved: [time]
Total duration: [duration]
Cause: [brief technical explanation - non-security incidents only]

All services have been restored. We will conduct a full investigation and share findings within 4 business weeks.
```

---

## 6. SIMPLIFIED TIMEZONE HANDOFF

### State-Based Handoff Protocol

**Routine Handoff (Beginning of each shift):**
```
Handoff [Date] [Time]
Active incidents: [List with current Incident Commander]
Recent monitoring alerts: [Anything trending toward thresholds]
Handoff contact: [Primary phone for next 1 hour]
```

**Active Incident Handoff:**
- **Handoff timing: After 8 hours maximum OR when IC requests relief**
- **Handoff method: 10-minute phone call + written status in incident channel**
- **Previous IC available for questions for 2 hours after handoff**

**Limited Timezone Coverage:**
- **For teams <10 engineers: Explicitly communicate to customers that overnight response may be delayed**
- **Engineering Manager takes phone consultation role during coverage gaps**

---

## 7. FOCUSED POST-MORTEM PROCESS

### Incident-Appropriate Analysis Timeline

**Post-Mortem Timeline Based on Impact:**
- **Sev 1 incidents: Root cause analysis within 4 business weeks**
- **Sev 2 incidents affecting >50 customers: Analysis within 4 business weeks**
- **Other Sev 2 incidents: Brief summary within 2 business weeks**
- **Sev 3 incidents: No formal post-mortem required**

*Fixes Problem 7: Allocates analysis resources based on actual impact rather than treating all incidents equally*

### Streamlined Review Process

**Post-Mortem Document:**
```
# [Incident Title] - [Date]

## Customer Impact Summary
- Duration: [start to full resolution]
- Services affected: [specific functionality unavailable]
- Customer experience: [what customers could not do]
- Estimated customers affected: [number]

## Timeline (Key Events Only)
- [Detection time and method]
- [Major troubleshooting steps]
- [Resolution implementation]
- [Full service restoration]

## Root Cause Analysis
- Technical cause: [specific system/code/configuration failure]
- Detection gap: [why wasn't this caught earlier]
- Response gap: [what slowed resolution]

## Prevention Plan
- Critical fixes: [changes to prevent exact recurrence - with feasibility assessment]
- Monitoring improvements: [better detection - with resource requirements]
- Process changes: [response improvements - with owner and timeline]
```

**Review Process:**
- **Sev 1 incidents: 60-minute review meeting within 2 weeks of resolution**
- **Prevention plan items: Must include resource requirements and feasibility assessment**
- **Prevention work prioritized against other engineering work through normal sprint planning**

*Fixes Problem 7: Requires resource planning for prevention work instead of assuming sprint capacity exists*

---

## 8. MONITORING AND ALERTING REQUIREMENTS

### Specific Pre-Implementation Requirements

**Required monitoring coverage before process launch:**
- **User authentication success/failure rates (measured per 5-minute interval)**
- **Core API endpoints response time >30 seconds for 10 consecutive minutes**
- **Database connection pool >90% utilization for 10 consecutive minutes**
- **Application error rates >20% over 15-minute window**
- **Primary business workflow completion rates measured daily (not real-time)**

*Fixes Problem 5: Uses longer measurement windows and higher thresholds to reduce false positives, removes real-time workflow monitoring*

**Monitoring Infrastructure:**
- **Primary: Internal monitoring system with 5-minute check intervals**
- **Secondary: External service checking login page and core API every 10 minutes**
- **Alert delivery: Email + SMS (both required, Slack optional)**
- **Historical data: 12 weeks of baseline data before process launch**

*Fixes Problem 5: Longer baseline period to capture usage patterns, more realistic check intervals*

**Monitoring Failure Protocol:**
- **If primary monitoring down >1 hour: Engineering Manager manually checks system status every 2 hours during business hours**
- **If all monitoring down: Customer reports become detection method with acknowledgment that response will be delayed**
- **Monitoring failure triggers immediate investigation as Sev 2 incident**

*Fixes Problem 5: Provides realistic manual backup with resource constraints acknowledged*

---

## 9. SLA INTEGRATION AND IMPACT

### Objective SLA Calculation Method

**Downtime Definition:**
- **Sev 1 incidents: Downtime from incident start to verified resolution**
- **Sev 2 incidents: 50% downtime weight (recognizes partial impact)**
- **Sev 3 incidents: No SLA impact**

*Fixes Problem 6: Eliminates incentive to downgrade by giving Sev 2 incidents partial SLA impact*

**Monthly SLA Calculation:**
Total uptime = (Total minutes in month - Sev 1 downtime minutes - 0.5 × Sev 2 downtime minutes) / Total minutes in month

**SLA Credit Process:**
- **Monthly uptime <99.95%: Service credits = 5% of monthly service fee**
- **Single incident >8 hours: Additional 5% credit (maximum 10% total monthly credit)**
- **Credits applied automatically to next month's invoice with brief explanation**
- **No evaluation or approval required - automatic based on downtime tracking**

*Fixes Problem 6: Caps total credits at reasonable level, extends incident threshold to 8 hours to reduce artificial closure incentive*

### Customer Communication for SLA Impact

**When SLA breach occurs:**
```
This incident caused us to miss our monthly SLA commitment of 99.95% uptime. A service credit of [X]% has been automatically applied to your next invoice. Our incident analysis will be shared within 4 business weeks.
```

---

## 10. FAILURE SCENARIOS AND DEGRADED SERVICE

### Personnel Shortage Response

**Key personnel unavailable:**
- **Primary on-call engineer unavailable: Next person in rotation takes over with extended response time commitment (+2 hours)**
- **Engineering Manager unavailable: VP Engineering provides consultation within 8 hours**
- **Both unavailable: Incident response continues with on-call engineer as sole decision maker**

*Addresses Problem 4: Provides realistic substitution timelines*

**Multiple simultaneous incidents:**
- **2 Sev 1 incidents: Engineering Manager takes command of second incident**
- **>2 Sev 1 incidents: Combine incidents into single response effort, communicate as single issue to customers**
- **Customer communication: "Multiple related technical issues are affecting our services. We are working on comprehensive resolution."**

### System Failures

**Communication systems down:**
- **Use personal phone calls for internal coordination (phone numbers collected during implementation)**
- **Customer communication delayed until systems restored - acknowledge delay in post-incident communication**
- **No customer communication during active system failures affecting communication infrastructure**

*Fixes Problem 9: Acknowledges when incident response infrastructure is affected by the incident itself*

**Third-Party Service Dependencies:**
- **Incidents caused by third-party services: Communicate vendor status and escalation efforts**
- **No SLA impact for verified third-party service outages affecting platform**
- **Customer communication: "This issue is caused by [vendor] service disruption. We are working with them on resolution and will provide updates as available."**

*Fixes Problem 9: Handles incidents where direct resolution isn't possible*

---

## 11. IMPLEMENTATION REQUIREMENTS AND SUCCESS CRITERIA

### Pre-Implementation Checklist

**Required before starting:**
- [ ] **8+ engineers committed and technically verified capable of incident response through individual technical interviews**
- [ ] **On-call stipend approved by legal/HR in all operating jurisdictions**
- [ ] **Monitoring system implemented with 12 weeks baseline data**
- [ ] **Incident tracking system configured**
- [ ] **Phone numbers collected for all participants**
- [ ] **SLA calculation system tested with historical data**

*Fixes Problem 8: Requires technical verification of engineer capabilities, legal approval of compensation*

### Training Requirements

**24-hour training per engineer over 6 weeks covering:**
- **Week 1-2: System architecture deep-dive led by senior engineers (8 hours)**
- **Week 3-4: Incident investigation using actual past incidents (8 hours)**
- **Week 5: Communication procedures with customer communication practice (4 hours)**
- **Week 6: Full incident simulation including vendor coordination (4 hours)**

*Fixes Problem 8: Increases training time to cover real-world complexities*

**Competency validation:**
- **Successfully lead response to simulated incident including customer communication**
- **Demonstrate correct escalation procedures**
- **Handle simulated monitoring failure scenario**

*Fixes Problem 8: Tests broader range of real-world scenarios*

### Success Metrics (18-month evaluation)

**Process Effectiveness:**
- **Sev 1 response time within committed timeframe: >85% of incidents**
- **Customer communication within committed timeframe: >90% of incidents**
- **Post-mortem completion within committed timeline: >85%**

**Operational Sustainability:**
- **On-call rotation coverage: <10% shift coverage gaps**
- **Engineer retention (overall team): >85% annually**
- **Prevention plan items completed within 6 months: >60%**

*Fixes Problem 10: Uses overall retention rather than program-specific retention, extends prevention timeline realistically*

**Customer Impact:**
- **Monthly SLA achievement: 99.95% uptime**
- **Customer-reported incidents vs. monitoring detected: <30