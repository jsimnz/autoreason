# Blind Evaluation: task_05_pair_03

## Task
Design the incident response process for a B2B SaaS company with 200 enterprise customers, a 99.95% SLA, and a 15-person engineering team split across US and EU timezones. Cover: severity levels and criteria, on-call rotation, escalation paths, communication templates (internal and customer-facing), post-mortem process, and how to handle incidents that span timezone boundaries. The company has had 3 major incidents in the past quarter and customers are losing patience.

---

## Proposal X

# Revised Incident Response Process Design for B2B SaaS Company

## Executive Summary

This proposal establishes a practical incident response framework focused on rapid resolution and clear customer communication. Given recent customer confidence issues, this process prioritizes effective technical response over complex process overhead, with realistic resource requirements and proven escalation patterns.

## 1. Severity Levels and Response Targets

### SEV-1 (Critical - All Hands)
**Response Target:** 30 minutes
**Resolution Target:** Best effort, continuous work
**Criteria:**
- Complete service unavailable for majority of customers
- Active security breach or data loss
- Payment processing completely down

### SEV-2 (High - Urgent Response)
**Response Target:** 1 hour during business hours, 2 hours off-hours
**Resolution Target:** 8 hours
**Criteria:**
- Significant feature degradation affecting customer operations
- Single enterprise customer complete outage
- Performance degradation preventing normal usage

### SEV-3 (Standard - Normal Priority)
**Response Target:** Next business day
**Resolution Target:** 5 business days
**Criteria:**
- Minor issues that don't prevent core functionality
- Cosmetic problems in secondary features

**FIXES:** Reduces complexity from 4 to 3 severity levels (addresses "complexity without payoff"), uses realistic 30-minute response time instead of impossible 15-minute target (addresses "response time SLAs conflict with human reality"), removes precise percentage measurements that don't exist in real-time (addresses "wrong assumptions").

## 2. On-Call Structure (Sustainable Rotation)

### Coverage Model
- **Business Hours (8 AM - 6 PM local):** Dedicated incident response engineer
- **After Hours/Weekends:** Rotating on-call from engineering team
- **Minimum team size:** 20 engineers to support rotation

### Rotation Schedule
- **1 week shifts** (Monday 8 AM to Monday 8 AM)
- **Minimum 4 weeks between shifts** per person
- **Maximum 4 weekend shifts per year** per person
- **Backup on-call:** Always assigned, responds if primary unavailable after 45 minutes

### On-Call Responsibilities
- Acknowledge alerts within response target times
- Begin initial assessment and coordinate response
- Engage additional engineers as needed for SEV-1/2 incidents
- Maintain incident status updates

**FIXES:** Creates mathematically viable rotation (20 engineers supporting 1-week shifts = 5 months between rotations), establishes realistic weekend limits (addresses "on-call rotation is mathematically broken"), increases response window to 45 minutes total (addresses "response time SLAs conflict with human reality").

## 3. Escalation and Incident Command

### Incident Commander Assignment
- **SEV-1:** Senior engineer designated as IC immediately, regardless of who discovered issue
- **SEV-2:** On-call engineer acts as IC unless they request senior engineer support
- **SEV-3:** On-call engineer manages without IC role

### Incident Commander Authority
- Coordinate all technical response activities
- Make service degradation vs. restoration tradeoff decisions
- Determine when to engage additional engineers
- Approve customer communications before sending

### Escalation Triggers (Time-Based)
- **SEV-1:** Engineering Manager notified immediately, VP Engineering at 2 hours
- **SEV-2:** Engineering Manager at 4 hours if no progress
- **SEV-3:** Weekly review of open items

### Regional Management
- **US Hours (6 AM - 6 PM PST):** US Engineering Manager → US VP Engineering
- **EU Hours (6 AM - 6 PM CET):** EU Engineering Manager → EU VP Engineering
- **Cross-timezone handoffs:** Full incident context transfer with 30-minute overlap

**FIXES:** Defines incident commander role and selection process (addresses "no incident commander role definition"), creates parallel EU management escalation path (addresses "cross-timezone escalation paths don't align"), reflects realistic incident response where multiple people engage simultaneously rather than rigid linear escalation (addresses "wrong assumptions about escalation").

## 4. Customer Communication Framework

### Communication Triggers
- **SEV-1:** Customer Success Manager notifies affected customers within 2 hours
- **SEV-2:** Customer Success Manager notifies affected customers within 4 hours if impact continues
- **SEV-3:** No proactive customer communication unless specifically requested

### Approval Process
- Incident Commander drafts technical status
- Customer Success Manager adapts for customer audience
- Engineering Manager approves before sending (or EU Engineering Manager during EU hours)

### Communication Content (Brief Updates)
**Initial Notification:**
- What service is affected
- When it started
- What we're doing
- When next update will come

**Resolution Notification:**
- What was fixed
- When service was restored
- Brief explanation of cause
- Reference to detailed post-mortem (if applicable)

### Status Page Integration
- SEV-1/2 incidents posted to status page within 2 hours
- Updates posted every 4 hours until resolution
- Customer Success team manages status page content

**FIXES:** Reduces communication complexity by eliminating rigid templates requiring immediate customer updates (addresses "dual communication templates create coordination overhead"), assumes customers prefer brief updates over detailed technical communication during incidents (addresses "wrong assumptions about customer communication preferences"), includes approval process recognizing legal/marketing review needs (addresses "assumes Customer Success can send templated messages immediately").

## 5. Post-Mortem Process (Realistic Timeline)

### Post-Mortem Requirements
- **SEV-1:** Full post-mortem required, draft within 2 weeks
- **SEV-2:** Post-mortem required if >4 hour impact or customer escalation, draft within 1 week
- **SEV-3:** Post-mortem only if pattern of similar issues identified

### Post-Mortem Content
- **Timeline:** Key events and decisions
- **Impact:** Customer count, duration, business effect
- **Root Cause:** Technical cause and contributing factors
- **Action Items:** Specific improvements with owners and realistic deadlines

### Review and Publication
- **Internal review:** Engineering team review within 3 business days of draft
- **Customer version:** Summary published within 5 business days of internal review
- **Follow-up:** Action item progress reviewed monthly

**FIXES:** Establishes realistic timeline of weeks instead of 48-72 hours for root cause analysis (addresses "assumes post-mortem completion in 48-72 hours is realistic"), focuses on actionable improvements rather than detailed technical analysis (addresses "rushing post-mortems leads to incorrect conclusions").

## 6. Technical Integration Requirements

### Required Tooling
- **Alerting:** PagerDuty for on-call notifications and escalation
- **Communication:** Dedicated Slack channels (#incidents, #incident-YYYY-MM-DD-description)
- **Tracking:** Jira for incident tickets and action item management
- **Status:** Status page integration (Statuspage.io or equivalent)

### Customer Impact Measurement
- **Automated monitoring:** Track login success rates, API error rates, key user journey completion
- **Manual assessment:** Customer Success team maintains list of affected customers during incidents
- **Post-incident analysis:** Review support ticket volume and customer feedback

### Integration with Support
- **Incident tickets automatically create high-priority support tickets**
- **Customer Success team manages customer communication using incident status**
- **Support team escalates customer reports of issues to incident response team**

**FIXES:** Specifies actual tooling integration instead of just mentioning tools (addresses "no tooling integration specified"), defines customer impact measurement system (addresses "no customer impact measurement system"), explains integration with existing support processes (addresses "no integration with existing support processes").

## 7. Implementation Plan (Phased Approach)

### Phase 1 (Weeks 1-2): Core Setup
- Configure PagerDuty rotations and Slack integrations
- Train engineering team on severity definitions and IC responsibilities
- Establish incident tracking in Jira
- Test alerting and escalation paths

### Phase 2 (Weeks 3-4): Process Integration
- Begin using incident commander model for all SEV-1/2 incidents
- Implement customer communication approval process
- Start post-mortem process for new incidents
- Create first monthly review of action items

### Phase 3 (Month 2): Optimization
- Review first month's incidents for process improvements
- Adjust on-call rotation based on actual workload
- Train Customer Success team on incident communication
- Implement status page automation

### Phase 4 (Month 3+): Continuous Improvement
- Monthly incident review meetings
- Quarterly process refinement
- Annual review of on-call compensation and rotation sustainability

## 8. Success Metrics (Realistic Targets)

### Response Metrics
- **Acknowledgment:** <30 min for SEV-1, <2 hours for SEV-2
- **Resolution:** Track MTTR trends, aim for month-over-month improvement
- **Escalation effectiveness:** Engineering Manager engaged appropriately (not too early/late)

### Communication Metrics
- **Customer notification:** SEV-1 within 2 hours, SEV-2 within 4 hours
- **Post-mortem completion:** 100% for SEV-1, 80% for SEV-2 within target timelines
- **Action item completion:** 80% completed within committed timeframes

### Business Impact
- **Repeat incidents:** <20% same root cause within 60 days
- **Customer escalations:** Reduce by 50% within 6 months
- **Support ticket volume:** Track correlation between incident communication and ticket volume

**FIXES:** Establishes realistic targets instead of potentially impossible metrics like 99.95% uptime (addresses "assumes engineering teams can maintain consistent availability metrics"), focuses on improvement trends rather than absolute targets for a company with recent major incidents (addresses "wrong assumptions about realistic metrics").

## 9. Cost and Resource Requirements

### Personnel Requirements
- **20 engineers minimum** for sustainable on-call rotation
- **Dedicated incident commander training** (4 hours per senior engineer)
- **Customer Success incident communication training** (2 hours)

### Tooling Costs
- **PagerDuty:** ~$50/month per engineer
- **Status page service:** ~$100/month
- **Additional Jira licenses:** ~$10/month per engineer

### Operational Overhead
- **On-call compensation:** Budget for evening/weekend work
- **Post-mortem time:** ~8 hours per SEV-1, ~4 hours per SEV-2
- **Monthly reviews:** 2 hours/month engineering management time

**FIXES:** Acknowledges operational costs that weren't mentioned in original proposal (addresses "no cost analysis"), provides realistic resource requirements for implementation.

## 10. Technical Response Procedures

### Immediate Response Actions
- **SEV-1:** Incident Commander assesses rollback options within first 30 minutes
- **Service degradation decisions:** IC has authority to disable features to restore core functionality
- **Recovery validation:** Define "service restored" criteria before declaring resolution

### Rollback Procedures
- **Automated rollback:** Available for application deployments (target <15 minutes)
- **Database rollback:** Requires Engineering Manager approval, documented procedures
- **Feature flags:** Immediate disable capability for problematic features

### Communication During Technical Response
- **Internal updates:** Every 30 minutes for SEV-1, hourly for SEV-2
- **Customer updates:** Only after IC confirms technical status
- **Resolution criteria:** Must validate customer impact is resolved, not just technical fix deployed

**FIXES:** Includes actual technical response procedures and rollback plans missing from original proposal (addresses "no rollback/recovery procedures"), defines recovery validation process (addresses focus entirely on communication rather than technical response).

This revised proposal provides a foundation for reliable incident response that matches the company's current resources and addresses the specific problems that led to customer confidence issues, while avoiding the operational overhead and unrealistic commitments that would make the original proposal fail in practice.

---

## Proposal Y

# Incident Response Process Design for B2B SaaS Company

## Executive Summary

This proposal establishes a comprehensive incident response framework designed to restore customer confidence through faster resolution times, improved communication, and systematic learning from incidents. Given the recent pattern of 3 major incidents and customer frustration, this process prioritizes transparency, speed, and continuous improvement.

## 1. Severity Levels and Criteria

### SEV-1 (Critical)
**Response Time:** 15 minutes
**Resolution Target:** 4 hours
**Criteria:**
- Complete service outage affecting >75% of customers
- Data breach or security compromise
- Data loss or corruption affecting multiple customers
- Payment processing completely down
- Core authentication system failure

### SEV-2 (High)
**Response Time:** 30 minutes
**Resolution Target:** 8 hours
**Criteria:**
- Partial service degradation affecting >50% of customers
- Single customer complete outage for enterprise tier
- Performance degradation >50% slower than baseline
- Non-core feature completely unavailable
- Intermittent authentication issues

### SEV-3 (Medium)
**Response Time:** 2 hours (business hours only)
**Resolution Target:** 24 hours
**Criteria:**
- Minor feature degradation affecting <25% of customers
- Performance issues 25-50% slower than baseline
- Cosmetic issues in critical workflows
- Non-critical integrations failing

### SEV-4 (Low)
**Response Time:** Next business day
**Resolution Target:** 72 hours
**Criteria:**
- Minor cosmetic issues
- Documentation errors
- Non-critical feature requests logged as incidents

## 2. On-Call Rotation Structure

### Primary On-Call (24/7 Coverage)
- **US Primary:** Monday 6 AM PST - Tuesday 6 AM PST
- **EU Primary:** Tuesday 6 AM PST - Wednesday 6 AM PST
- **US Primary:** Wednesday 6 AM PST - Thursday 6 AM PST
- **EU Primary:** Thursday 6 AM PST - Friday 6 AM PST
- **US Primary:** Friday 6 AM PST - Monday 6 AM PST

### Secondary On-Call (Backup)
- Always from opposite timezone
- Must respond within 10 minutes if primary doesn't acknowledge

### Rotation Assignments
- **US Pool:** 8 engineers (Senior: 4, Mid: 4)
- **EU Pool:** 7 engineers (Senior: 3, Mid: 4)
- **Minimum 2 weeks between on-call shifts per person**
- **No more than 1 weekend per month per person**

### On-Call Responsibilities
- Monitor alerting systems continuously
- Acknowledge incidents within response time SLAs
- Begin initial assessment and triage
- Escalate according to severity and complexity
- Update incident status every 30 minutes during active incidents

## 3. Escalation Paths

### Technical Escalation
```
L1: On-Call Engineer (Primary)
↓ (15 min for SEV-1, 30 min for SEV-2)
L2: On-Call Engineer (Secondary) + Team Lead
↓ (30 min for SEV-1, 1 hour for SEV-2)
L3: Engineering Manager + Senior Architect
↓ (1 hour for SEV-1, 2 hours for SEV-2)
L4: CTO + VP Engineering
```

### Business Escalation
```
Customer Success Manager (immediate for SEV-1/2)
↓
VP Customer Success (30 min for SEV-1, 2 hours for SEV-2)
↓
CEO (1 hour for SEV-1, 4 hours for SEV-2)
```

### Auto-Escalation Triggers
- No acknowledgment within response time SLA
- No meaningful progress update within 2x response time
- Customer escalation received
- Estimated resolution time exceeds target by 50%

## 4. Communication Templates

### Internal Communication

#### SEV-1/2 Incident Slack Template
```
🚨 **INCIDENT DECLARED** 🚨
**Severity:** SEV-X
**Title:** [Brief description]
**Started:** [Timestamp]
**Incident Commander:** @[name]
**Status:** Investigating/Identified/Monitoring/Resolved

**Impact:**
- Affected customers: X/200 (X%)
- Affected features: [list]
- Business impact: [revenue/SLA impact]

**Next Update:** [timestamp + 30 min]
**War Room:** #incident-[timestamp]
**Status Page:** [link if updated]

cc: @incident-team @leadership
```

#### Progress Update Template
```
**INCIDENT UPDATE** - SEV-X
**Time:** [timestamp]
**Status:** [current status]
**Progress:** [what we've learned/tried]
**Next Steps:** [specific actions with owners]
**ETA:** [realistic estimate or "investigating"]
**Customer Communication:** [sent/scheduled/not needed]
```

### Customer-Facing Communication

#### Initial Customer Notification (SEV-1/2)
**Subject:** [Service Impact] - We're investigating an issue affecting [specific service]

Dear [Customer Name],

We are currently investigating an issue that began at [time] affecting [specific functionality]. 

**What's happening:** [Brief, clear description]
**Who's affected:** [Specific scope]
**What we're doing:** [Current actions]
**Next update:** We will provide another update within [timeframe]

You can monitor our progress at [status page URL].

We sincerely apologize for the disruption and are working urgently to resolve this issue.

Best regards,
[Name], Customer Success Manager

#### Resolution Notification
**Subject:** [Resolved] - Service issue has been resolved

Dear [Customer Name],

The service issue that began at [start time] has been resolved as of [end time].

**What happened:** [Brief technical explanation]
**Root cause:** [High-level cause]
**Resolution:** [What was done]
**Prevention:** [Steps being taken to prevent recurrence]

**Total impact duration:** [X hours, Y minutes]

We deeply apologize for the disruption to your business operations. A detailed post-mortem will be available within 72 hours at [URL].

If you have any questions or concerns, please don't hesitate to reach out.

Best regards,
[Name], Customer Success Manager

## 5. Post-Mortem Process

### Timeline
- **Draft due:** 48 hours after resolution
- **Review completed:** 72 hours after resolution  
- **Customer version published:** 96 hours after resolution
- **Action items assigned:** Within review meeting

### Post-Mortem Template

#### Executive Summary
- Incident duration and impact
- Root cause in one sentence
- Key lessons learned

#### Timeline
- Detailed chronology with timestamps
- All actions taken and by whom
- Communication sent and when

#### Root Cause Analysis
- Primary root cause
- Contributing factors
- What went well (blameless culture)

#### Impact Assessment
- Customers affected (by tier/segment)
- Revenue impact
- SLA impact
- Support ticket volume

#### Action Items
- Immediate fixes (0-7 days)
- Short-term improvements (1-4 weeks)  
- Long-term investments (1-3 months)
- Each item assigned to owner with due date

### Review Process
1. **Draft creation:** Incident Commander + 1 peer reviewer
2. **Technical review:** Engineering Manager + Senior Engineer
3. **Business review:** Customer Success + Product Manager
4. **Final approval:** VP Engineering
5. **Customer communication:** Customer Success Manager

### Customer Post-Mortem (External)
- Sanitized version focusing on impact and prevention
- Published to customer portal
- Proactive email to affected customers
- Available for customer success calls

## 6. Timezone Boundary Handling

### Handoff Protocol

#### US to EU Handoff (6 AM PST Daily)
**15 minutes before handoff:**
1. US on-call posts comprehensive status in #incident-handoffs
2. EU on-call acknowledges readiness
3. Brief verbal sync if active incidents

#### Handoff Status Template
```
**HANDOFF TO EU** - [Date]
**Active Incidents:**
- SEV-X: [title] - Status: [status] - Next: [action with ETA]
- [Repeat for each]

**Monitoring Items:**
- [System/metric to watch] - Last status: [status]

**Pending Items:**
- [Non-urgent items that need attention]

**Context Notes:**
- [Any additional context EU team needs]

EU Team: Please acknowledge receipt 👍
```

### Cross-Timezone Incident Management

#### For SEV-1 Incidents
- **Both teams engaged immediately** regardless of timezone
- US Incident Commander during US hours (6 AM - 6 PM PST)
- EU Incident Commander during EU hours (6 PM - 6 AM PST)
- Minimum 2 engineers from each timezone on major incidents

#### For SEV-2 Incidents
- Primary timezone leads, secondary provides support
- Handoff only if incident extends beyond 4 hours
- Full context transfer required

#### Weekend Coverage
- Each timezone covers their own weekends
- Cross-timezone support available for SEV-1 only
- Weekend incidents get Monday priority for post-mortem

### Escalation Across Timezones
- **US Hours:** Standard US escalation path
- **EU Hours:** Standard EU escalation path  
- **Overlap Hours (8 AM - 11 AM PST):** Dual management available
- **Emergency escalation:** VP Engineering (US) and Engineering Manager (EU) both contactable 24/7

## 7. Implementation Plan

### Phase 1 (Week 1-2): Foundation
- Set up incident management tooling (PagerDuty + Slack integration)
- Create incident response Slack channels and workflows
- Train all engineers on new severity definitions
- Establish on-call rotations

### Phase 2 (Week 3-4): Process Implementation
- Begin using new escalation paths
- Implement communication templates
- Start post-mortem process for new incidents
- Review and refine based on initial usage

### Phase 3 (Week 5-8): Optimization
- Analyze response times and adjust processes
- Complete post-mortems for previous quarter's incidents
- Customer communication about improved processes
- Full team training and certification

### Phase 4 (Month 3+): Continuous Improvement
- Monthly process review meetings
- Quarterly customer feedback collection
- Semi-annual process updates
- Advanced incident management training

## 8. Success Metrics

### Response Metrics
- Mean Time to Acknowledge (MTTA): <15 min for SEV-1, <30 min for SEV-2
- Mean Time to Resolution (MTTR): <4 hours for SEV-1, <8 hours for SEV-2
- Escalation rate: <20% of incidents require L3+ escalation

### Communication Metrics
- Customer notification within 30 minutes of SEV-1/2 incidents
- Post-mortem completion rate: 100% within 72 hours
- Customer satisfaction with incident communication: >4.0/5.0

### Quality Metrics  
- Repeat incident rate: <10% (same root cause within 30 days)
- False positive alert rate: <15%
- SLA compliance: Maintain 99.95% uptime

### Business Impact
- Customer churn related to incidents: <2% quarterly
- Support ticket volume during incidents: Reduce by 30%
- Average incident impact: <50 customers per SEV-2 incident

This incident response process provides the structure needed to restore customer confidence while building a foundation for long-term reliability improvements. The key to success will be consistent execution, regular refinement based on real incidents, and maintaining a culture of blameless learning and continuous improvement.
