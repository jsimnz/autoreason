# Practical Incident Response Process for B2B SaaS Company

## Executive Summary

This incident response framework balances reliability needs with operational sustainability for a 15-person distributed engineering team serving 200 enterprise customers. The process prioritizes effective problem-solving over rigid timelines while maintaining clear communication with customers.

## 1. Severity Levels and Response Targets

### Severity 1 (Critical)
**Response Target:** 30 minutes during business hours, 1 hour outside business hours | **Customer Communication:** Within 1 hour of confirmation

**Criteria:**
- Complete service outage preventing customer work
- Data loss or active security breach
- Payment processing failure affecting multiple customers

**Response Logic:** *Fixes "Impossible Response Time Commitments" - allows time for proper assessment before response*

### Severity 2 (High)  
**Response Target:** 1 hour during business hours, 2 hours outside business hours | **Customer Communication:** Within 2 hours

**Criteria:**
- Significant performance degradation (>75% slower than baseline)
- Core feature unavailable for >25% of customers
- Single enterprise customer complete outage

**Response Logic:** *Addresses "Communication Framework Problems" - realistic timing allows for proper problem understanding*

### Severity 3 (Medium)
**Response Target:** 4 hours during business hours, next business day outside hours | **Customer Communication:** As needed

**Criteria:**
- Minor feature degradation with workarounds available
- Non-critical integrations failing
- Performance issues affecting <25% of customers

### Severity 4 (Low)
**Response Target:** Next business day | **Customer Communication:** Via regular support channels

**Criteria:**
- Cosmetic issues, documentation problems
- Enhancement requests filed as incidents

**Severity Classification:** All incidents start as Severity 2 until assessed. *Fixes "Technical Implementation Gaps" - removes subjective initial classification*

## 2. Sustainable On-Call Structure

### Business Hours Coverage (9 AM - 6 PM local time)
- **US Team:** Covers US business hours Monday-Friday
- **EU Team:** Covers EU business hours Monday-Friday
- **Shared Coverage:** 2-hour overlap period (1 PM - 3 PM UTC) for handoffs

### After-Hours Coverage
- **Rotating Weekly:** One engineer from each region takes after-hours alerts
- **Maximum Shift:** 12 hours (6 PM - 6 AM local time) *Fixes "Broken On-Call Mathematics" - complies with labor laws*
- **Compensation:** Engineers receive time-off-in-lieu for after-hours responses

### Rotation Schedule
- **Frequency:** Each engineer on-call approximately every 8 weeks
- **Backup System:** Two engineers per region designated as secondary contacts
- **Leave Coverage:** Planned coverage for vacations, sick days, departures *Addresses "no coverage for vacations, sick days" problem*

### On-Call Responsibilities
- Acknowledge alerts within response targets
- Perform initial assessment and document findings
- Execute documented runbooks where available
- Escalate when issue exceeds individual capacity

## 3. Practical Escalation Framework

### Level 1: On-Call Engineer
**Duration:** First hour of response
**Escalate When:**
- Issue requires knowledge outside engineer's expertise
- Multiple system components involved
- Standard runbooks don't resolve the issue

### Level 2: Engineering Lead (Available during business hours)
**Escalate When:**
- Cross-team coordination needed
- Decision required on service degradation vs. downtime tradeoffs
- Customer is asking for executive involvement

### Level 3: Engineering Manager
**Escalate When:**
- Issue duration exceeds 4 hours
- Multiple customers reporting escalations
- Potential need for customer credits or SLA exceptions

*Fixes "Unrealistic Escalation Chain" - removes unrealistic executive availability assumptions and focuses on business-hours escalation*

### Executive Notification (Not Escalation)
Engineering Manager notifies VP Engineering and CEO via email/Slack for:
- Incidents lasting >6 hours
- Incidents affecting >50% of customers
- Customer contract implications

*Addresses "executives always available" problem - changes from escalation to notification*

## 4. Streamlined Communication

### Internal Communication

#### Incident Declaration (Slack #incidents)
```
🚨 SEV [X] INCIDENT
Impact: [One sentence describing customer experience]
Owner: [Engineer name]
Status: [Investigating/Fixing/Monitoring]
Customer Comms: [Sent/Scheduled for X time/Not needed]
```

#### Updates (Every 2 hours for Sev 1/2, daily for Sev 3/4)
```
📊 UPDATE - SEV [X]
Progress: [What we learned/tried]
Next: [Immediate next action]
Customer Update: [When next communication goes out]
```

*Fixes "Template Overload" - simplified templates focus on essential information*

### Customer Communication

#### Notification Approach
- **Sev 1:** Immediate status page update + targeted emails to affected customers within 1 hour
- **Sev 2:** Status page update + email to affected customers within 2 hours  
- **Sev 3/4:** Status page update, email only if customers report issues

#### Update Frequency
- **Sev 1:** Every 2 hours until resolved *Fixes "overwhelm customers" - reduces from 30-minute updates*
- **Sev 2:** Every 4 hours or at major milestones
- **Timing:** Updates sent during customer business hours when possible *Addresses "3 AM updates" problem*

#### Communication Content
**Initial Notification:**
"We're experiencing an issue affecting [specific functionality]. Our team is actively working on a resolution. We'll update you in [timeframe] with our progress."

**Progress Updates:**
"Update on [issue]: We've [specific progress made] and expect resolution [timeframe/investigating]. Next update in [timeframe]."

**Resolution:**
"Issue resolved. [Brief explanation of what happened and what we did]. We're monitoring to ensure stability."

*Fixes "rigid templates" problem - provides flexible framework instead of rigid scripts*

## 5. Focused Post-Mortem Process

### Post-Mortem Triggers
- All Severity 1 incidents
- Severity 2 incidents lasting >4 hours
- Any incident causing customer contract discussions
- Incidents revealing new failure modes

*Fixes "overwhelming documentation burden" - reduces trigger criteria*

### Timeline
- **1 week post-resolution:** Engineering lead assigns owner and scope
- **2 weeks post-resolution:** Draft completed and reviewed
- **3 weeks post-resolution:** Final version and action plan

*Addresses "unrealistic timeline demands" - provides reasonable timeframes*

### Simplified Post-Mortem Format

**What Happened:** Timeline of key events and decisions

**Why It Happened:** Root cause analysis focusing on system/process factors

**What We're Doing About It:** 3-5 specific action items with owners and due dates

**What Went Well:** Positive aspects to reinforce

*Fixes "blameless culture contradictions" - removes rigid procedures that create blame pressure*

## 6. Timezone Coordination

### Handoff Philosophy
**Preserve Context Over Perfect Handoffs** - better to have one engineer see an incident through than lose context in handoff

### Handoff Rules
- **Sev 1:** Original engineer stays until resolution or natural break (not forced timezone boundary)
- **Sev 2:** Handoff only if incoming engineer can take full ownership
- **Sev 3/4:** Standard timezone handoff with status update

*Fixes "Follow-the-Sun Model Conflicts" - removes contradictory handoff requirements*

### Handoff Documentation
```
INCIDENT HANDOFF
What's broken: [Customer impact description]
What we've tried: [Actions taken]
Current theory: [Working hypothesis]
Next steps: [Specific actions for incoming engineer]
Key info: [Relevant context/contacts]
```

*Addresses "15-minute handoff impossibility" - focuses on essential information transfer*

### Cross-Timezone Support
- **Slack #incidents:** Primary coordination channel with timezone context
- **Shared incident log:** Google Doc with real-time updates
- **Alert escalation:** Automatic escalation to secondary region after 2 hours during off-hours

## 7. Implementation Approach

### Phase 1 (Month 1): Foundation
- Set up sustainable on-call rotation with proper coverage
- Deploy incident tracking system (linear/simple ticketing)
- Create basic runbooks for common issues
- Train team on severity classification and escalation

*Fixes "operational overhead explosion" - focuses on essential tools first*

### Phase 2 (Month 2): Process Refinement  
- Implement customer communication workflows
- Establish post-mortem process with first few incidents
- Create timezone handoff procedures
- Begin measuring response times and customer satisfaction

### Phase 3 (Month 3): Optimization
- Refine severity criteria based on actual incident patterns
- Optimize alert tuning to reduce false positives
- Establish incident metrics dashboard
- Plan quarterly process review

*Addresses "assumes engineering team can absorb overhead" - phases implementation to manage impact*

### Success Metrics
- **Response Time:** Percentage of incidents acknowledged within targets
- **Customer Impact:** Duration of customer-affecting issues
- **Engineer Sustainability:** On-call engineer feedback and turnover
- **Process Effectiveness:** Time from incident start to customer communication

*Fixes "measurement and metrics gaps" - focuses on outcomes rather than just speed*

## 8. Tool Requirements

### Essential Tools
- **Incident Tracking:** Linear or similar simple system
- **Alerting:** PagerDuty with smart escalation rules
- **Communication:** Slack integration + email templates
- **Documentation:** Google Docs for incident logs

### Tool Integration Philosophy
Keep tools simple and have manual fallbacks for tool failures during incidents.

*Addresses "tool integration assumptions" - acknowledges tool failure scenarios*

This framework provides sustainable incident response that balances customer needs with team sustainability, focusing on effective problem-solving rather than unrealistic process compliance.