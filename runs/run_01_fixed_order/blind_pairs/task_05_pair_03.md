# Blind Evaluation: task_05_pair_03

## Task
Design the incident response process for a B2B SaaS company with 200 enterprise customers, a 99.95% SLA, and a 15-person engineering team split across US and EU timezones. Cover: severity levels and criteria, on-call rotation, escalation paths, communication templates (internal and customer-facing), post-mortem process, and how to handle incidents that span timezone boundaries. The company has had 3 major incidents in the past quarter and customers are losing patience.

---

## Proposal X

# Incident Response Process for B2B SaaS Enterprise Platform

## Executive Summary

This document outlines a comprehensive incident response process designed for a B2B SaaS company serving 200 enterprise customers with a 99.95% SLA commitment. The process addresses current challenges with major incidents while ensuring sustainable 24/7 coverage across US and EU timezones with a 15-person engineering team.

## 1. Incident Severity Classification

### Severity 1 (Critical)
**Criteria:**
- Complete service outage affecting all customers
- Data loss or corruption affecting multiple customers
- Security breach with confirmed data exposure
- Payment processing completely down

**Response Time:** 15 minutes
**Resolution Target:** 4 hours
**Communication:** Immediate customer notification required

### Severity 2 (High)
**Criteria:**
- Partial service outage affecting >25% of customers
- Core functionality degraded but workarounds available
- Single customer data loss/corruption
- Authentication/authorization issues
- Performance degradation >50% of normal response times

**Response Time:** 30 minutes
**Resolution Target:** 8 hours
**Communication:** Customer notification within 1 hour

### Severity 3 (Medium)
**Criteria:**
- Minor feature outages affecting <25% of customers
- Performance degradation 25-50% of normal response times
- Non-critical integrations down
- UI/UX issues not blocking core workflows

**Response Time:** 2 hours
**Resolution Target:** 24 hours
**Communication:** Status page update, proactive notification for affected customers

### Severity 4 (Low)
**Criteria:**
- Cosmetic issues
- Documentation errors
- Minor feature requests
- Performance degradation <25%

**Response Time:** Next business day
**Resolution Target:** 72 hours
**Communication:** Internal tracking only

*Kept Version A response times - aggressive but achievable with proper escalation. Removed SLA breach language per Version B since 99.95% uptime allows only 21.6 minutes/month downtime.*

## 2. On-Call Rotation Structure

### Primary On-Call Engineers
**Business Hours Coverage (9 AM - 6 PM local time):**
- US: 3 engineers (weekly rotation)
- EU: 3 engineers (weekly rotation)

**After-Hours Coverage:**
- US: 3 engineers (rotating every 2 weeks)
- EU: 3 engineers (rotating every 2 weeks)

**Weekend Coverage:** Shared rotation among all 12 on-call eligible engineers

### Secondary On-Call (Escalation)
- **US:** 1 senior engineer (bi-weekly rotation)
- **EU:** 1 senior engineer (bi-weekly rotation)
- **Cross-timezone backup:** Senior engineers provide backup during coverage gaps

### Management Escalation
- **Engineering Manager US:** Available for P1/P2 escalation
- **Engineering Manager EU:** Available for P1/P2 escalation
- **VP Engineering:** P1 incidents >2 hours, all P2 incidents >4 hours

### Incident Commander Designation
**Business Hours:** Engineering team lead in respective timezone automatically becomes IC
**After Hours:** Primary on-call engineer becomes IC unless they explicitly request escalation
**Cross-timezone incidents:** Original IC remains through natural handoff points

### On-Call Compensation
- After-hours on-call stipend: $400/week
- Weekend on-call stipend: $200/weekend
- Incident response bonus: $150 per P1, $75 per P2
- Maximum 2 consecutive weeks on-call, minimum 2 weeks off

*Adopted Version B's sustainable staffing model (12 primary + 2 secondary + 1 development-focused) but kept Version A's compensation structure with slight reduction for financial viability.*

## 3. Escalation Matrix

### Automatic Escalations
- **P1 incidents:** Auto-escalate to secondary on-call after 30 minutes
- **P2 incidents:** Auto-escalate to secondary on-call after 1 hour
- **Cross-timezone escalation:** If primary on-call doesn't respond within 15 minutes, escalate to backup timezone

### Management Escalation Triggers
- P1 incident duration >2 hours → Eng Manager + VP Engineering
- P2 incident duration >4 hours → Eng Manager
- Customer escalation received → Immediate management notification
- Media/social media attention → CEO notification

### External Escalation
- **Customer Success:** Notified for all P1/P2 incidents within 30 minutes
- **Sales:** Notified for incidents affecting >3 enterprise customers
- **Legal/Compliance:** Notified for security incidents within 1 hour

*Kept Version A escalation matrix but adopted Version B's realistic cross-timezone backup approach.*

## 4. Communication Templates and Customer Segmentation

### Customer Segmentation
**Tier 1 (Top 20 customers by ARR):** Direct phone/email notification within 30 minutes for P1, 1 hour for P2
**Tier 2 (Enterprise customers with specific SLA terms):** Email notification per contract requirements
**Tier 3 (All other customers):** Status page and standard email notifications

### Communication Approval
**P1 Incidents:** Engineering Manager approval required before Tier 1 customer notification
**P2 Incidents:** Standard templates can be sent immediately, custom communications require approval
**Legal Review Required:** Any incident involving data breach, regulatory compliance, or customer contract violations

### Internal Slack Incident Channel Template

```
🚨 INCIDENT DECLARED - P[X] 
**Summary:** [Brief description]
**Impact:** [Number of customers/services affected]
**Started:** [Timestamp]
**Incident Commander:** @[name]
**Status:** Investigating/Identified/Monitoring/Resolved

**Next Update:** [Time]
**Bridge:** [Conference link]
**Tracking:** [Ticket/Jira link]

cc: @here @engineering-managers
```

### Customer Communication Templates

#### Initial P1 Notification (Within 30 minutes for Tier 1)
**Subject:** [Service Name] Service Disruption - Investigation Underway

```
Dear [Customer Name],

We are currently experiencing a service disruption affecting [specific functionality]. Our engineering team has been alerted and is actively investigating.

**Impact:** [Specific impact to their service]
**Started:** [Time in customer's timezone]
**Next Update:** Within 30 minutes

We sincerely apologize for the inconvenience and will provide regular updates as we work toward resolution.

Status Page: [URL]
Support: [Contact information]

[Company Name] Engineering Team
```

### External Dependency Incidents
**Vendor-Caused Outages (AWS, Stripe, etc.):**
- Customer notification acknowledges external dependency
- Include vendor status page links
- Proactive communication about mitigation efforts
- No SLA penalty clauses triggered for documented vendor outages

*Adopted Version B's customer segmentation and approval workflow while keeping Version A's detailed templates. Added external dependency framework from Version B.*

## 5. Cross-Timezone Incident Handling

### Handoff Protocol
**Standard Handoff (6 PM local time):**
- Outgoing engineer posts written handoff in #incidents-handoff channel
- Incoming engineer acknowledges within 30 minutes
- No synchronous call required unless P1/P2 active

**Active Incident Handoff:**
- 15-minute overlap call required for P1/P2 incidents
- Handoff delayed until natural break point (not mid-investigation)
- Original IC remains available for 2 hours post-handoff

### Coverage Gaps
**EU Night Coverage (11 PM - 7 AM CET):** US after-hours engineer provides backup
**US Night Coverage (11 PM - 7 AM PT):** EU morning engineer (starting 8 AM CET) provides backup

### Timezone Escalation Rules
- If primary on-call in off-hours timezone doesn't respond within 15 minutes, automatically page secondary on-call in active timezone
- P1 incidents always require immediate cross-timezone notification regardless of time
- Management in both timezones notified for P1 incidents >1 hour

*Adopted Version B's realistic handoff timing (6 PM local) while keeping Version A's comprehensive escalation rules.*

## 6. Post-Mortem Process

### Timeline Requirements
- **P1 incidents:** Post-mortem initiated within 24 hours, completed within 5 business days
- **P2 incidents:** Post-mortem initiated within 48 hours, completed within 7 business days
- **Customer-impacting P3:** Post-mortem at discretion of Engineering Manager

### Post-Mortem Template

```
# Post-Mortem: [Incident Title]
**Date:** [Date]
**Authors:** [Names]
**Status:** Draft/Review/Final
**Summary:** [One-line summary]

## Impact
- **Duration:** [Start time] to [End time] ([Total duration])
- **Customers Affected:** [Number and list of major customers]
- **SLA Impact:** [Calculation against 99.95% target]

## Timeline
[Detailed timeline with timestamps and actions]

## Root Cause Analysis
**Immediate Cause:** [What directly caused the incident]
**Contributing Factors:** [What made it possible/worse]
**Root Cause:** [Underlying system/process failure]

## Resolution
[What was done to resolve the incident]

## Action Items
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| [Action 1] | [Name] | [Date] | Open/In Progress/Done |

## Lessons Learned
**What Went Well:**
- [Positive aspects]

**What Could Be Improved:**
- [Areas for improvement]

**Prevention Measures:**
- [Specific steps to prevent recurrence]

## Customer Summary
[Version safe to share with customers]
```

### Review Process
1. **Draft:** Incident Commander completes within 48 hours
2. **Review:** Engineering Manager + affected service owners review
3. **Customer Version:** Sanitized version prepared for customer sharing
4. **Final:** Published to internal wiki and shared with customers within 5 business days

*Kept Version A's comprehensive template and process but added customer summary section from Version B.*

## 7. Monitoring and Alerting Framework

### Alert Routing
- **P1 alerts:** Page primary on-call immediately, escalate to secondary after 15 minutes
- **P2 alerts:** Page primary on-call, escalate after 30 minutes
- **P3 alerts:** Slack notification to on-call channel
- **Alert grouping:** Maximum 1 page per 15-minute window per service

### SLA Monitoring
- **Real-time dashboard:** Current monthly uptime percentage
- **Early warning system:** Alert when monthly downtime >50% of budget (10.8 minutes)
- **Customer-specific SLA tracking:** Individual customer SLA dashboards for Tier 1/2 customers

*Kept Version A's alert structure but adopted Version B's improved alert grouping and early warning system.*

## 8. Training and Preparedness

### New Engineer Onboarding
- Shadow on-call rotation for 1 week
- Complete incident response simulation
- Review last 3 major post-mortems
- Certification quiz before joining rotation

### Quarterly Incident Response Drills
- **Game Day exercises:** Simulated P1 incidents
- **Cross-timezone coordination:** Practice handoffs
- **Communication drills:** Customer notification practice

### Documentation Maintenance
- **Runbooks:** Updated after each P1/P2 incident, reviewed quarterly
- **Escalation contacts:** Updated within 48 hours of personnel changes
- **Process review:** Quarterly review with engineering leadership

*Adopted Version B's realistic 1-week shadow period while keeping Version A's comprehensive training program.*

## 9. Regulatory and Compliance Framework

### Regulated Customer Requirements
**Financial Services:** Incident reports within 24 hours, specific format requirements
**Healthcare:** HIPAA breach notification procedures if PHI involved
**Government:** Security incident reporting to appropriate agencies

### Documentation Requirements
**Audit Trail:** All incident communications and decisions logged
**Compliance Reporting:** Quarterly incident summaries for enterprise customers
**Legal Hold:** Incident data retention for minimum 3 years

*Added Version B's compliance framework which was missing from Version A but essential for enterprise customers.*

## 10. Success Metrics and KPIs

### Response Time Metrics
- **Mean Time to Acknowledge (MTTA):** Target <5 minutes for P1, <15 minutes for P2
- **Mean Time to Resolution (MTTR):** Target <4 hours for P1, <8 hours for P2
- **Escalation Rate:** <25% of incidents require management escalation

### Communication Metrics
- **Customer Notification Time:** 95% within SLA targets (acknowledging some may miss due to approval workflows)
- **Status Page Updates:** <15 minutes for P1, <30 minutes for P2
- **Post-mortem Completion:** 90% within target timelines

### Quality Metrics
- **Action Item Completion:** >85% completed within due dates
- **Customer Satisfaction:** >4.0/5.0 rating on incident handling (for Tier 1/2 customers)

*Kept Version A's comprehensive metrics but adjusted targets to be achievable with approval workflows and real-world constraints.*

## 11. Implementation Timeline

### Phase 1 (Weeks 1-2): Foundation
- Implement severity classification
- Set up on-call rotations in PagerDuty with sustainable staffing
- Create Slack incident channels and templates
- Establish customer segmentation

### Phase 2 (Weeks 3-4): Process Integration
- Deploy cross-timezone handoff procedures
- Implement escalation automation
- Create customer communication templates with approval workflows
- Launch status page updates

### Phase 3 (Weeks 5-6): Optimization
- Conduct first game day exercise
- Refine post-mortem process
- Implement SLA monitoring dashboards
- Complete team training

### Phase 4 (Week 7+): Continuous Improvement
- Monthly process reviews
- Quarterly game day exercises
- Ongoing metrics analysis and optimization

*Kept Version A's implementation timeline but incorporated Version B's realistic staffing and approval workflow considerations.*

This incident response process balances operational excellence with team sustainability, acknowledging real-world constraints while maintaining the comprehensive structure needed for enterprise customers. The process prioritizes customer impact mitigation through rapid response and clear communication while ensuring long-term team health through sustainable on-call practices.

---

## Proposal Y

# Incident Response Process for B2B SaaS Enterprise Platform

## Executive Summary

This document outlines a comprehensive incident response process designed for a B2B SaaS company serving 200 enterprise customers with a 99.95% SLA commitment. The process addresses current challenges with major incidents while ensuring 24/7 coverage across US and EU timezones with a 15-person engineering team.

## 1. Incident Severity Classification

### Severity 1 (Critical)
**Criteria:**
- Complete service outage affecting all customers
- Data loss or corruption affecting multiple customers
- Security breach with confirmed data exposure
- Payment processing completely down
- SLA breach imminent (>30 minutes of P1 incident threatens monthly SLA)

**Response Time:** 15 minutes
**Resolution Target:** 4 hours
**Communication:** Immediate customer notification required

### Severity 2 (High)
**Criteria:**
- Partial service outage affecting >25% of customers
- Core functionality degraded but workarounds available
- Single customer data loss/corruption
- Authentication/authorization issues
- Performance degradation >50% of normal response times

**Response Time:** 30 minutes
**Resolution Target:** 8 hours
**Communication:** Customer notification within 1 hour

### Severity 3 (Medium)
**Criteria:**
- Minor feature outages affecting <25% of customers
- Performance degradation 25-50% of normal response times
- Non-critical integrations down
- UI/UX issues not blocking core workflows

**Response Time:** 2 hours
**Resolution Target:** 24 hours
**Communication:** Status page update, proactive notification for affected customers

### Severity 4 (Low)
**Criteria:**
- Cosmetic issues
- Documentation errors
- Minor feature requests
- Performance degradation <25%

**Response Time:** Next business day
**Resolution Target:** 72 hours
**Communication:** Internal tracking only

## 2. On-Call Rotation Structure

### Primary On-Call Engineers
**US Coverage (5 PM - 9 AM PT):** 4 engineers rotating weekly
**EU Coverage (5 PM - 9 AM CET):** 4 engineers rotating weekly
**Overlap Hours (9 AM - 5 PM PT / 6 PM - 2 AM CET):** Shared coverage

### Secondary On-Call (Escalation)
- **US:** 2 senior engineers (bi-weekly rotation)
- **EU:** 2 senior engineers (bi-weekly rotation)

### Management Escalation
- **Engineering Manager US:** Available for P1/P2 escalation
- **Engineering Manager EU:** Available for P1/P2 escalation
- **VP Engineering:** P1 incidents >2 hours, all P2 incidents >4 hours

### On-Call Compensation
- Base on-call stipend: $500/week
- Incident response bonus: $200 per P1, $100 per P2
- Maximum 2 consecutive weeks on-call, minimum 2 weeks off

## 3. Escalation Matrix

### Automatic Escalations
- **P1 incidents:** Auto-escalate to secondary on-call after 30 minutes
- **P2 incidents:** Auto-escalate to secondary on-call after 1 hour
- **Cross-timezone escalation:** If primary on-call doesn't respond within 15 minutes

### Management Escalation Triggers
- P1 incident duration >2 hours → Eng Manager + VP Engineering
- P2 incident duration >4 hours → Eng Manager
- Customer escalation received → Immediate management notification
- Media/social media attention → CEO notification

### External Escalation
- **Customer Success:** Notified for all P1/P2 incidents within 30 minutes
- **Sales:** Notified for incidents affecting >3 enterprise customers
- **Legal/Compliance:** Notified for security incidents within 1 hour

## 4. Communication Templates

### Internal Slack Incident Channel Template

```
🚨 INCIDENT DECLARED - P[X] 
**Summary:** [Brief description]
**Impact:** [Number of customers/services affected]
**Started:** [Timestamp]
**Incident Commander:** @[name]
**Status:** Investigating/Identified/Monitoring/Resolved

**Next Update:** [Time]
**Bridge:** [Conference link]
**Tracking:** [Ticket/Jira link]

cc: @here @engineering-managers
```

### Customer Communication Templates

#### Initial P1 Notification (Within 15 minutes)
**Subject:** [Service Name] Service Disruption - Investigation Underway

```
Dear [Customer Name],

We are currently experiencing a service disruption affecting [specific functionality]. Our engineering team has been alerted and is actively investigating.

**Impact:** [Specific impact to their service]
**Started:** [Time in customer's timezone]
**Next Update:** Within 30 minutes

We sincerely apologize for the inconvenience and will provide regular updates as we work toward resolution.

Status Page: [URL]
Support: [Contact information]

[Company Name] Engineering Team
```

#### Resolution Notification
**Subject:** [RESOLVED] [Service Name] Service Disruption

```
Dear [Customer Name],

The service disruption that began at [time] has been resolved as of [time].

**Root Cause:** [Brief, non-technical explanation]
**Resolution:** [What was done to fix it]
**Prevention:** [Steps being taken to prevent recurrence]

**Total Duration:** [X hours Y minutes]

We deeply apologize for the impact to your business. A detailed post-mortem will be shared within 48 hours.

[Company Name] Engineering Team
```

### Status Page Templates

#### P1 Incident
```
🔴 Major Service Disruption
We are experiencing a major service disruption affecting [functionality]. 
Our engineering team is actively working on resolution.
Started: [Time]
Next update: [Time]
```

#### P2 Incident
```
🟡 Service Degradation
We are experiencing degraded performance in [functionality]. 
Some users may experience [specific impact].
Started: [Time]
Next update: [Time]
```

## 5. Cross-Timezone Incident Handling

### Handoff Protocol
1. **30 minutes before shift end:** Outgoing IC posts comprehensive handoff summary
2. **Handoff summary must include:**
   - Current status and actions taken
   - Outstanding action items with owners
   - Customer communications sent
   - Management notifications made
   - Bridge information and key contacts

### Follow-the-Sun Coverage
- **US → EU Handoff (5 PM PT / 2 AM CET):** 
  - Slack handoff + 15-minute overlap call for P1/P2
  - Email summary for P3/P4
- **EU → US Handoff (5 PM CET / 8 AM PT):**
  - Slack handoff + overlap call during US morning standup

### Timezone Escalation Rules
- If primary on-call in off-hours timezone doesn't respond within 15 minutes, automatically page secondary on-call in active timezone
- P1 incidents always require immediate cross-timezone notification regardless of time
- Management in both timezones notified for P1 incidents >1 hour

## 6. Post-Mortem Process

### Timeline Requirements
- **P1 incidents:** Post-mortem initiated within 24 hours, completed within 5 business days
- **P2 incidents:** Post-mortem initiated within 48 hours, completed within 7 business days
- **Customer-impacting P3:** Post-mortem at discretion of Engineering Manager

### Post-Mortem Template

```
# Post-Mortem: [Incident Title]
**Date:** [Date]
**Authors:** [Names]
**Status:** Draft/Review/Final
**Summary:** [One-line summary]

## Impact
- **Duration:** [Start time] to [End time] ([Total duration])
- **Customers Affected:** [Number and list of major customers]
- **Revenue Impact:** [$X estimated]
- **SLA Impact:** [Calculation against 99.95% target]

## Timeline
[Detailed timeline with timestamps and actions]

## Root Cause Analysis
**Immediate Cause:** [What directly caused the incident]
**Contributing Factors:** [What made it possible/worse]
**Root Cause:** [Underlying system/process failure]

## Resolution
[What was done to resolve the incident]

## Action Items
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| [Action 1] | [Name] | [Date] | Open/In Progress/Done |

## Lessons Learned
**What Went Well:**
- [Positive aspects]

**What Could Be Improved:**
- [Areas for improvement]

**Prevention Measures:**
- [Specific steps to prevent recurrence]
```

### Review Process
1. **Draft:** Incident Commander completes within 48 hours
2. **Review:** Engineering Manager + affected service owners review
3. **Customer Version:** Sanitized version prepared for customer sharing
4. **Final:** Published to internal wiki and shared with customers within 5 business days

### Action Item Tracking
- All action items tracked in Jira with "post-mortem" label
- Weekly review in engineering standup
- Monthly executive summary of completion rates

## 7. Monitoring and Alerting Framework

### Alert Routing
- **P1 alerts:** Page primary on-call immediately, escalate to secondary after 5 minutes
- **P2 alerts:** Page primary on-call, escalate after 15 minutes
- **P3 alerts:** Slack notification to on-call channel
- **Alert fatigue prevention:** Maximum 5 pages per hour, then escalate to secondary

### SLA Monitoring
- **Real-time dashboard:** Current monthly uptime percentage
- **SLA burn rate alerts:** Trigger when monthly SLA at risk
- **Customer-specific SLA tracking:** Individual customer SLA dashboards

## 8. Training and Preparedness

### New Engineer Onboarding
- Shadow on-call rotation for 2 weeks
- Complete incident response simulation
- Review last 3 major post-mortems
- Certification quiz before joining rotation

### Quarterly Incident Response Drills
- **Game Day exercises:** Simulated P1 incidents
- **Cross-timezone coordination:** Practice handoffs
- **Communication drills:** Customer notification practice
- **Chaos engineering:** Controlled failure injection

### Documentation Maintenance
- **Runbooks:** Updated monthly, reviewed quarterly
- **Escalation contacts:** Updated immediately when personnel changes
- **Process review:** Quarterly review with engineering leadership

## 9. Success Metrics and KPIs

### Response Time Metrics
- **Mean Time to Acknowledge (MTTA):** Target <5 minutes for P1, <15 minutes for P2
- **Mean Time to Resolution (MTTR):** Target <4 hours for P1, <8 hours for P2
- **Escalation Rate:** <20% of incidents require management escalation

### Communication Metrics
- **Customer Notification Time:** 100% within SLA targets
- **Status Page Updates:** <15 minutes for P1, <30 minutes for P2
- **Post-mortem Completion:** 100% within target timelines

### Quality Metrics
- **Repeat Incidents:** <10% of incidents are repeats within 30 days
- **Action Item Completion:** >90% completed within due dates
- **Customer Satisfaction:** >4.0/5.0 rating on incident handling

## 10. Implementation Timeline

### Phase 1 (Weeks 1-2): Foundation
- Implement severity classification
- Set up on-call rotations in PagerDuty
- Create Slack incident channels and templates
- Train initial on-call engineers

### Phase 2 (Weeks 3-4): Process Integration
- Deploy cross-timezone handoff procedures
- Implement escalation automation
- Create customer communication templates
- Launch status page updates

### Phase 3 (Weeks 5-6): Optimization
- Conduct first game day exercise
- Refine post-mortem process
- Implement SLA monitoring dashboards
- Complete team training

### Phase 4 (Week 7+): Continuous Improvement
- Monthly process reviews
- Quarterly game day exercises
- Ongoing metrics analysis and optimization

This incident response process is designed to restore customer confidence through predictable, professional incident handling while maintaining team sustainability across timezones. Regular review and iteration based on actual incident data will ensure continuous improvement.
