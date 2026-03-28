# Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a scalable notification system capable of handling 10M monthly active users with a team of 4 backend engineers over 6 months. The design prioritizes rapid delivery, user experience, and operational reliability while making strategic tradeoffs to meet resource constraints.

## System Architecture Overview

### Core Components
1. **Notification Service** - Central orchestration layer
2. **Channel Adapters** - Push, Email, In-app, SMS delivery
3. **User Preference Engine** - Manages delivery preferences
4. **Queue System** - Handles batching and prioritization
5. **Analytics & Monitoring** - Tracks delivery metrics

## 1. Delivery Channels Strategy

### Channel Selection & Tradeoffs

**Push Notifications (Primary Channel)**
- **Implementation**: Firebase Cloud Messaging (FCM) for Android, Apple Push Notification Service (APNs) for iOS
- **Rationale**: Highest engagement rates (10-20%), real-time delivery
- **Capacity**: Handle 500K concurrent push notifications
- **Fallback**: In-app notification if push fails

**In-App Notifications (Secondary)**
- **Implementation**: WebSocket connections with Redis pub/sub
- **Rationale**: Guaranteed delivery when user is active
- **Capacity**: Support 100K concurrent WebSocket connections
- **Storage**: Redis with 7-day TTL for unread notifications

**Email (Batch Channel)**
- **Implementation**: SendGrid API with custom templating
- **Rationale**: High deliverability, rich content support
- **Capacity**: 1M emails/day within free tier limits
- **Batching**: Digest emails for non-urgent notifications

**SMS (Emergency Only)**
- **Implementation**: Twilio API
- **Rationale**: Highest open rates but expensive ($0.0075/message)
- **Usage**: Critical security alerts, payment confirmations only
- **Monthly Budget**: $5,000 (667K messages/month)

### Channel Priority Matrix
```
High Priority: Push → In-App → Email
Medium Priority: Push → Email (batched)
Low Priority: In-App → Email (daily digest)
Critical: SMS → Push → Email
```

## 2. Priority and Batching Logic

### Priority Classification

**Critical (P0)** - Immediate delivery
- Security alerts, payment issues
- Direct delivery, no batching
- All available channels
- SLA: <30 seconds

**High (P1)** - Near real-time
- Direct messages, mentions, friend requests
- Micro-batching (5-second windows)
- Push + In-app
- SLA: <2 minutes

**Medium (P2)** - Standard delivery
- Likes, comments, follows
- Batching windows: 15 minutes
- Push or Email (user preference)
- SLA: <15 minutes

**Low (P3)** - Digest delivery
- Weekly summaries, recommendations
- Daily/weekly batches
- Email only
- SLA: Within scheduled window

### Batching Strategy

**Micro-batching Implementation**:
```python
# Pseudo-code for batching logic
class NotificationBatcher:
    def __init__(self, batch_window_seconds, max_batch_size):
        self.window = batch_window_seconds
        self.max_size = max_batch_size
        
    def should_flush_batch(self, batch):
        return (
            len(batch) >= self.max_size or 
            time.now() - batch.created_at > self.window or
            any(notification.priority == 'CRITICAL' for notification in batch)
        )
```

**Batch Size Limits**:
- Push: 1000 notifications per batch
- Email: 500 recipients per batch
- SMS: 100 messages per batch (cost control)

## 3. User Preference Management

### Preference Schema
```json
{
  "user_id": "12345",
  "preferences": {
    "push_enabled": true,
    "email_enabled": true,
    "sms_enabled": false,
    "quiet_hours": {
      "start": "22:00",
      "end": "08:00",
      "timezone": "America/New_York"
    },
    "notification_types": {
      "direct_messages": ["push", "email"],
      "mentions": ["push"],
      "likes": ["push"],
      "follows": ["email"],
      "marketing": []
    },
    "frequency_caps": {
      "push_daily_limit": 50,
      "email_weekly_limit": 10
    }
  }
}
```

### Preference Engine Features

**Smart Defaults**:
- New users: Push enabled for high-priority only
- Gradual opt-in based on engagement patterns
- Geographic defaults (GDPR compliance for EU users)

**Frequency Capping**:
- Daily push limit: 50 notifications
- Weekly email limit: 10 emails
- Exponential backoff for ignored notifications

**Preference Management API**:
```
POST /api/v1/users/{user_id}/notification-preferences
GET /api/v1/users/{user_id}/notification-preferences
PUT /api/v1/users/{user_id}/notification-preferences/{type}
```

## 4. Infrastructure Choices

### Technology Stack Rationale

**Message Queue: Apache Kafka**
- **Why**: High throughput (1M messages/second), durability, partitioning
- **Alternative Considered**: Redis Streams (simpler but less durable)
- **Configuration**: 3 brokers, replication factor 3, 7-day retention
- **Cost**: ~$1,500/month on AWS MSK

**Database: PostgreSQL + Redis**
- **PostgreSQL**: User preferences, notification templates, audit logs
- **Redis**: In-app notification cache, rate limiting, session management
- **Why**: Team expertise, ACID compliance for preferences
- **Scaling**: Read replicas for notification queries

**Compute: Kubernetes on AWS EKS**
- **Why**: Auto-scaling, container orchestration, team familiarity
- **Pods**: 
  - Notification Service: 5 pods (auto-scale 2-10)
  - Channel Adapters: 3 pods each
  - Worker Processes: 8 pods
- **Cost**: ~$3,000/month

**Monitoring: Prometheus + Grafana + PagerDuty**
- **Metrics**: Delivery rates, latency, error rates per channel
- **Alerts**: SLA violations, queue depth, service health
- **Cost**: ~$500/month

### Capacity Planning

**Peak Load Assumptions**:
- 10M MAU = ~500K DAU
- Average 20 notifications/user/day = 10M notifications/day
- Peak hours: 3x average = 1,000 notifications/second
- Growth buffer: 2x capacity = 2,000 notifications/second

**Infrastructure Sizing**:
- Kafka: 6 partitions for notification topic
- Redis: 16GB memory, 95% cache hit rate
- PostgreSQL: 4 vCPUs, 32GB RAM, 1TB SSD
- Application servers: Total 20 vCPUs across pods

## 5. Failure Handling Strategy

### Retry Mechanisms

**Exponential Backoff Strategy**:
```python
def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except RetryableException as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
```

**Channel-Specific Retry Logic**:
- **Push**: 3 retries over 1 hour, then mark failed
- **Email**: 5 retries over 24 hours (ISP temporary blocks)
- **SMS**: 2 retries over 30 minutes (cost consideration)
- **In-app**: No retries (real-time only)

### Circuit Breaker Pattern

**Implementation per channel**:
- Failure threshold: 50% error rate over 5 minutes
- Open circuit duration: 30 seconds
- Half-open state: Allow 10 test requests

### Dead Letter Queues

**DLQ Strategy**:
- Failed notifications → DLQ after max retries
- Manual review process for DLQ items
- Replay capability for resolved issues
- 30-day retention in DLQ

### Graceful Degradation

**Fallback Hierarchy**:
1. Primary channel fails → Try secondary channel
2. All channels fail → Store for retry
3. System overload → Drop low-priority notifications
4. Database unavailable → Cache-only mode

### Monitoring & Alerting

**Key Metrics**:
- Delivery rate by channel (target: >95%)
- End-to-end latency (target: <2 minutes for P1)
- Queue depth (alert: >10K messages)
- Error rate by channel (alert: >5%)

**Alert Escalation**:
- P1 alerts → Immediate PagerDuty
- P2 alerts → Slack notification
- P3 alerts → Email to team

## 6. Implementation Timeline (6 Months)

### Phase 1: Foundation (Months 1-2)
**Team Allocation**: All 4 engineers
- Set up Kafka, Redis, PostgreSQL infrastructure
- Implement basic notification service with push notifications
- Build user preference management system
- Basic monitoring and alerting

**Deliverables**:
- Push notifications working for 100K users
- User preference API
- Basic admin dashboard

### Phase 2: Multi-Channel (Months 3-4)
**Team Allocation**: 2 engineers on channels, 2 on reliability
- Implement email and in-app notification channels
- Add priority and batching logic
- Implement retry mechanisms and circuit breakers
- Performance optimization

**Deliverables**:
- All 4 channels operational
- Batching and priority system
- Failure handling mechanisms

### Phase 3: Scale & Polish (Months 5-6)
**Team Allocation**: 1 on SMS, 2 on performance, 1 on analytics
- SMS integration for critical notifications
- Performance tuning for 10M MAU scale
- Advanced analytics and reporting
- Load testing and optimization

**Deliverables**:
- Full system supporting 10M MAU
- Comprehensive monitoring
- Performance benchmarks met

## 7. Key Tradeoffs and Decisions

### Build vs. Buy Analysis

**Decision: Hybrid Approach**
- **Build**: Core orchestration, batching logic, preference management
- **Buy**: Third-party services for actual delivery (FCM, SendGrid, Twilio)
- **Rationale**: Maximize team efficiency while maintaining control

### Consistency vs. Performance

**Decision: Eventual Consistency**
- Preference updates may take up to 30 seconds to propagate
- Acceptable for notification system vs. real-time requirements
- Enables better caching and performance

### Cost vs. Reliability

**Decision: Balanced Approach**
- SMS limited to critical notifications only (cost control)
- 3-node Kafka cluster (reliability) vs. single node (cost)
- Managed services where possible to reduce operational burden

### Complexity vs. Time-to-Market

**Decision: Phased Approach**
- MVP with push notifications first
- Gradual addition of channels and features
- Focus on core functionality over advanced features

## 8. Success Metrics

### Technical KPIs
- **Delivery Rate**: >95% for all channels
- **Latency**: <2 minutes end-to-end for P1 notifications
- **Uptime**: 99.9% system availability
- **Throughput**: Support 2,000 notifications/second peak load

### Business KPIs
- **Engagement**: 15% click-through rate on push notifications
- **Opt-out Rate**: <5% monthly churn from notifications
- **Cost per Notification**: <$0.001 average across all channels
- **User Satisfaction**: >4.0/5.0 rating for notification relevance

## 9. Risk Mitigation

### Technical Risks
- **Kafka cluster failure**: Multi-AZ deployment, automated failover
- **Third-party API limits**: Multiple provider fallbacks
- **Database bottlenecks**: Read replicas, connection pooling
- **Memory leaks**: Comprehensive monitoring, automatic restarts

### Business Risks
- **Regulatory compliance**: GDPR-compliant preference management
- **Spam complaints**: Strict opt-in policies, easy unsubscribe
- **Cost overruns**: Automated budget alerts, usage caps
- **Team capacity**: Cross-training, documentation, external consultants on standby

## Conclusion

This notification system design balances scalability, reliability, and development velocity within the constraints of a 4-engineer team and 6-month timeline. The phased approach ensures early value delivery while building toward full-scale capability. Key success factors include disciplined scope management, leveraging managed services, and maintaining focus on core user experience over advanced features.

The proposed architecture can handle 10M MAU with room for 2x growth, provides multiple delivery channels with intelligent fallbacks, and includes comprehensive monitoring and failure handling. Total estimated infrastructure cost: $5,000-7,000/month at full scale.