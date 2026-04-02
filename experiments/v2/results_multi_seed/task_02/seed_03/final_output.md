# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system design for a social app with 10M monthly active users, deliverable by 4 backend engineers within 6 months. The system prioritizes reliability, user experience, and operational simplicity while maintaining cost efficiency at scale.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator for all notifications
- **Channel Adapters**: Separate adapters for push, email, in-app, SMS
- **Preference Engine**: User preference management and filtering
- **Queue System**: Message queuing with priority handling
- **Template Engine**: Dynamic content generation
- **Analytics & Monitoring**: Delivery tracking and system health

### Key Design Principles
1. **Fail-fast approach**: Prioritize system stability over feature completeness
2. **Channel isolation**: Failures in one channel don't affect others
3. **Gradual rollout**: Phased implementation to validate at scale
4. **Cost optimization**: Minimize expensive channels (SMS) through smart routing

## 2. Delivery Channels Implementation

### 2.1 Push Notifications (Primary Channel)
**Technology Stack**: Firebase Cloud Messaging (FCM) for Android/iOS
**Rationale**: Mature, reliable, free at our scale, handles device token management

```
Implementation Details:
- Topic-based subscriptions for broadcast notifications
- Direct token messaging for personalized notifications
- Automatic token refresh handling
- Rich media support (images, actions)
```

**Capacity Planning**: 
- Peak: 50K notifications/minute (assuming 5% DAU engagement)
- FCM handles 1M+ messages/minute, providing 20x headroom

### 2.2 Email Notifications
**Technology Stack**: Amazon SES
**Rationale**: Cost-effective ($0.10/1000 emails), good deliverability, AWS integration

```
Implementation Features:
- HTML/text dual format
- Unsubscribe link automation
- Bounce/complaint handling
- Template versioning
```

**Usage Strategy**: 
- Weekly digests for inactive users
- Critical account notifications
- Re-engagement campaigns

### 2.3 In-App Notifications
**Technology Stack**: Custom WebSocket service + Redis
**Rationale**: Real-time delivery, no external costs, full control

```
Architecture:
- WebSocket connections managed by Node.js servers
- Redis for connection state and message persistence
- Fallback to polling for unreliable connections
```

**Scalability**: 
- 100K concurrent connections per server instance
- Auto-scaling based on connection count

### 2.4 SMS Notifications (Limited Use)
**Technology Stack**: Twilio
**Rationale**: Reliable delivery, global coverage, pay-per-use model

```
Usage Constraints:
- Only for critical security notifications (2FA, login alerts)
- Strict rate limiting: max 2 SMS/user/day
- Geographic restrictions based on cost
```

**Cost Management**: ~$5K/month at 50K SMS/month

## 3. Priority and Batching Logic

### 3.1 Priority Classification

```
CRITICAL (P0): Security alerts, account issues
- Immediate delivery across all channels
- No batching, individual processing
- 99.9% delivery SLA

HIGH (P1): Direct mentions, comments on user content
- Delivery within 5 minutes
- Micro-batching (10 notifications/batch)
- 99% delivery SLA

MEDIUM (P2): Likes, follows, general activity
- Delivery within 30 minutes
- Batching up to 100 notifications
- 95% delivery SLA

LOW (P3): Weekly digests, promotional content
- Delivery within 24 hours
- Large batches (1000+ notifications)
- 90% delivery SLA
```

### 3.2 Batching Strategy

**Queue Implementation**: Redis Streams with consumer groups
```redis
# Priority queues
XADD notifications:p0 * user_id 123 type security_alert
XADD notifications:p1 * user_id 456 type mention
XADD notifications:p2 * user_id 789 type like
```

**Processing Logic**:
- P0: Immediate processing, dedicated workers
- P1: 5-minute batching window
- P2/P3: Time-based batching with size limits

### 3.3 Smart Batching Rules

```python
class BatchingEngine:
    def should_flush_batch(self, batch, priority):
        if priority == "P0":
            return True  # No batching
        elif priority == "P1":
            return len(batch) >= 10 or age(batch) > 300  # 5 min
        elif priority == "P2":
            return len(batch) >= 100 or age(batch) > 1800  # 30 min
        else:  # P3
            return len(batch) >= 1000 or age(batch) > 86400  # 24 hr
```

## 4. User Preference Management

### 4.1 Preference Schema

```json
{
  "user_id": "123",
  "preferences": {
    "push": {
      "enabled": true,
      "quiet_hours": {
        "start": "22:00",
        "end": "08:00",
        "timezone": "America/New_York"
      },
      "types": {
        "mentions": true,
        "likes": false,
        "follows": true,
        "comments": true
      }
    },
    "email": {
      "enabled": true,
      "frequency": "weekly_digest",
      "types": {
        "security": true,
        "social": false,
        "marketing": false
      }
    },
    "sms": {
      "enabled": false,
      "number": "+1234567890",
      "verified": true,
      "types": {
        "security": true
      }
    }
  },
  "global_settings": {
    "do_not_disturb": false,
    "vacation_mode": false
  }
}
```

### 4.2 Preference Storage
**Technology**: PostgreSQL with JSON columns
**Rationale**: ACID compliance, complex queries, JSON flexibility

```sql
CREATE TABLE user_preferences (
    user_id BIGINT PRIMARY KEY,
    preferences JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW(),
    version INTEGER DEFAULT 1
);

CREATE INDEX idx_preferences_push ON user_preferences 
USING GIN ((preferences->'push'));
```

### 4.3 Default Preferences Strategy
- New users: Conservative defaults (minimal notifications)
- Progressive opt-in during onboarding
- A/B testing for optimal default configurations

## 5. Infrastructure Choices

### 5.1 Core Infrastructure Stack

**Application Layer**:
- **Language**: Node.js with TypeScript
- **Framework**: Express.js with custom notification middleware
- **Rationale**: Team expertise, excellent async I/O, rich ecosystem

**Data Layer**:
- **Primary DB**: PostgreSQL 14 (user preferences, notification logs)
- **Cache/Queue**: Redis 7.0 (message queuing, session management)
- **Analytics**: ClickHouse (notification analytics, delivery metrics)

**Deployment**:
- **Platform**: AWS EKS (Kubernetes)
- **Scaling**: Horizontal Pod Autoscaler based on queue depth
- **Monitoring**: Prometheus + Grafana

### 5.2 Service Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   API Gateway   │───▶│ Notification API │───▶│ Preference API  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Notification     │
                       │ Orchestrator     │
                       └──────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │Push Adapter │ │Email Adapter│ │ SMS Adapter │
        └─────────────┘ └─────────────┘ └─────────────┘
```

### 5.3 Scaling Strategy

**Horizontal Scaling Triggers**:
- Queue depth > 1000 messages: Scale notification workers
- CPU > 70%: Scale API pods
- Memory > 80%: Scale Redis cluster

**Capacity Planning**:
- **Peak Load**: 100K notifications/minute
- **Infrastructure**: 20 application pods, 3-node Redis cluster
- **Cost**: ~$3K/month AWS infrastructure

## 6. Failure Handling & Reliability

### 6.1 Circuit Breaker Pattern

```javascript
class ChannelCircuitBreaker {
  constructor(channel, threshold = 50, timeout = 60000) {
    this.channel = channel;
    this.failureThreshold = threshold;
    this.timeout = timeout;
    this.state = 'CLOSED'; // CLOSED, OPEN, HALF_OPEN
    this.failures = 0;
  }

  async execute(notification) {
    if (this.state === 'OPEN') {
      throw new Error(`Circuit breaker OPEN for ${this.channel}`);
    }
    
    try {
      const result = await this.sendNotification(notification);
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }
}
```

### 6.2 Retry Strategy

**Exponential Backoff**:
- Initial delay: 1 second
- Max delay: 300 seconds (5 minutes)
- Max retries: 5 attempts
- Jitter: ±25% to prevent thundering herd

**Dead Letter Queue**:
- Failed notifications after max retries
- Manual investigation and replay capability
- Alerts for DLQ depth > 100

### 6.3 Fallback Mechanisms

```javascript
const deliveryFallbacks = {
  push: ['in_app', 'email'],
  email: ['push', 'in_app'],
  sms: ['push', 'email'],
  in_app: ['push']
};
```

**Fallback Triggers**:
- Channel unavailable > 5 minutes
- Error rate > 20% over 10-minute window
- Manual failover capability

### 6.4 Monitoring & Alerting

**Key Metrics**:
- Delivery success rate per channel
- End-to-end latency (P50, P95, P99)
- Queue depth and processing rate
- Error rates by type and channel

**Alert Thresholds**:
- Delivery success rate < 95% (Warning)
- Delivery success rate < 90% (Critical)
- Queue depth > 10K messages (Critical)
- Any P0 notification failure (Immediate)

## 7. Implementation Timeline (6 Months)

### Phase 1: Foundation (Months 1-2)
**Team Allocation**: 4 engineers
- Core notification service architecture
- PostgreSQL schema and basic APIs
- Redis queue implementation
- Push notification integration (FCM)

**Deliverables**:
- Basic push notifications working
- User preference management
- Simple batching logic

### Phase 2: Channel Expansion (Months 3-4)
**Team Allocation**: 3 engineers on channels, 1 on reliability
- Email integration (SES)
- In-app notification system
- SMS integration (limited scope)
- Circuit breaker implementation

**Deliverables**:
- Multi-channel delivery
- Basic failure handling
- Preference-based filtering

### Phase 3: Scale & Polish (Months 5-6)
**Team Allocation**: 2 engineers on optimization, 2 on monitoring
- Advanced batching algorithms
- Comprehensive monitoring
- Performance optimization
- Load testing and tuning

**Deliverables**:
- Production-ready system
- Full observability
- Documentation and runbooks

## 8. Key Tradeoffs & Rationale

### 8.1 Build vs Buy Decisions

**Built In-House**:
- **Notification Orchestrator**: Core business logic requires customization
- **In-app Notifications**: Real-time requirements, cost control
- **Preference Management**: Complex business rules

**Third-Party Services**:
- **Push Delivery**: FCM mature, reliable, free
- **Email Delivery**: SES cost-effective, good deliverability
- **SMS Delivery**: Twilio reliable, pay-per-use model

### 8.2 Technology Choices

**Node.js over Go/Java**:
- ✅ Team expertise reduces development time
- ✅ Excellent async I/O for notification workloads
- ❌ Slightly higher memory usage at scale

**PostgreSQL over NoSQL**:
- ✅ ACID compliance for user preferences
- ✅ Complex querying capabilities
- ❌ Potential scaling bottleneck (mitigated by read replicas)

**Redis over Apache Kafka**:
- ✅ Simpler operations, faster implementation
- ✅ Built-in data structures for batching
- ❌ Less robust for high-throughput scenarios

### 8.3 Feature Scope Limitations

**Excluded Features** (for initial launch):
- Rich notification templates
- A/B testing framework
- Advanced personalization
- Cross-platform notification sync

**Rationale**: Focus on core reliability and scalability first

## 9. Success Metrics & KPIs

### 9.1 Technical Metrics
- **Availability**: 99.9% uptime SLA
- **Latency**: P95 end-to-end delivery < 30 seconds
- **Throughput**: Handle 100K notifications/minute peak
- **Delivery Success Rate**: >95% across all channels

### 9.2 Business Metrics
- **User Engagement**: 15% increase in DAU notification interaction
- **Retention**: 10% improvement in Day-7 retention
- **Opt-out Rate**: <5% monthly notification unsubscribe rate

### 9.3 Operational Metrics
- **MTTR**: <30 minutes for critical issues
- **Change Failure Rate**: <5% for production deployments
- **Cost per Notification**: <$0.001 average across all channels

## 10. Risk Mitigation

### 10.1 Technical Risks

**Risk**: FCM service outages
**Mitigation**: In-app notification fallback, SLA monitoring

**Risk**: Database performance degradation
**Mitigation**: Read replicas, query optimization, connection pooling

**Risk**: Queue overflow during traffic spikes
**Mitigation**: Auto-scaling, backpressure mechanisms, priority queues

### 10.2 Business Risks

**Risk**: User notification fatigue
**Mitigation**: Smart batching, preference controls, engagement monitoring

**Risk**: Compliance violations (GDPR, CAN-SPAM)
**Mitigation**: Explicit consent tracking, easy unsubscribe, data retention policies

## 11. Conclusion

This notification system design balances scalability, reliability, and development velocity within the given constraints. The phased approach ensures early value delivery while building toward a robust, production-ready system. Key success factors include:

1. **Pragmatic technology choices** leveraging team expertise
2. **Incremental complexity** with clear fallback mechanisms  
3. **Cost-conscious design** optimizing expensive channels
4. **Comprehensive monitoring** enabling proactive issue resolution

The proposed architecture supports 10M MAU with room for 5x growth before requiring significant architectural changes, providing a solid foundation for the product's scaling needs.