# Revised Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a pragmatic notification system capable of handling 10M monthly active users with a team of 4 backend engineers over 6 months. The design prioritizes simplicity, operational feasibility, and rapid delivery while leveraging managed services to minimize operational overhead.

## System Architecture Overview

### Core Components
1. **Notification API Service** - REST API for notification creation
2. **Background Workers** - Async processing with Redis queues
3. **Channel Services** - Dedicated services per delivery channel
4. **User Service Integration** - Preference management in existing user database
5. **Monitoring & Analytics** - Delivery tracking and metrics

**FIXES**: Eliminates Kafka over-engineering, simplifies WebSocket complexity, removes Redis as primary storage

## 1. Delivery Channels Strategy

### Channel Selection & Simplified Implementation

**Push Notifications (Primary Channel)**
- **Implementation**: Firebase Admin SDK for both iOS and Android
- **Rationale**: Single API for both platforms, Google-managed scaling
- **Reality Check**: FCM rate limit is 600K messages/minute - our peak 2,000/second = 120K/minute (within limits)
- **Device Token Management**: 
  - Store tokens in PostgreSQL with user_id mapping
  - Background job to validate tokens daily, remove invalid ones
  - Handle token refresh via mobile app callback

**FIXES**: Addresses FCM rate limits, adds missing token management, removes "concurrent" push misconception

**Email (Batch Channel)**
- **Implementation**: SendGrid paid plan (100K emails/month for $19.95)
- **Setup Requirements**: 
  - Domain authentication with SPF/DKIM records
  - Dedicated IP warming over 2-week period
  - Unsubscribe handling and bounce processing
- **Capacity**: 100K emails/month, digest-only approach
- **Templates**: SendGrid dynamic templates with basic personalization

**FIXES**: Corrects SendGrid free tier misconception, adds deliverability requirements, realistic volume limits

**In-App Notifications (Polling-Based)**
- **Implementation**: REST API polling every 30 seconds when app is active
- **Storage**: PostgreSQL table with user_id index
- **Mobile Strategy**: iOS/Android background refresh, not persistent connections
- **Capacity**: Standard database queries, no special infrastructure needed

**FIXES**: Eliminates unrealistic WebSocket scaling, uses mobile-appropriate polling pattern

**SMS (Severely Limited)**
- **Implementation**: Twilio API
- **Usage**: Only password resets and account security (estimated 1% of users/month)
- **Budget**: $500/month (66K messages at $0.0075 each)
- **Geographic Scope**: US/Canada only initially (lower costs)

**FIXES**: Realistic SMS budget and use cases, eliminates international cost issues

### Channel Priority Matrix
```
Critical (Security): SMS → Push → Email
High (Social): Push → In-App
Medium (Engagement): Push OR Email (user preference)
Low (Marketing): Email only
```

## 2. Simplified Priority and Processing

### Priority Classification

**Critical (P0)** - Security only
- Password resets, suspicious login attempts
- Immediate processing, no batching
- SMS + Push + Email
- Volume: <1,000/day

**High (P1)** - Real-time social
- Direct messages, mentions, friend requests
- Process within 1 minute
- Push + In-App
- Volume: ~50,000/day

**Medium (P2)** - Standard engagement
- Likes, comments, follows
- Process within 15 minutes, batch by user
- Push OR Email (user setting)
- Volume: ~8,000,000/day

**Low (P3)** - Marketing/summaries
- Weekly digests, recommendations
- Daily batch processing
- Email only
- Volume: ~100,000/week

**FIXES**: Eliminates complex micro-batching, removes conflicting priority/batching logic

### Processing Strategy

**Redis Queue Implementation**:
```python
# Simple priority queues
QUEUE_CRITICAL = "notifications:critical"
QUEUE_HIGH = "notifications:high" 
QUEUE_MEDIUM = "notifications:medium"
QUEUE_LOW = "notifications:low"

# Worker processes queues in priority order
def process_notifications():
    while True:
        # Process critical first, then high, etc.
        notification = redis.brpop([QUEUE_CRITICAL, QUEUE_HIGH, QUEUE_MEDIUM, QUEUE_LOW], timeout=5)
        if notification:
            send_notification(notification)
```

**Batching Only for Medium/Low Priority**:
- Batch by user_id to prevent spam
- Maximum 5 notifications per user per hour for medium priority
- Daily digest for low priority

**FIXES**: Removes complex batching logic, eliminates micro-batching problems

## 3. User Preference Management

### Simplified Preference Schema
```sql
-- Add to existing users table
ALTER TABLE users ADD COLUMN notification_preferences JSONB DEFAULT '{
  "push_enabled": true,
  "email_enabled": true,
  "sms_enabled": false,
  "quiet_hours_start": 22,
  "quiet_hours_end": 8,
  "timezone": "UTC",
  "types": {
    "direct_messages": ["push"],
    "mentions": ["push"],
    "likes": ["push"],
    "follows": [],
    "marketing": []
  }
}';

-- Index for performance
CREATE INDEX idx_users_push_enabled ON users USING GIN ((notification_preferences->'push_enabled'));
```

**FIXES**: Uses existing user table, eliminates complex JSON querying, adds proper indexing

### Preference Engine Features

**Smart Defaults**:
- New users: Push enabled for direct messages and mentions only
- Auto-disable push if user hasn't opened app in 30 days
- EU users: All disabled by default (GDPR compliance)

**Frequency Capping**:
- Application-level: Max 50 push notifications per user per day
- Medium priority: Max 5 per user per hour
- Implemented in worker logic, not database

**Simple API**:
```
GET /api/v1/user/notification-preferences
PUT /api/v1/user/notification-preferences
```

**FIXES**: Eliminates preference propagation complexity, uses simple database storage

## 4. Infrastructure Choices

### Technology Stack Rationale

**Message Queue: Redis with Persistence**
- **Why**: Team already knows Redis, much simpler than Kafka
- **Configuration**: Single Redis instance with AOF persistence
- **Scaling**: Redis Cluster when we hit limits (not in Phase 1)
- **Cost**: $200/month for managed Redis (AWS ElastiCache)

**FIXES**: Eliminates Kafka operational complexity, matches team capabilities

**Database: PostgreSQL Only**
- **User preferences**: JSONB column in existing users table
- **Notification history**: Simple table with partitioning by month
- **Templates**: Static files, not database-stored
- **Scaling**: Read replica for reporting queries only

**FIXES**: Eliminates Redis memory issues, uses single database system

**Compute: Simple EC2 Auto Scaling**
- **Why**: Kubernetes is overkill for 4-person team
- **Setup**: Application Load Balancer + Auto Scaling Group
- **Instances**: 
  - API servers: 2-6 instances (t3.medium)
  - Background workers: 2-4 instances (t3.small)
- **Cost**: $800-1,500/month

**FIXES**: Eliminates Kubernetes complexity, appropriate for team size

**Monitoring: CloudWatch + PagerDuty**
- **Metrics**: Standard CloudWatch metrics + custom application metrics
- **Logs**: CloudWatch Logs with structured logging
- **Alerts**: PagerDuty for critical issues only
- **Cost**: $300/month

**FIXES**: Realistic monitoring costs, eliminates Prometheus/Grafana complexity

### Capacity Planning

**Realistic Load Calculations**:
- 10M MAU = ~333K DAU (industry standard 3% daily/monthly ratio)
- Average 10 notifications/user/day = 3.3M notifications/day
- Peak hours: 2x average = 77 notifications/second
- Growth buffer: 3x capacity = 231 notifications/second

**FIXES**: Corrects unrealistic user activity assumptions, right-sizes infrastructure

**Infrastructure Sizing**:
- Redis: 4GB memory (queue data only, not storage)
- PostgreSQL: 2 vCPUs, 16GB RAM, 500GB SSD
- Application servers: Total 8-24 vCPUs across instances

## 5. Failure Handling Strategy

### Simplified Retry Logic

**Per-Channel Retry Strategy**:
```python
RETRY_DELAYS = {
    'push': [60, 300, 900],  # 1min, 5min, 15min then fail
    'email': [300, 1800, 7200, 21600],  # 5min, 30min, 2hr, 6hr then fail
    'sms': [60, 300]  # 1min, 5min then fail (cost control)
}
```

**Dead Letter Handling**:
- Failed notifications go to `failed_notifications` table
- Daily report of failures for manual investigation
- No automatic replay (manual decision required)

**FIXES**: Removes complex circuit breaker patterns, realistic retry counts

### Graceful Degradation

**Simple Fallback Strategy**:
1. If push service is down: Skip push, log failure
2. If email service is down: Store in database for later retry
3. If database is down: Log to file, manual recovery needed
4. If Redis is down: Process notifications synchronously (slower but works)

**FIXES**: Eliminates complex degradation scenarios, focuses on likely failures

## 6. Implementation Timeline (6 Months)

### Phase 1: MVP Push Notifications (Months 1-2)
**Team Allocation**: 
- 2 engineers: Core notification API and push implementation
- 1 engineer: User preference integration
- 1 engineer: Infrastructure setup and monitoring

**Deliverables**:
- Push notifications working for all users
- Basic user preferences (enable/disable push)
- Redis queue system
- Basic monitoring

**Success Criteria**: 1,000 push notifications/day with >90% delivery rate

**FIXES**: Focuses team on single channel first, realistic deliverables

### Phase 2: Email and Scaling (Months 3-4)
**Team Allocation**:
- 2 engineers: Email integration and template system
- 1 engineer: Performance optimization and scaling
- 1 engineer: Advanced preferences and frequency capping

**Deliverables**:
- Email notifications with SendGrid integration
- Batch processing for low-priority notifications
- Auto-scaling infrastructure
- User preference management UI

**Success Criteria**: Handle 100K notifications/day across push and email

### Phase 3: Polish and SMS (Months 5-6)
**Team Allocation**:
- 1 engineer: SMS integration for security notifications
- 2 engineers: Performance tuning and reliability improvements
- 1 engineer: Analytics dashboard and reporting

**Deliverables**:
- SMS for critical notifications
- Comprehensive monitoring and alerting
- Analytics dashboard for business metrics
- Load testing validation

**Success Criteria**: Support full 10M MAU load with all channels

**FIXES**: Realistic team allocation, achievable milestones, proper skill distribution

## 7. Key Tradeoffs and Decisions

### Build vs. Buy Analysis

**Decision: Managed Services First**
- **Buy**: SendGrid (email), Twilio (SMS), Firebase (push), AWS managed services
- **Build**: Notification orchestration, user preferences, batching logic
- **Rationale**: 4-person team cannot operate complex infrastructure

**FIXES**: Acknowledges team size limitations, focuses on core business logic

### Consistency vs. Performance

**Decision: Immediate Consistency**
- Preference changes take effect immediately (simple database update)
- No caching of preferences (database can handle the load)
- Acceptable performance trade-off for operational simplicity

### Cost vs. Reliability

**Decision: Cost-Conscious Approach**
- Single Redis instance initially (can upgrade later)
- SMS severely limited to control costs
- Managed services despite higher cost (team efficiency)

**FIXES**: Realistic cost management, acknowledges team operational limits

## 8. Success Metrics

### Technical KPIs
- **Delivery Rate**: >90% for push, >85% for email (realistic targets)
- **Latency**: <5 minutes end-to-end for high priority
- **Uptime**: 99.5% system availability (achievable with this architecture)
- **Throughput**: Support 250 notifications/second sustained

### Business KPIs
- **Engagement**: 8% click-through rate on push notifications (industry average)
- **Opt-out Rate**: <10% monthly (allows for user education)
- **Cost per Notification**: <$0.002 average
- **User Satisfaction**: >3.5/5.0 rating

**FIXES**: Realistic performance targets based on industry standards

## 9. Risk Mitigation

### Technical Risks
- **Redis failure**: Daily backups, 4-hour RTO acceptable for notifications
- **Third-party API limits**: Monitor usage, implement queuing when approaching limits
- **Database bottlenecks**: Read replica for analytics, connection pooling
- **Team knowledge gaps**: Focus on technologies team already knows

### Business Risks
- **GDPR compliance**: Default opt-out for EU users, simple preference management
- **Spam complaints**: Conservative sending limits, easy unsubscribe
- **Cost overruns**: Hard limits in code, daily spend monitoring
- **Scope creep**: Stick to defined channels and features

**FIXES**: Addresses compliance requirements, realistic risk assessment

## 10. Critical Missing Components from Original

### Authentication & Security
- **API Authentication**: JWT tokens for internal service communication
- **User Session Management**: Leverage existing user authentication system
- **Data Encryption**: TLS in transit, encrypted database storage

### Data Retention & Compliance
- **GDPR Right to be Forgotten**: Cascade delete from notification_history table
- **Audit Trail**: Simple logging of all notification sends
- **Data Retention**: 90-day retention for notification history

### Monitoring & Debugging
- **Structured Logging**: JSON logs with correlation IDs
- **Error Tracking**: Sentry integration for error aggregation
- **Simple Distributed Tracing**: Request IDs through the system

**FIXES**: Addresses all missing components identified in the critique

## Conclusion

This revised notification system design focuses on pragmatic implementation within team constraints. By eliminating over-engineered components (Kafka, Kubernetes, complex WebSocket scaling) and leveraging managed services, the 4-person team can deliver a working system that handles 10M MAU.

Key changes from the original:
- Simplified technology stack matching team capabilities
- Realistic performance targets and cost estimates
- Proper mobile app integration patterns
- Achievable implementation timeline
- Focus on operational simplicity over theoretical scalability

Total estimated infrastructure cost: $2,000-3,000/month at full scale - a realistic budget that accounts for managed service premiums in exchange for reduced operational complexity.

The system can be built, deployed, and operated by the available team while providing room for future growth and enhancement.