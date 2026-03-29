# Incident Response Process Design
## B2B SaaS Company - Strategic Implementation Guide

---

## 1. EXECUTIVE SUMMARY

This proposal establishes a robust incident response process designed to meet your 99.95% SLA commitment while managing realistic operational constraints. Given recent incidents and customer concerns, this framework prioritizes rapid response, clear communication, and sustainable operations that can actually be executed by your team.

**Key Commitments:**
- Response time targets based on business impact with realistic coverage capabilities
- Clear decision authority eliminating approval bottlenecks
- Sustainable on-call model preventing burnout while maintaining coverage

---

## 2. BUSINESS-IMPACT DRIVEN SEVERITY CLASSIFICATION

### Clear Classification with Immediate Decision Authority

**Severity 1 (Critical) - ALL conditions must be met:**
**Response Time:** 30 minutes maximum during covered hours, 4 hours maximum during coverage gaps
**Authority:** On-call engineer classifies immediately; no approval required

**Must meet BOTH customer impact AND technical criteria:**

**Customer Impact (BOTH required):**
- Business functionality completely unavailable (authentication, data access, or primary workflow completion)
- AND affects either: ≥10 customers OR any single customer with >$100k ARR

**Technical Criteria (ONE required):**
- Primary database completely inaccessible
- Authentication system completely down
- Core application servers completely down preventing customer access
- Confirmed security breach requiring immediate containment

*Fixes Problem #1: Eliminates "ANY qualifies" structure that created conflicting criteria. Requires both customer and technical impact to prevent minor issues from triggering maximum response.*

**Severity 2 (High)**
**Response Time:** 2 hours maximum during covered hours, next business day during coverage gaps
**Authority:** On-call engineer classifies immediately

**Customer Impact Criteria (ONE required):**
- 5-9 customers completely unable to access core functionality
- Performance degradation >300% of baseline response times affecting any customer
- Any customer escalation involving contract or renewal risk
- Non-core functionality unavailable affecting ≥20 customers

**Severity 3 (Medium)**
**Response Time:** Next business day
**Criteria:** All other reported issues

### Classification Decision Support

**Pre-built customer tier reference:**
- High-value customers (>$100k ARR): [Customer name list maintained in incident system]
- Customer count thresholds automatically calculated in incident system based on current customer base
- Core functionality definition: Authentication, primary data access, primary business workflow as defined in standard service description (not individual contract variations)

*Fixes Problem #1: Eliminates need for engineers to know individual contract details during time-critical classification.*

### Classification Review Process

**Classification can be adjusted during incident response:**
- Any team member can recommend reclassification with justification
- Engineering Manager makes final classification decision if disputed within 1 hour of request
- If Engineering Manager unavailable, classification stands until next review point

*Fixes Problem #9: Adds timing requirement for classification disputes.*

---

## 3. REALISTIC COVERAGE MODEL

### Team Size Assessment and Sustainable Rotation Math

**Coverage calculation using whole-person availability:**

**15 total engineers - 3 engineering managers - 2 junior engineers (not on-call eligible) = 10 potential on-call engineers**

**Sustainable participation calculation:**
- 10 potential engineers × 80% availability factor (vacation, sick, training, opt-outs) = 8 participating engineers
- Minimum viable rotation: 6 participating engineers
- Target rotation: 8+ participating engineers

*Fixes Problem #2: Uses whole-person math and realistic availability factors instead of incorrectly applied percentages.*

**Option A: 8+ Engineers Participating**
- 2-week rotations (16+ weeks between shifts per person)
- Coverage: Monday-Friday 8:00-20:00 company timezone
- After-hours: Best-effort 1-hour response, guaranteed 4-hour response

**Option B: 6-7 Engineers Participating**
- 3-week rotations (18-21 weeks between shifts per person)
- Coverage: Monday-Friday 8:00-18:00 company timezone
- After-hours: Engineering Manager backup only, 4-hour maximum response time

**Option C: <6 Engineers Participating**
- Business-hours-only incident response: Monday-Friday 8:00-18:00
- After-hours: Next business day response for all incidents except confirmed security breaches
- Customer communication sets clear expectation of business-hours response

*Fixes Problem #2: Acknowledges that insufficient participation requires reduced coverage rather than impossible promises.*

### Practical Coverage Schedule

**Business Hours Coverage:**
- Primary on-call engineer: 30-minute response for Sev 1, 2-hour response for Sev 2
- Engineering Manager: Available for consultation within 1 hour

**After-Hours Coverage (when staffing permits):**
- 18:00-02:00 company timezone: 1-hour target response for Sev 1
- 02:00-08:00 company timezone: 4-hour maximum response (coverage gap acknowledged)
- Customer communication explicitly states coverage hours and gap periods

*Fixes Problem #2: Aligns response time commitments with actual coverage capabilities.*

### Rotation Sustainability

**Participation Requirements:**
- Voluntary participation with 6-month minimum commitment
- Training completion required before first shift
- Maximum 2 consecutive weeks on-call, minimum 2 weeks between rotations

**Compensation:**
- $200/week base on-call stipend (reduced from unsustainable $500)
- $100/hour for incident work >30 minutes outside business hours
- Comp time: 1:1 for incident work >2 hours, no monthly cap
- Automatic rotation relief after 12 hours active incident response

*Fixes Problem #5: Creates sustainable compensation model that scales with actual work performed.*

---

## 4. STREAMLINED ESCALATION AND COMMUNICATION

### Customer Communication Authority

**Authority by incident severity (not customer tier):**

**Sev 1 incidents:**
- Initial communication: On-call engineer (using templates)
- Ongoing updates: Support Team Lead
- Executive escalation: VP Engineering (if customer requests executive contact)

**Sev 2/3 incidents:**
- All communication: Support Team Lead
- Escalation: Customer Success Manager (if available)

*Fixes Problem #3: Eliminates CSM single points of failure by making role-based rather than customer-specific assignments.*

**Communication Authority Backup:**
- Primary unavailable: Next person in chain takes responsibility immediately
- No approval required for emergency customer communication
- Engineering Manager coordinates backup assignments during business hours

### Internal Escalation

**Automatic notifications:**
- Engineering Manager: All Sev 1 incidents (immediate Slack + email)
- VP Engineering: Sev 1 incidents >4 hours (email notification)
- CEO: Customer threatening contract termination (Engineering Manager initiates)

**Escalation response times:**
- Engineering Manager: Available for consultation within 1 hour during business hours, 4 hours after-hours
- VP Engineering: Available within 4 business hours
- If escalated person unavailable: Incident continues with available personnel

*Fixes Problem #3: Provides realistic response times for escalated personnel.*

---

## 5. INCIDENT-SPECIFIC COMMUNICATION APPROACH

### Security Incident Communication

**Immediate response protocol:**
- Hour 0: Incident Commander determines if potential security breach
- Hour 0: Legal counsel notified via email + phone call
- Hour 2: If legal unavailable, use holding statement
- Hour 24: Engineering Manager makes communication decision regardless of legal response
- Hour 48: CEO makes final communication decision if regulatory notification required

**Holding statement for suspected breaches:**
```
We are investigating a technical issue that may have affected service availability. We take security seriously and are conducting a thorough investigation. We will provide updates as information becomes available.
```

*Fixes Problem #3: Provides specific timeline and escalation path that doesn't create legal liability.*

### Detection and Initial Response

#### Immediate Response (Within response time target)
**Subject: Service Issue - [Company] Platform**

```
We are investigating a service issue affecting [specific services/functionality].

Issue detected: [time]
Services affected: [specific list of what customers cannot do]
Estimated customers affected: [specific count if known, "investigating scope" if unknown]
Current status: [investigating cause/implementing fix/monitoring resolution]

Expected next update: [specific time, maximum 4 hours from now]

Status page: [URL]
Support: [contact]
```

#### Progress Updates (Every 4 hours maximum or when meaningful progress occurs)

```
Service Issue Update - [time]

Current status: [specific progress made OR "investigation continuing"]
Services still affected: [what customers still cannot do]
[Include estimated resolution ONLY if confident within 2 hours]

Actions completed since last update:
- [specific technical steps taken OR "investigation ongoing"]

Next update: [specific time, maximum 4 hours from now]
```

### Resolution Communication

```
Service Issue Resolved - [time]

Issue resolved: [time]
Total duration: [duration]
Root cause: [brief technical explanation]
Customers affected: [final count and percentage of customer base]

All services have been restored. We will provide a detailed incident report within [specific timeline based on incident severity: 5 business days for Sev 1, 10 business days for Sev 2].
```

---

## 6. TIMEZONE HANDOFF AND COVERAGE GAPS

### Documented Coverage Limitations

**Coverage hours by staffing level:**
- Full staffing (8+ engineers): Monday-Friday 8:00-20:00 company timezone, best-effort after-hours
- Reduced staffing (6-7 engineers): Monday-Friday 8:00-18:00 company timezone only
- Minimal staffing (<6 engineers): Business hours only with next-business-day after-hours response

**Coverage gap communication:**
Customer-facing status page states current coverage hours and expected response times for after-hours incidents.

*Fixes Problem #2: Makes coverage limitations explicit rather than promising impossible response times.*

### Active Incident Handoff Protocol

**Mid-incident handoff procedure:**
1. Outgoing IC provides 10-minute verbal handoff + written status
2. Incoming IC confirms understanding and takes command
3. Customer communication acknowledges handoff: "Our incident response team is continuing work on this issue with a fresh engineer taking command."
4. Previous IC available for 2 hours for questions, then fully handed off

*Fixes Problem #9: Provides specific process for mid-incident handoffs.*

**Handoff timing:**
- Maximum 8 hours as IC before mandatory handoff offered
- IC can request handoff at any time
- If no replacement available, IC continues with Engineering Manager support

---

## 7. FOCUSED POST-MORTEM PROCESS

### Simplified Timeline Requirements

**Post-mortem completion timeline:**
- Sev 1 incidents: 5 business days from resolution
- Sev 2 incidents: 10 business days from resolution
- Sev 3 incidents: 15 business days from resolution (if post-mortem required)

*Fixes Problem #4: Uses simple severity-based timelines instead of requiring contract review.*

### Streamlined Review Process

**Post-Mortem Document:**
```
# [Incident Title] - [Date]

## Customer Impact Summary
- Duration: [start to full resolution]
- Services affected: [specific functionality unavailable]
- Customer experience: [what customers could not do]
- Customers affected: [specific count and percentage]

## Timeline (Key Events Only)
- [Detection time and method]
- [Major troubleshooting steps with duration]
- [Resolution implementation]
- [Full service restoration]

## Root Cause Analysis
- Technical cause: [specific system/code/configuration failure]
- Contributing factors: [what made this worse or detection slower]
- Why not caught earlier: [monitoring gap or expected behavior]

## Prevention Plan
- Critical fixes: [changes to prevent exact recurrence - assigned to specific sprint]
- Monitoring improvements: [better detection - assigned to specific sprint]  
- Process changes: [response improvements - owner and completion date]

## Outstanding Questions
[Only if root cause cannot be determined within timeline]
- Current findings: [what is known]
- Ongoing investigation: [what is still being researched with specific owner]
- Expected completion: [realistic date for remaining investigation]
```

**Review Process:**
- 1-hour review meeting within 1 week of resolution
- Prevention plan items must have sprint assignment or explicit decision not to implement
- Customer communication includes summary of prevention actions taken

---

## 8. MONITORING AND ALERTING REQUIREMENTS

### Specific Pre-Implementation Requirements

**Required monitoring before process launch:**
- User authentication success/failure rates (alert: >15% failure rate over 10 minutes)
- Core API endpoints response time (alert: >5 seconds average over 10 minutes)
- Database connection availability (alert: any connection failures)
- Application error rates (alert: >5% over 15 minutes)
- Basic external service checking (login page and one primary workflow)

**Monitoring Infrastructure:**
- Primary: Internal monitoring with 2-minute check intervals
- Secondary: External service (Pingdom/StatusCake) with 5-minute intervals
- Alert delivery: Email + SMS + Slack (minimum two methods required)
- Historical data: 1 week minimum before process launch (reduced from unrealistic 2 weeks)

*Fixes Problem #6: Reduces circular dependency by requiring only 1 week baseline and simpler monitoring setup.*

### Monitoring Failure Protocol

**Primary monitoring system failure:**
- Switch to external service alerts immediately
- Engineering Manager coordinates manual checks with top 10 customers
- Restore primary monitoring before resuming normal incident response

**Complete monitoring failure:**
- Customer reports become primary detection method
- Engineering Manager coordinates proactive contact with enterprise customers
- Incident response continues with available information

---

## 9. SLA INTEGRATION AND IMPACT

### Objective SLA Calculation Method

**Downtime Definition:**
- Sev 1 incidents: Full downtime for duration of complete service unavailability
- Partial outages: Downtime = (incident duration) × (percentage of customers completely unable to access core functionality)
- Sev 2/3 incidents: No SLA impact unless customer contract specifically includes performance degradation

*Fixes Problem #4: Simplifies calculation to use binary availability (working/not working) rather than complex weighting.*

**Monthly SLA Calculation:**
Monthly uptime percentage = (Total minutes in month - Total downtime minutes) / Total minutes in month

**SLA Credit Process:**
- Monthly uptime <99.95%: Service credits = 10% of monthly service fee for affected customers
- Single incident >4 hours: Additional 5% credit for affected customers
- Credits calculated based on customer-reported impact if system impact data unavailable
- Credits applied to next month's invoice with incident reference

*Fixes Problem #4: Acknowledges that precise customer impact tracking may not be available and provides fallback method.*

---

## 10. FAILURE SCENARIOS AND DEGRADED SERVICE

### Personnel Shortage Response

**Staffing shortage protocol:**
- <6 engineers available: Reduce to business-hours coverage immediately
- Multiple engineers unavailable: Engineering Manager participates in rotation
- Engineering Manager unavailable: VP Engineering provides consultation
- Incident Commander unavailable mid-incident: Automatic handoff to backup engineer or Engineering Manager

*Fixes Problem #7: Eliminates assumption that volunteers exist and provides concrete backup plans.*

### Multiple Simultaneous Incidents

**Incident coordination:**
- Multiple Sev 1s: Engineering Manager becomes Incident Coordinator, individual ICs for each incident
- >2 simultaneous Sev 1s: Declare major incident status, all available engineers assigned
- Customer communication coordinated by Support Team Lead to avoid conflicting messages
- Incident prioritization: By customer count affected, then by revenue impact

*Fixes Problem #7: Provides specific coordination structure for multiple incidents.*

### Communication System Failures

**Backup communication methods:**
- Primary incident tracking system down: Use shared document with phone coordination
- Slack/Teams down: Email coordination with phone backup
- Customer communication systems down: Direct email from support team personal accounts
- All systems down: Phone tree coordination, manual customer contact list

---

## 11. IMPLEMENTATION REQUIREMENTS AND SUCCESS CRITERIA

### Pre-Implementation Checklist

**Required before starting:**
- [ ] 6+ engineers committed to on-call participation with signed agreements
- [ ] Support Team Lead identified and trained on communication procedures
- [ ] Basic monitoring system implemented with 1 week baseline data
- [ ] Incident tracking system configured with severity templates
- [ ] Customer tier list (>$100k ARR) loaded into incident system
- [ ] Phone numbers collected for all participants with backup contacts
- [ ] Status page configured with coverage hour information

*Fixes Problem #6: Reduces circular dependencies and eliminates customer contract review requirement.*

### Training Requirements

**Mandatory training (8 hours total over 2 weeks):**
- Week 1: System architecture, common failure modes, monitoring tools (4 hours)
- Week 2: Communication procedures, incident simulation, handoff practice (4 hours)

**Ongoing training:**
- Monthly 30-minute session reviewing recent incidents
- Quarterly tabletop exercises (2 hours)

**Competency validation:**
- Successfully complete incident simulation with proper communication
- Demonstrate monitoring tool usage and alert response

*Fixes Problem #5: Reduces training commitment from unrealistic 16 hours to achievable 8 hours.*

### Success Metrics (12