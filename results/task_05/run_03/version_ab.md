# Incident Response Process Design for B2B SaaS Company

## Executive Summary

This document outlines a comprehensive incident response process designed for a B2B SaaS company with 200 enterprise customers, a 99.95% SLA commitment, and distributed engineering teams across US and EU timezones. The process emphasizes realistic response targets, clear decision-making authority, and systematic resolution while maintaining customer trust through transparent, proactive engagement.

## 1. Incident Severity Classification

### Severity 1 - Critical (P1)
**Criteria:**
- Complete service outage affecting >50% of customers
- Data loss or corruption affecting any customer
- Security breach or suspected breach
- Any issue preventing customers from accessing core functionality during business hours
- SLA breach imminent or in progress (>26.3 minutes of downtime per month)

**Initial Response Target:** 30 minutes during business hours, 60 minutes off-hours
**Resolution Target:** Best effort based on technical complexity
**Communication:** Customer notification within 2 hours of impact confirmation

*[Uses Version B's realistic response times while keeping Version A's specific SLA-based criteria]*

### Severity 2 - High (P2)
**Criteria:**
- Partial service degradation affecting >25% of customers
- Core functionality impaired but workarounds available
- Performance degradation >200% of baseline response times
- Single-customer critical issues for enterprise accounts
- Non-core service outages during business hours

**Initial Response Target:** 2 hours during business hours, 4 hours off-hours
**Resolution Target:** Best effort based on technical complexity
**Communication:** Customer notification within 4 hours if customer-facing

*[Uses Version B's realistic response times with Version A's specific degradation thresholds]*

### Severity 3 - Medium (P3)
**Criteria:**
- Minor service degradation affecting <25% of customers
- Non-critical feature outages
- Performance issues 150-200% of baseline
- Isolated customer-specific issues

**Initial Response Target:** 4 hours during business hours, next business day off-hours
**Resolution Target:** Within 1 business week
**Communication:** Customer notification if directly requested

### Severity 4 - Low (P4)
**Criteria:**
- Cosmetic issues or minor bugs
- Internal system issues not affecting customers
- Documentation or configuration issues

**Initial Response Target:** Next business day
**Resolution Target:** Best effort during normal development cycles
**Communication:** No customer notification required

## 2. On-Call Rotation Structure and Decision Authority

### Primary On-Call Structure
**US Team (8 engineers):**
- Monday-Thursday: 8 AM PST - 12 AM PST (16 hours)
- Friday-Sunday: 24-hour coverage
- 1-week rotation with 1-week advance notice

**EU Team (7 engineers):**
- Monday-Friday: 8 AM CET - 8 PM CET (12 hours)
- Weekends: Backup only
- 1-week rotation with 1-week advance notice

*[Keeps Version A's detailed coverage model but uses Version B's realistic advance notice period]*

### Coverage Model
- **US Business Hours (8 AM - 6 PM PST):** US Primary + EU Secondary
- **EU Business Hours (8 AM - 6 PM CET):** EU Primary + US Secondary
- **Overlap Hours (8 AM - 11 AM PST / 5 PM - 8 PM CET):** Both teams available
- **Off-Hours:** Single primary with secondary backup

### Incident Command Structure and Escalation

**Incident Commander (IC):** First responder becomes IC until handoff
- Authority to make technical decisions (restarts, traffic routing, rollbacks)
- Authority to declare severity and adjust as needed
- Authority to request up to 3 additional engineers for P1, 1 for P2

**Engineering Manager:** Automatically engaged for P1 incidents after 2 hours or P2 incidents after 4 hours
- Authority to override IC decisions
- Authority to engage additional teams or vendors
- Authority to approve database rollbacks or major changes

**VP Engineering:** Automatically engaged for P1 incidents after 4 hours
- Authority to make resource allocation decisions affecting other projects
- Authority to approve customer compensation discussions

**Escalation Triggers:**
- **30/60 minutes:** Primary on-call non-responsive → Secondary on-call automatically paged
- **2 hours:** P1 incident → Engineering Manager automatically engaged as co-IC
- **4 hours:** P1 incident → VP Engineering automatically engaged
- **Customer escalation:** Any severity → Appropriate management level engaged within 1 hour

*[Combines Version A's detailed escalation chain with Version B's clear decision-making authority and automatic escalation triggers]*

## 3. Cross-Timezone Incident Management

### Handoff Protocol
**Handoff required when:**
- IC explicitly requests timezone handoff due to expertise needs
- Incident extends beyond 8 hours and requires fresh perspective
- Primary timezone team reaches end of reasonable working hours (>12 hours on incident)

**Handoff Process:**
1. Written summary in incident channel (mandatory)
2. 15-minute verbal handoff call (scheduled, not immediate)
3. New IC acknowledges acceptance of handoff
4. Status page updated by outgoing team
5. Customer communications handed over explicitly

*[Uses Version B's realistic handoff triggers while keeping Version A's thorough handoff requirements]*

### Timezone-Specific Responsibilities
**Incident Owner:** IC authority remains with most qualified engineer regardless of timezone
**Communication Owner:** Based on customer timezone concentration
**Technical Lead:** Most qualified available engineer

### Follow-the-Sun Model for Major Incidents
For P1 incidents lasting >8 hours:
1. Maintain single Incident Commander with timezone handoff as needed
2. Formal handoff every 8 hours with 1-hour overlap for coordination
3. Single source of truth in incident management tool

*[Eliminates Version A's unrealistic "war room in both timezones" while maintaining coordination for extended incidents]*

## 4. Internal Communication Templates

### Initial Incident Alert (Slack/Teams)
```
🚨 INCIDENT DECLARED - P[X] 🚨
Incident ID: INC-YYYY-MMDD-XXX
Severity: P[X] - [Severity Name]
Start Time: [Timestamp UTC]
Incident Commander: @[name]
Status: INVESTIGATING

Brief Description: [One line description]
Customer Impact: [Specific impact and customer count if known]
Initial Response: [What's being done right now]

War Room: [Link to video call]
Incident Channel: #incident-[ID]
Status Page: [Updated/Pending]

Next Update: When status changes or significant progress made
```

*[Keeps Version A's comprehensive alert format but removes promise of timed updates regardless of progress]*

### Progress Update Template (Only When Meaningful Progress Occurs)
```
📊 INCIDENT UPDATE - P[X] - INC-YYYY-MMDD-XXX

Time: [Timestamp UTC]
Status: [INVESTIGATING/IDENTIFIED/MONITORING/RESOLVED]
Duration: [X hours Y minutes]

Progress Since Last Update:
- [Specific action taken]
- [Discovery made]
- [Solution attempted]

Current Actions:
- [What's happening now]
- [Who's doing what]

Customer Impact:
- [Current impact level]
- [Any changes since last update]

ETA: [If known, otherwise "Investigating"]
Next Update: When next significant development occurs
```

*[Uses Version A's detailed update format but adopts Version B's realistic update timing]*

## 5. Customer Communication Strategy

### Communication Timing
**P1 Incidents:**
- Initial notification: Within 2 hours of impact confirmation
- Updates: Only when meaningful progress or status changes occur
- Minimum update frequency: Every 4 hours if incident exceeds 8 hours

**P2 Incidents:**
- Initial notification: Within 4 hours if customer-facing
- Updates: Every 8 hours if incident exceeds 24 hours

*[Uses Version B's realistic communication timing while maintaining Version A's commitment to regular updates for extended incidents]*

### Customer Communication Templates

### Initial Customer Notification (P1/P2)
**Subject:** [Service Alert] Service Impact Detected - [Timestamp]

```
Dear [Customer Name],

We have identified a service issue affecting [specific service/functionality] that began at approximately [time] UTC.

CURRENT STATUS:
- Issue: [Brief, non-technical description]
- Services Affected: [Specific list if known]
- Customer Impact: [What customers are experiencing]

IMMEDIATE ACTIONS:
- Our engineering team is actively investigating
- We have identified [initial findings if any]
- [Any workarounds available]

We are treating this as a high priority issue and will provide updates when we have meaningful progress to report or every [4 hours for P1, 8 hours for P2] if the incident continues.

Our next update will be when we have significant progress or by [specific time] if the issue persists.

You can track real-time updates at: [status page URL]
For urgent questions, please contact: [emergency contact]

We apologize for the inconvenience and appreciate your patience.

Best regards,
[Name], Incident Response Team
```

*[Combines Version A's comprehensive initial notification with Version B's realistic update promises]*

### Progress Update Template
**Subject:** [Service Update] Progress Update - [Timestamp]

```
Dear [Customer Name],

UPDATE as of [time] UTC:

CURRENT STATUS: [INVESTIGATING/IDENTIFIED/IMPLEMENTING FIX]

PROGRESS:
- [What we've discovered]
- [Actions taken]
- [Current focus area]

CUSTOMER IMPACT:
- [Any changes to impact]
- [Workarounds if available]

ESTIMATED RESOLUTION:
[If known, otherwise: "We are working to resolve this as quickly as possible and will provide an ETA as soon as we have more information."]

NEXT UPDATE: [When next significant development occurs or specific time if incident continues]

Status page: [URL]
Emergency contact: [Details]

Thank you for your continued patience.

Best regards,
[Name], Incident Response Team
```

*[Uses Version A's comprehensive progress template with Version B's realistic update timing]*

### Resolution Notification
*[Uses Version A's comprehensive resolution template unchanged as it provides necessary closure information]*

## 6. Post-Mortem Process

### Post-Mortem Requirements
**P1 incidents:** Within 1 week of resolution
**P2 incidents:** Within 2 weeks if customer-impacting  
**P3 incidents:** Monthly review batch for recurring issues
**P4 incidents:** Quarterly review batch

*[Uses Version B's realistic timeframes while maintaining Version A's systematic approach]*

### Streamlined Post-Mortem Process (60-minute meeting)

**Required Participants:**
- Incident Commander
- Primary responders with specific input
- Engineering Manager
- Customer Success representative

**Optional Participants:**
- VP Engineering (for P1/P2)

*[Balances Version A's thorough participant list with Version B's realistic meeting constraints]*

**Agenda:**
1. **Timeline Review (15 minutes)**
   - Incident detection method
   - Response timeline
   - Key decision points

2. **Root Cause Analysis (20 minutes)**
   - Technical root cause
   - Process failures
   - Communication gaps

3. **Customer Impact Assessment (10 minutes)**
   - Affected customer count and segments
   - Business impact quantification

4. **Action Items Definition (15 minutes)**
   - Maximum 5 action items with clear owners and realistic deadlines
   - Priority ranking (P1 actions completed within 2 weeks)

*[Combines Version A's comprehensive agenda with Version B's realistic time constraints and action item limits]*

### Post-Mortem Document Template

```markdown
# Post-Mortem: [Incident Title]
**Incident ID:** INC-YYYY-MMDD-XXX
**Date:** [Date]
**Severity:** P[X]
**Duration:** [X hours Y minutes]
**Participants:** [List]

## Executive Summary
[2-3 sentence summary of what happened, impact, and resolution]

## Timeline (Key Events Only)
| Time (UTC) | Event | Action Taken |
|------------|-------|--------------|
| [Time] | [Event] | [Action] |

## Root Cause Analysis
### Technical Root Cause
[Detailed technical explanation]

### Contributing Factors
- [Factor 1]
- [Factor 2]

## Customer Impact
- **Customers Affected:** [Number and percentage]
- **Services Impacted:** [List]
- **Business Impact:** [Quantified where possible]

## What Went Well
- [Positive aspect 1]
- [Positive aspect 2]

## What Could Be Improved
- [Improvement area 1]
- [Improvement area 2]

## Action Items
| Action | Owner | Deadline | Priority |
|--------|-------|----------|----------|
| [Action] | [Person] | [Date] | [P1/P2/P3] |

## Lessons Learned
[Maximum 3 key takeaways]
```

*[Combines Version A's comprehensive structure with Version B's focus on key events and limited action items]*

## 7. Success Metrics and Process Refinement

### Success Metrics
- **Response Effectiveness:** 90% of P1 incidents have IC engaged within target times
- **Resolution Quality:** <20% of resolved incidents require follow-up fixes within 7 days
- **Communication Quality:** Customer satisfaction score >3.5/5.0 for P1/P2 incidents
- **Process Adherence:** 100% of P1/P2 incidents follow complete process
- **Learning Effectiveness:** 80% of post-mortem action items completed within committed timeframes

*[Uses Version B's realistic, outcome-focused metrics while maintaining Version A's process adherence measurement]*

### Monthly Process Review
- Review all P1/P2 incidents from previous month
- Identify recurring issues or process gaps
- Adjust severity criteria or response procedures based on actual experience
- Update communication templates based on customer feedback

*[Adopts Version B's built-in refinement process]*

## 8. Implementation Plan

### Phase 1 (Weeks 1-4): Foundation
- Weeks 1-2: Set up incident management tooling and integrations
- Weeks 3-4: Train all engineers on new process, conduct tabletop exercises
- Focus: Ensure everyone understands decision-making authority and escalation

### Phase 2 (Weeks 5-8): Process Integration and Refinement
- Weeks 5-6: Run new process with existing incidents, gather feedback
- Weeks 7-8: Refine communication templates and cross-timezone handoff procedures
- Focus: Adjust process based on actual incident patterns

### Phase 3 (Weeks 9-12): Optimization
- Weeks 9-10: Implement post-mortem tracking system
- Weeks 11-12: Establish metrics collection and reporting
- Focus: Optimize for long-term sustainability

*[Uses Version B's realistic timeline with built-in learning phases while maintaining Version A's systematic approach]*

### Tools and Technology Requirements
- **Incident Management:** PagerDuty or OpsGenie ($150/month)
- **Communication:** Slack/Teams integration
- **Status Page:** StatusPage.io or similar ($79/month)
- **Post-Mortem:** Confluence or Notion templates
- **Monitoring:** Enhanced alerting rules in existing monitoring tools

### Resource Allocation Guidelines
**P1 Incidents:** IC can request up to 3 additional engineers be pulled from other work
**P2 Incidents:** IC can request up to 1 additional engineer during business hours
**Sprint Impact:** Engineering Manager must communicate delivery impacts to Product/Customer Success within 24 hours

*[Incorporates Version B's explicit resource allocation guidance]*

This incident response process provides a comprehensive yet realistic framework that addresses the specific challenges of distributed teams, enterprise customer expectations, and the need for rapid, transparent communication while maintaining sustainable engineering practices and continuous process improvement.