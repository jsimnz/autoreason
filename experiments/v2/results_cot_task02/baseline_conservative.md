# Notification System Design for Social App (10M MAU)

## Executive Summary

This document outlines a comprehensive notification system design for a social app serving 10 million monthly active users. The system prioritizes user experience through intelligent batching, multi-channel delivery, and granular preference management while maintaining 99.9% reliability and sub-30-second delivery times.

**Key Design Decisions:**
- Event-driven architecture with Redis for real-time processing
- Smart batching to reduce notification fatigue
- Gradual rollout strategy to minimize risk
- Cost-optimized channel selection (push-first, SMS for critical only)

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
[Mobile Apps] ──┐
[Web App]     ──┼──> [Load Balancer] ──> [Notification Gateway]
[Backend APIs]──┘                              │
                                               ▼
                                    [Message Queue (Redis)]
                                               │
                                               ▼
                                    [Notification Processor]
                                               │
                        ┌──────────────────────┼──────────────────────┐
                        ▼                      ▼                      ▼
                [Channel Router]        [Batching Engine]     [Preference Engine]
                        │                      │                      │
           ┌────────────┼────────────┐        │                      │
           ▼            ▼            ▼        ▼                      ▼
    [Push Service] [Email Service] [SMS]  [Batch Store]      [User Preferences DB]
           │            │            │        │                      │
           ▼            ▼            ▼        ▼                      ▼
    [FCM/APNS]    [SendGrid API]  [Twilio] [PostgreSQL]        [PostgreSQL]
```

### 1.2 Core Components

**Notification Gateway**: RESTful API service handling incoming notification requests
**Message Queue**: Redis-based queue for async processing and load balancing
**Notification Processor**: Core business logic engine for routing and transformation
**Channel Services**: Dedicated services for each delivery channel
**Preference Engine**: User preference management and enforcement

## 2. Delivery Channels Strategy

### 2.1 Channel Priority Matrix

| Notification Type | Push | In-App | Email | SMS |
|------------------|------|--------|-------|-----|
| Friend Request   | ✓    | ✓      | Daily Digest | ✗ |
| New Message      | ✓    | ✓      | Hourly Batch | ✗ |
| Live Event       | ✓    | ✓      | ✗     | ✗ |
| Security Alert   | ✓    | ✓      | ✓     | ✓ |
| Weekly Summary   | ✗    | ✗      | ✓     | ✗ |

### 2.2 Push Notifications (Primary Channel)
**Technology**: Firebase Cloud Messaging (Android), Apple Push Notification Service (iOS)
**Rationale**: Immediate delivery, high engagement rates, cost-effective at scale

**Implementation Details:**
- Token management with automatic refresh handling
- Rich media support for images and actions
- Deep linking for direct app navigation
- A/B testing framework for message optimization

**Delivery SLA**: 95% delivered within 30 seconds

### 2.3 In-App Notifications
**Technology**: WebSocket connections with Socket.io, fallback to HTTP polling
**Rationale**: Guaranteed delivery for active users, supports rich interactions

**Implementation Details:**
- Real-time WebSocket for active sessions
- Persistent storage for offline users
- Toast notifications with action buttons
- Notification center with read/unread states

**Delivery SLA**: Instant for online users, queued for offline

### 2.4 Email Notifications
**Technology**: SendGrid API with template management
**Rationale**: High deliverability, rich content support, digest functionality

**Implementation Details:**
- Intelligent batching (hourly for messages, daily for social updates)
- Responsive HTML templates with personalization
- Unsubscribe management and list hygiene
- Bounce and complaint handling

**Delivery SLA**: Batched emails sent within 1 hour of batch window

### 2.5 SMS Notifications (Critical Only)
**Technology**: Twilio API for global coverage
**Rationale**: Highest urgency channel, reserved for security and critical alerts

**Implementation Details:**
- Geographic routing for optimal delivery
- Character limit optimization
- International number format handling
- Delivery receipt tracking

**Delivery SLA**: 90% delivered within 60 seconds
**Cost Consideration**: $0.0075 per SMS, estimated 50K critical notifications/month = $375/month

## 3. Priority and Batching Logic

### 3.1 Priority Classification

```javascript
const PRIORITY_LEVELS = {
  CRITICAL: 0,    // Security alerts, payment issues
  HIGH: 1,        // Direct messages, friend requests
  MEDIUM: 2,      // Likes, comments on your content
  LOW: 3,         // General social updates
  DIGEST: 4       // Weekly summaries, recommendations
};
```

### 3.2 Intelligent Batching Strategy

**Real-time Delivery (Critical/High):**
- Process immediately upon receipt
- Maximum 30-second delay for delivery optimization
- No batching for security or direct communication

**Smart Batching (Medium/Low):**
- 15-minute windows for similar notification types
- User activity-based timing (send when user typically active)
- Maximum 6 notifications per batch to prevent overwhelm

**Digest Batching (Low Priority):**
- Daily digest at user's preferred time (default 6 PM local)
- Weekly summary every Sunday
- Monthly highlights for low-engagement users

### 3.3 Batching Algorithm Implementation

```python
class SmartBatcher:
    def __init__(self):
        self.batch_windows = {
            'immediate': timedelta(seconds=30),
            'short': timedelta(minutes=15),
            'hourly': timedelta(hours=1),
            'daily': timedelta(days=1)
        }
    
    def determine_batch_strategy(self, notification_type, user_activity):
        if notification_type in ['security', 'direct_message']:
            return 'immediate'
        elif user_activity.last_seen < timedelta(hours=1):
            return 'short'  # User recently active
        else:
            return 'hourly'
```

## 4. User Preference Management

### 4.1 Preference Hierarchy

1. **Global Preferences**: Overall notification on/off
2. **Channel Preferences**: Enable/disable specific channels
3. **Category Preferences**: Control notification types
4. **Quiet Hours**: Time-based delivery restrictions
5. **Frequency Limits**: Maximum notifications per time period

### 4.2 Database Schema

```sql
CREATE TABLE user_preferences (
    user_id UUID PRIMARY KEY,
    global_enabled BOOLEAN DEFAULT true,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    max_push_per_hour INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE notification_categories (
    user_id UUID,
    category VARCHAR(50),
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    frequency VARCHAR(20) DEFAULT 'real_time', -- real_time, hourly, daily, never
    PRIMARY KEY (user_id, category)
);
```

### 4.3 Preference Enforcement Engine

```python
class PreferenceEngine:
    def check_delivery_allowed(self, user_id, notification_type, channel):
        prefs = self.get_user_preferences(user_id)
        
        # Check global settings
        if not prefs.global_enabled:
            return False
            
        # Check channel settings
        if channel == 'push' and not prefs.push_enabled:
            return False
            
        # Check quiet hours
        if self.in_quiet_hours(prefs.timezone, prefs.quiet_hours):
            if notification_type not in ['critical', 'security']:
                return False
                
        # Check frequency limits
        if self.exceeds_frequency_limit(user_id, channel, prefs):
            return False
            
        return True
```

## 5. Infrastructure Choices and Rationale

### 5.1 Core Infrastructure

**Application Platform**: AWS ECS with Fargate
- **Rationale**: Managed container orchestration, auto-scaling, reduced operational overhead
- **Alternative Considered**: Kubernetes (rejected due to team size and complexity)

**Message Queue**: Redis with Redis Cluster
- **Rationale**: Sub-millisecond latency, built-in pub/sub, familiar to team
- **Capacity**: Handle 10,000 messages/second with 3-node cluster
- **Alternative Considered**: Apache Kafka (overkill for current scale)

**Database**: PostgreSQL with read replicas
- **Rationale**: ACID compliance, JSON support for flexible schemas, team expertise
- **Configuration**: Primary + 2 read replicas across availability zones
- **Alternative Considered**: DynamoDB (chosen PostgreSQL for complex queries)

**Caching**: Redis (separate from message queue)
- **Use Cases**: User preferences, notification templates, rate limiting
- **Configuration**: 2-node cluster with failover

### 5.2 External Service Integrations

**Push Notifications**: Firebase Cloud Messaging + Apple Push Notification Service
- **Cost**: Free for reasonable volumes
- **Reliability**: 99.9% delivery rate guaranteed by providers

**Email Service**: SendGrid
- **Cost**: $15/month for 40K emails (estimated volume)
- **Features**: Template management, analytics, deliverability optimization

**SMS Service**: Twilio
- **Cost**: ~$375/month for estimated 50K critical notifications
- **Coverage**: Global reach with local number support

### 5.3 Monitoring and Observability

**Application Monitoring**: DataDog
- **Metrics**: Delivery rates, latency, error rates, queue depth
- **Alerting**: PagerDuty integration for critical failures

**Infrastructure Monitoring**: AWS CloudWatch
- **Auto-scaling triggers**: CPU > 70%, queue depth > 1000 messages
- **Cost optimization**: Scheduled scaling during low-traffic hours

## 6. Failure Handling and Reliability

### 6.1 Failure Scenarios and Mitigation

**External Service Outages:**
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call_service(self, service_func):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise ServiceUnavailableError("Circuit breaker is OPEN")
        
        try:
            result = service_func()
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            raise e
```

**Retry Strategy:**
- Exponential backoff: 1s, 2s, 4s, 8s, 16s (max)
- Maximum 5 retry attempts
- Dead letter queue for permanently failed notifications
- Manual retry capability for critical notifications

**Database Failures:**
- Read replica failover within 30 seconds
- Write operations queued during primary database recovery
- Point-in-time recovery capability (7-day retention)

**Queue Overflow Protection:**
- Priority queue implementation (critical notifications first)
- Automatic scaling triggers at 80% queue capacity
- Rate limiting per user to prevent abuse (100 notifications/hour max)

### 6.2 Data Consistency and Durability

**At-Least-Once Delivery Guarantee:**
- Message acknowledgment only after successful delivery
- Persistent storage for all notification attempts
- Idempotency keys to prevent duplicate deliveries

**Audit Trail:**
```sql
CREATE TABLE notification_audit (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    notification_type VARCHAR(50),
    channel VARCHAR(20),
    status VARCHAR(20), -- pending, sent, delivered, failed
    attempt_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    delivered_at TIMESTAMP,
    failure_reason TEXT
);
```

## 7. Implementation Timeline (6 Months)

### Phase 1: Foundation (Months 1-2)
**Team Split: 2 engineers on core system, 2 on channels**

**Month 1:**
- Week 1-2: Infrastructure setup (AWS ECS, Redis, PostgreSQL)
- Week 3-4: Core notification gateway and message queue implementation
- Deliverables: Basic notification API, Redis message queue, database schema

**Month 2:**
- Week 1-2: Push notification channel (FCM/APNS integration)
- Week 3-4: User preference service and basic batching logic
- Deliverables: Working push notifications, preference management API

### Phase 2: Multi-Channel Delivery (Months 3-4)
**Team Split: 1 on email/SMS, 1 on in-app, 2 on optimization**

**Month 3:**
- Week 1-2: Email channel with SendGrid integration and batching
- Week 3-4: In-app notifications with WebSocket connections
- Deliverables: Email digest system, real-time in-app notifications

**Month 4:**
- Week 1-2: SMS channel for critical notifications only
- Week 3-4: Advanced preference engine and quiet hours
- Deliverables: Complete multi-channel system, smart preferences

### Phase 3: Production Readiness (Months 5-6)
**Team Split: 2 on reliability, 1 on monitoring, 1 on optimization**

**Month 5:**
- Week 1-2: Failure handling, retry logic, and circuit breakers
- Week 3-4: Monitoring, alerting, and analytics dashboard
- Deliverables: Production-ready reliability features

**Month 6:**
- Week 1-2: Load testing and performance optimization
- Week 3-4: Documentation, team training, and go-live preparation
- Deliverables: System ready for production deployment

**Risk Mitigation:**
- 20% buffer built into each phase for unexpected complexity
- Weekly team sync to identify blockers early
- Phased rollout starting with 1% of users in Month 6

## 8. Success Metrics and KPIs

### 8.1 Technical Metrics
- **Delivery Rate**: >98% for critical, >95% for all notifications
- **Latency**: <30 seconds for push, <5 minutes for email batches
- **Uptime**: 99.9% system availability
- **Throughput**: Handle 1000+ notifications/second during peak

### 8.2 Business Metrics
- **User Engagement**: 25%+ push notification open rate
- **Opt-out Rate**: <5% monthly unsubscribe rate
- **User Satisfaction**: >4.0/5.0 rating for notification relevance
- **Cost Efficiency**: <$0.15 per MAU total notification cost

### 8.3 Operational Metrics
- **Mean Time to Recovery**: <15 minutes for critical failures
- **False Alert Rate**: <2% for monitoring alerts
- **Team Velocity**: Maintain 80%+ sprint completion rate
- **Technical Debt**: <10% of development time spent on maintenance

## 9. Cost Analysis and Optimization

### 9.1 Monthly Cost Breakdown (10M MAU)

| Component | Monthly Cost | Notes |
|-----------|--------------|--------|
| AWS ECS (4 services) | $480 | t3.medium instances with auto-scaling |
| Redis Cluster | $290 | r6g.large nodes with failover |
| PostgreSQL RDS | $350 | db.r6g.large primary + 2 read replicas |
| Load Balancers | $45 | 2 ALBs for redundancy