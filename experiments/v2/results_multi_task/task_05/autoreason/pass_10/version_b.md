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

### Clear Classification with Customer Impact Focus

**Severity 1 (Critical) - ALL of these conditions must be met:**
**Response Time:** 30 minutes maximum
**Authority:** On-call engineer classifies immediately; no approval required

**Customer Impact Criteria (ALL must apply):**
- Multiple customers affected (>1 customer)
- Core business workflow completely unavailable or data inaccessible
- Duration expected >30 minutes based on initial assessment

**Technical Criteria (Examples that typically create customer impact):**
- Primary database cluster down with failover failed
- Authentication service down affecting login for multiple customers
- Core application servers down with load balancer showing failures
- Data corruption detected in customer-facing systems

*Fixes dangerous classification inflation by requiring multiple customers affected and expected duration >30 minutes, preventing single-customer issues from triggering Sev 1.*

**Severity 2 (High)**
**Response Time:** 2 hours maximum
**Authority:** On-call engineer classifies immediately

**Criteria (ANY qualifies):**
- Single customer completely unable to access core functionality for >1 hour
- Performance degradation where customer workflows take >60 seconds (measurable via application logs, not response times)
- Error rates >10% over 15-minute window on customer-facing operations (specific measurement window defined)
- Non-core functionality unavailable affecting multiple customers (reporting, integrations, admin features)
- Customer executive escalation with contract implications

*Fixes unmeasurable performance thresholds by using concrete 60-second workflow time and specific error rate measurement window.*

**Severity 3 (Medium)**
**Response Time:** Next business day
**Criteria:** All other reported issues

*Fixes technical/customer criteria conflict by focusing classification on observable customer impact rather than internal technical state.*

### Executive Escalation (Automatic Triggers)

**Engineering Manager Notification (automatic):**
- All Sev 1 incidents (immediate notification)
- Any incident where on-call engineer requests help
- Sev 1 >4 hours: Joins as consultant (IC retains command authority)

**VP Engineering Notification (automatic):**
- Sev 1 incidents lasting >8 hours (reduced from 12 to prevent artificial closure)
- Customer threatens contract termination: Joins next scheduled business call

*Fixes perverse incentives by reducing VP notification trigger to 8 hours and making VP participation scheduled rather than immediate.*

---

## 3. REALISTIC COVERAGE MODEL

### Team Size Assessment and Sustainable Rotation Math

**Coverage Options Based on Available Team:**

**Option A: 10+ Engineers Available**
- 2-week rotations (5 rotation cycles = 10 weeks between shifts)
- Full timezone coverage sustainable

**Option B: 8-9 Engineers Available**
- 2-week rotations with 25% engineering management participation in rotation
- Single timezone primary coverage
- Cross-timezone: Delayed response acknowledged upfront

**Option C: 6-7 Engineers Available**
- **Recommendation: 3-week rotations to achieve 18-21 weeks between shifts**
- Engineering Manager participates as backup only (not primary on-call)
- Coverage gaps: Acknowledge 8-hour daily gaps with customer communication

**Option D: <6 Engineers Available**
- **Recommendation: Hire contractor or delay implementation**
- Rotation frequency would be unsustainable

*Fixes rotation math impossibility by using 2-3 week rotations and calculating actual time between shifts. Removes unrealistic expectation of managers as technical ICs.*

### Practical Coverage Schedule

**Business Hours (08:00-18:00 company primary timezone):**
- 1 engineer primary
- Engineering Manager available as backup consultant (not hands-on responder)

**After-Hours:**
- 1 engineer on-call (responds within 1 hour for Sev 1, within 2 hours for Sev 2)
- Engineering Manager available by phone for consultation only

**Coverage Gaps (Acknowledged and Communicated):**
- 02:00-08:00 primary timezone: Response may be delayed up to 2 hours
- Cross-timezone incidents: Response coordinated via phone/Slack until primary timezone coverage begins
- **Customer communication template addresses coverage limitations transparently**

### Sustainable Limits

**Individual Limits:**
- 2-3 week rotations depending on team size (see options above)
- Maximum 8 consecutive hours active incident response before mandatory handoff to Engineering Manager
- **Compensation: $500/week on-call stipend + automatic comp time 1:1 for any incident work >1 hour outside business hours**
- **Comp time automatically added to time tracking system, no approval required**

*Fixes management IC unrealism by making Engineering Manager backup consultant only. Increases stipend and lowers comp time threshold to 1 hour.*

---

## 4. STREAMLINED ESCALATION AND COMMUNICATION

### Single Point Communication Authority

**Customer Communication Authority:**
- **Primary: Designated Customer Success Manager (named individual, not role)**
- **Backup: VP Engineering (if CSM unavailable within 30 minutes)**
- **No cascade beyond these two people**

*Fixes communication cascade delays by limiting to two people maximum and naming specific individuals.*

**Communication Content Authority:**
- **Technical details: On-call engineer provides facts only**
- **Customer messaging: CSM/VP Engineering crafts customer-appropriate language**
- **No templates - each incident requires specific messaging based on actual customer impact**

*Fixes template inadequacy by eliminating generic templates in favor of incident-specific messaging.*

**Incident Command:**
- On-call engineer becomes Incident Commander automatically
- IC authority: Technical decisions, resource requests, vendor engagement
- IC handoff: After 8 hours maximum OR when IC requests relief

### Security Incident Communication

**Security incidents require legal review for external communication:**
- **Legal counsel has 4 business hours to respond**
- **If legal doesn't respond: VP Engineering provides factual technical update only: "We are investigating a technical issue affecting [specific services]. Investigation is ongoing."**
- **No speculation about security, data access, or impact in any communication until legal clearance**
- **After 24 hours: CEO makes communication decision regardless of legal response**

*Fixes impossible legal timelines by extending to 4 business hours and removing legal override mechanisms that create liability.*

---

## 5. INCIDENT-SPECIFIC COMMUNICATION APPROACH

### Detection and Initial Response

**Issue Detection Criteria:**
- Monitoring alert triggers automatic response
- Customer report verified by checking monitoring/logs
- Internal team identifies customer-affecting problem

#### Immediate Response (Within 30 minutes of detection)
**Subject: Service Issue - [Company] Platform**

```
We are investigating a service issue affecting [specific services/functionality].

Issue detected: [time]
Services affected: [specific list of what customers cannot do]
Current status: [investigating cause/implementing fix/monitoring resolution]

We are working on resolution and will update you in 2 hours with progress.

Status page: [URL]
Support: [contact]
```

*Fixes template inadequacy by requiring specific service impact rather than generic language.*

#### Progress Updates (Every 2 hours maximum until resolved)

```
Service Issue Update - [time]

Current status: [specific progress made]
Services affected: [what customers still cannot do]
Estimated resolution: [only if confident in timeline, otherwise "continuing investigation"]

Actions completed since last update:
- [specific technical steps taken]

Next update: [time - maximum 2 hours from now]
```

### Resolution Communication

```
Service Issue Resolved - [time]

Issue resolved: [time]
Total duration: [duration]
Cause: [brief technical explanation]

All services have been restored. We will conduct a full investigation and share findings within 3 business weeks.
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

*Fixes arbitrary 12-hour handoff by setting maximum at 8 hours and requiring phone handoff for active incidents.*

**Cross-timezone Coverage:**
- **If no engineers in secondary timezone: Engineering Manager takes phone consultation role until primary timezone coverage begins**
- **Acknowledge limitation in customer communication: "Our engineering team is coordinating response across timezones"**

---

## 7. FOCUSED POST-MORTEM PROCESS

### Single Timeline for All Incidents

**At Incident Resolution:**
All customers receive single timeline commitment:
- **Root cause analysis and prevention plan within 3 business weeks**
- **No different timelines based on severity - all incidents get same treatment**

*Fixes arbitrary classification timing by using single timeline for all incidents.*

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
- Immediate fixes: [changes to prevent exact recurrence - with sprint assignment]
- Monitoring improvements: [better detection - with sprint assignment]
- Process changes: [response improvements - with owner and timeline]
```

**Review Process:**
- **All incidents: 30-minute review meeting within 1 week of resolution**
- **Prevention plan items: Must have sprint assignment and owner before post-mortem is complete**
- **Customer communication: Send prevention plan summary when complete**

*Fixes enforcement weakness by requiring sprint assignment for all prevention items and simplifying review process.*

---

## 8. MONITORING AND ALERTING REQUIREMENTS

### Specific Pre-Implementation Requirements

**Required monitoring coverage before process launch:**
- **User authentication success/failure rates (measured per minute)**
- **Core API endpoints response time >10 seconds for 5 consecutive minutes**
- **Database connection pool exhaustion**
- **Application error rates >5% over 10-minute window**
- **Primary business workflow completion rates (e.g., user onboarding, data processing)**

*Fixes meaningless "basic monitoring" by specifying exact metrics and thresholds.*

**Monitoring Infrastructure:**
- **Primary: Internal monitoring system with 2-minute check intervals**
- **Secondary: External service (Pingdom/UptimeRobot) checking login page and core API every 5 minutes**
- **Alert delivery: Email + SMS + Slack/Teams (all three required)**
- **Historical data: 4 weeks of baseline data before process launch**

*Fixes inadequate baseline by extending to 4 weeks and specifying external monitoring as supplement, not replacement.*

**Monitoring Failure Protocol:**
- **If primary monitoring down >30 minutes: Switch to external service alerts + customer reports as detection methods**
- **If all monitoring down: Customer reports become primary detection method - acknowledge in incident communications**
- **No manual service checks - unsustainable and unreliable**

*Fixes impossible manual monitoring by eliminating it entirely.*

---

## 9. SLA INTEGRATION AND IMPACT

### Objective SLA Calculation Method

**Downtime Definition:**
- **Sev 1 incidents: Full downtime for entire incident duration**
- **Sev 2 incidents: No SLA impact (by definition, these don't affect core functionality for multiple customers)**
- **Sev 3 incidents: No SLA impact**

*Fixes case-by-case evaluation nightmare by making SLA impact automatic based on severity classification.*

**Monthly SLA Calculation:**
Total uptime = (Total minutes in month - Sev 1 downtime minutes) / Total minutes in month

**SLA Credit Process:**
- **Monthly uptime <99.95%: Service credits = 10% of monthly service fee**
- **Single incident >4 hours: Additional 5% credit regardless of monthly calculation**
- **Credits applied automatically to next month's invoice with brief explanation**
- **No evaluation or approval required - automatic based on downtime tracking**

*Fixes undefined credit determination by making credits automatic with specific percentages.*

### Customer Communication for SLA Impact

**When SLA breach occurs:**
```
This incident caused us to miss our monthly SLA commitment of 99.95% uptime. A service credit of [X]% has been automatically applied to your next invoice. Our incident analysis will be shared within 3 business weeks.
```

*Fixes prediction impossibility by communicating only after breach and making credits automatic.*

---

## 10. FAILURE SCENARIOS AND DEGRADED SERVICE

### Personnel Shortage Response

**Key personnel unavailable:**
- **Primary on-call engineer unavailable: Next person in rotation takes over immediately**
- **Engineering Manager unavailable: VP Engineering provides consultation**
- **Both unavailable: Incident response continues with on-call engineer as sole decision maker**

*Fixes unrealistic substitution by removing external consultant option and maintaining single command structure.*

**Multiple simultaneous incidents:**
- **2 Sev 1 incidents: Engineering Manager takes command of second incident**
- **>2 Sev 1 incidents: Triage by customer count affected - largest impact gets priority**
- **Customer communication: "Multiple critical incidents are affecting our services. We are prioritizing resolution by customer impact."**

*Fixes naive prioritization by using simple customer count metric instead of complex categories.*

### System Failures

**Communication systems down:**
- **Use personal phone calls for internal coordination (phone numbers collected during implementation)**
- **Delay customer communication until systems restored - focus on technical resolution**
- **Post-incident: Send comprehensive communication explaining communication delays**

*Fixes communication boundary issues by collecting phone numbers upfront and accepting communication delays.*

---

## 11. IMPLEMENTATION REQUIREMENTS AND SUCCESS CRITERIA

### Pre-Implementation Checklist

**Required before starting:**
- [ ] **6+ engineers committed to on-call participation (verified through individual conversations, not group meetings)**
- [ ] **Named Customer Success Manager designated and trained on incident communication (specific person, not role)**
- [ ] **Monitoring system implemented with 4 weeks baseline data**
- [ ] **Incident tracking system configured (Jira, PagerDuty, or equivalent)**
- [ ] **Phone numbers collected for all participants**
- [ ] **SLA calculation spreadsheet tested with sample data**

*Fixes undefined implementation by requiring individual engineer commitment verification and specific person designation.*

### Training Requirements

**16-hour training per engineer over 4 weeks covering:**
- **Week 1: System architecture deep-dive led by senior engineers (4 hours)**
- **Week 2: Incident investigation techniques using actual past incidents from your systems (4 hours)**
- **Week 3: Communication procedures with role-playing using real customer scenarios (4 hours)**
- **Week 4: Full incident simulation using production-like environment (4 hours)**

*Fixes inadequate training by doubling time and requiring system-specific content from senior engineers.*

**Competency validation:**
- **Successfully lead response to simulated incident within 30 minutes (practical test only)**
- **Demonstrate correct escalation procedures under time pressure**
- **No written tests - practical demonstration only**

*Fixes academic burden by eliminating written tests and focusing on practical demonstration.*

### Success Metrics (12-month evaluation)

**Process Effectiveness:**
- **Sev 1 response time <30 minutes from detection: >80% of incidents**
- **Customer communication within 30 minutes of incident detection: >90% of incidents**
- **Post-mortem completion within 3 business weeks: >90%**

*Fixes gaming-prone metrics by using detection time and extending evaluation to 12 months.*

**Operational Sustainability:**
- **On-call rotation coverage: <5% shift gaps**
- **Engineer retention in on-call program: >80% after 12 months**
- **Prevention plan completion: >80% of committed items completed within assigned sprint**

**Customer Impact:**
- **Monthly SLA achievement: 99.95% uptime**
- **Repeat incidents (same technical root cause within 6 months): <5% of total incidents**
- **Customer contract renewals not affected by incident response: >95%**

*Fixes weak proxies by using retention and contract renewal data instead of satisfaction surveys.*