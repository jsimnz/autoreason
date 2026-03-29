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

## 2. OBJECTIVE SEVERITY CLASSIFICATION

### Clear Classification with Immediate Decision Authority

**Severity 1 (Critical):**
**Response Time:** 30 minutes maximum during covered hours, 4 hours maximum during coverage gaps
**Authority:** On-call engineer classifies immediately; no approval required

**Auto-Classification Triggers (no human judgment required):**
- HTTP 5xx error rate >50% for >5 minutes (if monitoring available)
- Complete authentication system failure
- Primary database completely inaccessible or connection pool exhausted
- Core application servers completely down or load balancer showing all backend servers down
- Confirmed active security breach requiring immediate containment

**Manual Classification Rule:** If monitoring is unavailable or systems are completely inaccessible, any engineer can declare Severity 1 without approval or investigation.

*Eliminates requirements for investigation, customer impact research, or approval during system failures.*

**Severity 2 (High):**
**Response Time:** 2 hours maximum during covered hours, next business day during coverage gaps

**Classification:** Significant performance degradation (>5x normal response times), partial system failures affecting customer workflows, any escalation from Support Team Lead.

**Severity 3 (Medium):**
**Response Time:** Next business day
**Classification:** All other reported issues

### Classification Decision Support

Engineers classify incidents based only on:
1. Observable system behavior
2. Available monitoring data
3. Their own judgment of system accessibility

Customer impact assessment, revenue calculations, and contract research are prohibited during incident classification.

---

## 3. REALISTIC COVERAGE MODEL WITH GEOGRAPHIC CONSIDERATIONS

### Team Availability Assessment

**Coverage calculation accounting for real availability patterns:**
- Survey all 15 engineers for actual availability preferences and timezone constraints
- Identify engineers willing to be interrupted during business hours (not all will say yes)
- Map actual working hours and timezone preferences
- Document engineers who explicitly opt out of incident response

**Minimum viable coverage commitment:**
- 4 engineers willing to cover day shifts during their normal working hours
- 2 engineers willing to cover evening shifts or provide emergency contact
- 1 engineer willing to provide night emergency contact (phone only)

### Geographic Distribution Strategy

**Response time commitments by timezone and availability:**
- Engineer in same timezone during business hours: 30-minute response target
- Engineer in different timezone during their business hours: 1-hour response
- Engineer outside business hours: 4-hour response maximum
- After-hours/weekend coverage: Emergency contact only (phone/text for true emergencies)

**Business Hours Coverage:** 8 AM - 6 PM local time, 4-hour response target (no guarantee of 30-minute response as engineers have meetings, focused work, lunch)

### Rotation Sustainability

**Participation Requirements:**
- Voluntary participation with 3-month minimum commitment, 30-day notice for changes
- Engineers specify exact hours they're willing to be contacted
- Maximum 1 week primary responsibility every 6 weeks
- Engineers can specify "emergency only" vs "all incidents" availability

**Compensation (compliant with employment law):**
- On-call stipend: $200/week (processed as salary adjustment through payroll)
- Incident response: 1.5x hourly rate for time spent on incidents outside engineer's normal business hours
- Comp time: 1:1 for incident work >2 hours, usable within 30 days when business operations permit
- All compensation follows existing employment agreements and tax classifications

---

## 4. FLEXIBLE ESCALATION WITH BACKUP AUTHORITY

### Decision Authority When Primary Contacts Unavailable

**Incident Commander Authority:**
- Any responding engineer becomes Incident Commander automatically
- IC has full authority to make technical decisions without approval
- IC has authority to communicate with customers using provided templates
- IC can engage external vendors, restart systems, implement fixes
- IC can provide service credits up to $1,000 for emergency resolution

**Customer Communication Authority with Geographic Backups:**

**Sev 1 incidents:**
```
Hour 0-2: On-call engineer uses templates
Hour 2-8: Support Team Lead (primary) → Customer Success Manager (backup) → Engineering Manager (final backup)
Hour 8+: Engineering Manager (primary) → VP Engineering (backup) → CEO (emergency)
```

**Authority Determination Protocol:**
- Try to contact person for 30 minutes maximum
- If no response, authority automatically transfers to next level
- Emergency authority can make any incident response decision without approval
- All emergency decisions are reviewed post-incident, not blocked during incident

### Internal Escalation

**Automatic notifications with backup delivery:**
- Engineering Manager: All Sev 1 incidents (Slack + email + SMS if no response in 30 minutes)
- VP Engineering: Sev 1 incidents >4 hours (email + SMS)
- CEO: Customer threatening contract termination OR security breach (phone call + email)

**Escalation response commitment:**
- Engineering Manager: Available for consultation within 2 hours (business hours) or 6 hours (after hours)
- If escalated person confirms unavailability: Incident continues with current authority level

---

## 5. SYSTEM-INDEPENDENT COMMUNICATION

### Flexible Communication Templates

**Communication when systems are down:**
- Primary: Personal phone and email accounts of on-call engineer
- Backup: Engineering Manager's personal phone
- Emergency: CEO's personal phone (for customer escalations)

**Initial Response (uses available information only):**
```
Subject: Service Issue - [Company] Platform

We are investigating a service issue affecting our platform.

Issue detected: [time]
Current status: [investigating/implementing fix/monitoring]

We will provide an update within 4 hours or when we have significant progress to report.

Emergency contact: [engineer's direct phone]
```

**Progress Updates (every 4 hours):**
```
Service Issue Update - [time]

Current status: [brief description of progress]

[Include only if known:]
- Services affected: [if identified]
- Expected resolution: [only if confident]

Next update: [within 4 hours]
```

**No requirements for:**
- Customer count affected
- Revenue impact
- Specific technical details
- Access to status pages or support systems

### Security Incident Communication with Legal Flexibility

**Immediate response protocol:**
- Hour 0: IC determines if potential security breach, contacts legal counsel via email + emergency phone
- Hour 2: If legal counsel unavailable, use holding statement and proceed with technical response
- Hour 24: Engineering Manager makes customer communication decision with available information

**Holding statement for suspected breaches:**
```
We are investigating a technical issue affecting service availability. We are conducting a thorough investigation following our security protocols. We will provide updates as information becomes available and will notify affected customers of any confirmed security impacts according to applicable requirements.
```

---

## 6. PRACTICAL TIMEZONE HANDOFF

### Handoff Protocol with No-Overlap Scenarios

**Standard handoff (when both engineers available):**
1. 15-minute handoff call with written summary
2. Incoming engineer confirms understanding and takes IC role

**No-overlap handoff scenarios:**
1. **Gap coverage protocol:** Incidents can continue without active IC for up to 8 hours if no immediate action required
2. **Immediate action required during gap:** Outgoing engineer continues until replacement available or Engineering Manager becomes IC temporarily
3. **Customer communication acknowledges handoff delays:** "Our next engineer will be available at [time] and will provide an update within 2 hours of taking over."

**Handoff Documentation Template:**
```
Incident: [ID and brief description]
Current status: [what's working, what's broken]
Actions taken: [key steps completed]
Next steps: [immediate priorities]
Customer communication: [what's been communicated, when next update due]
Key contacts: [who's been involved, escalations made]
```

**Maximum IC Duration:**
- 16 hours maximum as IC before mandatory handoff attempt
- If no replacement available after 16 hours, Engineering Manager must find coverage or declare incident resolved
- No engineer required to work more than 20 hours continuously

---

## 7. SKILL-APPROPRIATE TRAINING REQUIREMENTS

### Tiered Training by Experience Level

**Junior Engineers (0-2 years incident response experience):**
- 8 hours total training over 4 weeks
- Week 1: System architecture and monitoring tools (3 hours)
- Week 2: Incident response procedures and communication (3 hours)
- Week 3: Incident simulation with mentorship (2 hours)

**Mid-level Engineers (2-5 years experience):**
- 4 hours total training over 2 weeks
- Week 1: Company-specific architecture and monitoring (2 hours)
- Week 2: Communication procedures and incident simulation (2 hours)

**Senior Engineers (5+ years experience):**
- 2 hours total training over 1 week
- Company-specific procedures, systems overview, and IC responsibilities (2 hours)

**Training validation (all levels):**
- Successfully restart one major service using runbooks
- Send test customer communication using templates
- Demonstrate ability to contact escalation chain

**Ongoing training:**
- Monthly 30-minute review of any incidents from previous month
- Quarterly tabletop exercises (1 hour)

---

## 8. CAPACITY-BASED MULTIPLE INCIDENT HANDLING

### Incident Coordination Based on Available Staffing

**Multiple simultaneous incidents:**
1. **4+ engineers available:** Assign separate IC to each incident
2. **2-3 engineers available:** Single engineer becomes IC for highest severity incident, Engineering Manager coordinates second incident
3. **1 engineer available:** Handle highest severity incident, other incidents wait
4. **No engineers available:** Engineering Manager becomes IC or incidents wait until next business day

**Incident prioritization:**
1. Active security breaches requiring immediate containment
2. Complete system unavailability
3. Incidents affecting external monitoring (needed for SLA calculation)
4. Customer count affected (higher count = higher priority)

**Emergency staffing:**
- Engineering Manager can request volunteer engineers with $500 bonus payment
- Engineers can decline without penalty
- Maximum 4 engineers can be called for emergency response

---

## 9. MINIMUM VIABLE MONITORING

### Monitoring Requirements That Don't Create Circular Dependencies

**Required before launch:**
- External monitoring service (Pingdom, StatusCake, etc.) monitoring main application URL
- Basic uptime monitoring (ping/HTTP response) with 5-minute intervals
- External monitoring configured to email Engineering Manager and on-call engineer
- Alert delivery to personal email accounts of participating engineers

**Monitoring failure procedures:**
- Primary monitoring failure: Switch to manual checks every 2 hours during business hours
- Complete monitoring failure: Customer reports become primary detection
- Monitoring restoration is separate incident, doesn't block response to service issues

**Monitoring Improvement Timeline:**
- Phase 1 (Month 1): Basic uptime and error monitoring
- Phase 2 (Month 2-3): Performance threshold monitoring
- Phase 3 (Month 4-6): Customer impact tracking and detailed metrics

---

## 10. SPRINT-COMPATIBLE POST-MORTEM PROCESS

### Flexible Timeline Requirements

**Post-mortem completion timeline:**
- Sev 1 incidents: Written summary within 5 business days, prevention plan within 15 business days
- Sev 2 incidents: Post-mortem within 10 business days if Engineering Manager requests
- Sev 3 incidents: Optional, at Engineering Manager's discretion

**Required sections:**
1. What happened (timeline)
2. What we did to fix it
3. Suggested improvements (optional)

**Prevention Plan Sprint Integration:**
- Prevention items are added to regular product backlog with effort estimates
- Product Manager and Engineering Manager jointly prioritize against other work
- Critical fixes may interrupt current sprint; other items follow normal prioritization

---

## 11. OBJECTIVE SLA MEASUREMENT

### SLA Calculation Based on External Monitoring

**Downtime measurement:**
- Use external monitoring service as single source of truth
- If external monitoring shows service unavailable, count as downtime
- If external monitoring is working and shows service available, no downtime counted
- Customer reports of downtime are accepted at face value for SLA calculation

**Monthly SLA calculation:**
```
Availability = (Total minutes - External monitoring downtime minutes) / Total minutes
```

**Service Credit Process:**
- Monthly availability <99.95%: 10% service credit for affected customers
- Single incident >4 hours: Additional 5% credit for affected customers
- Credits calculated and applied within 30 days of month end
- Customer can request credit review if they believe impact was higher than calculated

---

## 12. IMPLEMENTATION REQUIREMENTS AND SUCCESS CRITERIA

### Pre-Implementation Checklist

**Required before starting:**
- [ ] 4+ engineers committed to day shift coverage with signed participation agreements
- [ ] 2+ engineers willing to provide evening coverage or emergency contact
- [ ] External monitoring service configured and tested
- [ ] Emergency contact list created with personal phone numbers
- [ ] Customer communication templates loaded into personal email accounts
- [ ] Support Team Lead identified and trained on communication procedures

**Success measurement (after 3 months):**
- Average response time to customer-reported incidents
- Percentage of incidents where customer communication occurred within 8 hours
- Engineer satisfaction with incident response workload (survey)
- Monthly SLA achievement rate

**Implementation Timeline:**
- Week 1: Survey engineers for availability and get commitments
- Week 2: Set up external monitoring and test communication methods
- Week 3: Conduct training for participating engineers
- Week 4: Go live with incident response process

**Monthly review:**
- Review engineer availability and update participation
- Review response times and customer feedback
- Adjust process based on actual performance vs. commitments

---

This synthesis acknowledges the fundamental constraints of limited engineering staff while establishing measurable improvements that can realistically be achieved. It focuses on providing predictable, sustainable incident response capabilities that work within actual team capacity and geographic distribution.