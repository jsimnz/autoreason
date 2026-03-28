# Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a comprehensive notification system architecture capable of handling 10M monthly active users with a 4-engineer team over 6 months. The design prioritizes reliability, scalability, and user experience while making pragmatic technology choices that balance functionality with implementation complexity.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestration layer
- **Channel Handlers**: Specialized handlers for each delivery channel
- **Queue System**: Message queuing with priority support
- **User Preference Service**: Centralized preference management
- **Analytics & Monitoring**: Delivery tracking and system health

### Technology Stack Rationale
- **Primary Database**: PostgreSQL (team familiarity, ACID compliance for preferences)
- **Message Queue**: Redis with Lua scripts (simpler than Kafka for this scale)
- **Cache Layer**: Redis (dual-purpose: queue + cache)
- **API Framework**: Node.js/Express or Go (based on team expertise)
- **Infrastructure**: AWS/GCP managed services to reduce operational overhead

## 2. Delivery Channels Implementation

### 2.1 Push Notifications
**Technology**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)

**Implementation**:
```javascript
// Push notification handler
class PushNotificationHandler {
  async send(notification) {
    const { userId, title, body, data } = notification;
    const tokens = await this.getDeviceTokens(userId);
    
    const payload = {
      notification: { title, body },
      data: { ...data, notificationId: notification.id },
      android: { priority: 'high', ttl: 3600000 },
      apns: { payload: { aps: { badge: await this.getBadgeCount(userId) } } }
    };
    
    return await this.fcm.sendToDevice(tokens, payload);
  }
}
```

**Capacity**: 1M push notifications/day peak
**Latency SLA**: <30 seconds for high priority, <5 minutes for normal

### 2.2 Email Notifications
**Technology**: SendGrid (99.9% deliverability, robust API)

**Implementation Strategy**:
- Batch processing for digest emails (daily/weekly summaries)
- Transactional emails for immediate actions
- Template management with personalization
- Bounce/spam handling with automatic list hygiene

**Volume**: 500K emails/day, 50K transactional emails/day

### 2.3 In-App Notifications
**Technology**: WebSocket connections with Socket.io + Redis adapter

**Implementation**:
- Real-time delivery for active users
- Persistent storage in PostgreSQL for offline users
- Connection pooling and horizontal scaling
- Fallback to polling for connection issues

**Capacity**: 100K concurrent connections

### 2.4 SMS Notifications
**Technology**: Twilio (reliability + global reach)

**Usage**: Critical notifications only (security alerts, payment issues)
- Volume: 10K SMS/day maximum
- Cost optimization: Strict filtering and user opt-in required

## 3. Priority and Batching Logic

### 3.1 Priority Levels
```typescript
enum NotificationPriority {
  CRITICAL = 0,    // Security, payments - immediate delivery
  HIGH = 1,        // Direct messages, mentions - <1 minute
  NORMAL = 2,      // Likes, follows - <15 minutes
  LOW = 3          // Digest, recommendations - batched processing
}
```

### 3.2 Batching Strategy
**High Priority (CRITICAL/HIGH)**:
- Individual processing
- Dedicated worker processes
- Redis priority queues

**Normal/Low Priority**:
- Batch size: 100-1000 notifications
- Processing interval: 5-60 minutes based on priority
- User-level batching to prevent spam

### 3.3 Queue Implementation
```lua
-- Redis Lua script for priority queue
local function addNotification(priority, userId, notification)
  local queueKey = "notifications:priority:" .. priority
  local userKey = "user:last_sent:" .. userId
  local now = redis.call('TIME')[1]
  
  -- Rate limiting check
  local lastSent = redis.call('GET', userKey) or 0
  if (now - lastSent) < 60 then -- 1 minute cooldown
    return false
  end
  
  redis.call('ZADD', queueKey, now, notification)
  redis.call('SET', userKey, now, 'EX', 3600)
  return true
end
```

## 4. User Preference Management

### 4.1 Preference Schema
```sql
CREATE TABLE notification_preferences (
  user_id BIGINT PRIMARY KEY,
  channel_preferences JSONB DEFAULT '{
    "push": {"enabled": true, "quiet_hours": {"start": "22:00", "end": "08:00"}},
    "email": {"enabled": true, "frequency": "immediate"},
    "sms": {"enabled": false},
    "in_app": {"enabled": true}
  }',
  category_preferences JSONB DEFAULT '{
    "social": {"push": true, "email": false, "in_app": true},
    "security": {"push": true, "email": true, "sms": true},
    "marketing": {"push": false, "email": true, "sms": false}
  }',
  timezone VARCHAR(50) DEFAULT 'UTC',
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notification_prefs_updated ON notification_preferences(updated_at);
```

### 4.2 Preference Engine
```javascript
class PreferenceEngine {
  async shouldSend(userId, notificationType, channel) {
    const prefs = await this.getPreferences(userId);
    const categoryPrefs = prefs.category_preferences[notificationType.category];
    const channelPrefs = prefs.channel_preferences[channel];
    
    if (!channelPrefs.enabled || !categoryPrefs[channel]) {
      return false;
    }
    
    // Check quiet hours for push notifications
    if (channel === 'push' && this.isQuietHours(prefs)) {
      return false;
    }
    
    // Check frequency limits
    return await this.checkFrequencyLimit(userId, channel, channelPrefs.frequency);
  }
}
```

### 4.3 Default Preferences Strategy
- **Opt-in for marketing**: Comply with regulations (GDPR, CAN-SPAM)
- **Opt-out for social**: Maximize engagement for core features
- **Always-on for security**: Non-negotiable for account safety
- **Smart defaults**: Based on user behavior analysis

## 5. Infrastructure Choices & Scaling

### 5.1 Service Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   API Gateway   │────│ Notification API │────│  Preference DB  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │ Queue Manager   │
                       └────────┬────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
┌───────▼──────┐    ┌───────────▼────┐    ┌─────────────▼──┐
│ Push Handler │    │ Email Handler  │    │ SMS Handler    │
└──────────────┘    └────────────────┘    └────────────────┘
```

### 5.2 Scaling Strategy
**Phase 1 (Months 1-3)**: Single region, vertical scaling
- 2 application servers (4 cores, 16GB RAM each)
- 1 Redis instance (16GB memory)
- 1 PostgreSQL instance (4 cores, 32GB RAM)

**Phase 2 (Months 4-6)**: Horizontal scaling preparation
- Load balancer + 4 application servers
- Redis Cluster (3 nodes)
- PostgreSQL read replicas (2 slaves)

**Capacity Planning**:
- Peak load: 10K notifications/minute
- Storage: 100GB/year for notification history
- Queue depth: 50K messages maximum

### 5.3 Infrastructure Costs (Monthly)
- Compute: $800 (4 application servers)
- Database: $400 (PostgreSQL + replicas)
- Cache/Queue: $300 (Redis cluster)
- External services: $200 (SendGrid, FCM, Twilio)
- **Total: $1,700/month**

## 6. Failure Handling & Reliability

### 6.1 Retry Strategy
```javascript
class RetryHandler {
  async executeWithRetry(operation, maxRetries = 3) {
    const backoffDelays = [1000, 5000, 15000]; // Exponential backoff
    
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        if (this.isRetryable(error) && attempt < maxRetries) {
          await this.delay(backoffDelays[attempt]);
          continue;
        }
        
        await this.handleFailure(error, operation);
        throw error;
      }
    }
  }
  
  isRetryable(error) {
    return error.code === 'TIMEOUT' || 
           error.code === 'RATE_LIMIT' || 
           error.status >= 500;
  }
}
```

### 6.2 Dead Letter Queue
- Failed notifications after 3 retries → DLQ
- Manual review process for DLQ items
- Automatic retry of DLQ items after external service recovery

### 6.3 Circuit Breaker Pattern
```javascript
class CircuitBreaker {
  constructor(threshold = 5, timeout = 60000) {
    this.failureThreshold = threshold;
    this.timeout = timeout;
    this.failureCount = 0;
    this.lastFailureTime = null;
    this.state = 'CLOSED'; // CLOSED, OPEN, HALF_OPEN
  }
  
  async call(operation) {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > this.timeout) {
        this.state = 'HALF_OPEN';
      } else {
        throw new Error('Circuit breaker is OPEN');
      }
    }
    
    try {
      const result = await operation();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }
}
```

### 6.4 Monitoring & Alerting
**Key Metrics**:
- Delivery success rates per channel (target: >95%)
- Average delivery latency (target: <30s for high priority)
- Queue depth and processing rate
- Error rates and failure patterns

**Alerting Thresholds**:
- Queue depth >10K messages
- Delivery success rate <90% over 5 minutes
- Any CRITICAL priority notification delayed >60 seconds

## 7. Implementation Timeline (6 Months)

### Month 1-2: Foundation
- **Week 1-2**: Core notification service and database schema
- **Week 3-4**: Push notification handler with FCM integration
- **Week 5-6**: Basic user preferences and in-app notifications
- **Week 7-8**: Queue system and priority handling

### Month 3-4: Channel Expansion
- **Week 9-10**: Email notification handler with SendGrid
- **Week 11-12**: SMS notification handler (Twilio)
- **Week 13-14**: Batching logic and frequency controls
- **Week 15-16**: Advanced preference management UI

### Month 5-6: Reliability & Scale
- **Week 17-18**: Retry logic and failure handling
- **Week 19-20**: Monitoring, alerting, and analytics
- **Week 21-22**: Load testing and performance optimization
- **Week 23-24**: Documentation, deployment, and handover

## 8. Key Tradeoffs & Decisions

### 8.1 Technology Choices
**PostgreSQL over NoSQL**: 
- **Tradeoff**: Potentially lower write throughput
- **Rationale**: ACID compliance critical for user preferences, team expertise, complex querying needs

**Redis over Apache Kafka**:
- **Tradeoff**: Less sophisticated streaming capabilities
- **Rationale**: Simpler operations, faster implementation, sufficient for current scale

**Managed Services over Self-hosted**:
- **Tradeoff**: Higher costs, less control
- **Rationale**: Faster time-to-market, reduced operational overhead with small team

### 8.2 Feature Scope
**Limited SMS Usage**:
- **Tradeoff**: Reduced reach for critical notifications
- **Rationale**: Cost control and regulatory compliance

**Basic Analytics Initially**:
- **Tradeoff**: Limited insight into user engagement
- **Rationale**: Focus on reliability over advanced features in initial release

### 8.3 Scaling Approach
**Vertical First, Horizontal Later**:
- **Tradeoff**: Potential scaling bottlenecks
- **Rationale**: Faster initial implementation, easier debugging, sufficient for launch scale

## 9. Success Metrics & KPIs

### 9.1 Performance Metrics
- **Delivery Success Rate**: >95% across all channels
- **Latency**: <30s (high priority), <15min (normal priority)
- **Throughput**: 10K notifications/minute peak capacity
- **Uptime**: 99.9% service availability

### 9.2 Business Metrics
- **User Engagement**: 15% improvement in DAU within 3 months
- **Opt-out Rate**: <5% monthly churn on notifications
- **Cost Efficiency**: <$0.02 per notification delivered

### 9.3 Operational Metrics
- **Mean Time to Recovery**: <15 minutes for critical issues
- **False Alert Rate**: <10% of monitoring alerts
- **Team Productivity**: 80% of sprint commitments delivered on time

## Conclusion

This notification system design provides a robust, scalable foundation for a 10M MAU social application while remaining achievable with the given team and timeline constraints. The architecture prioritizes reliability and user experience while making pragmatic technology choices that balance functionality with implementation complexity. The phased approach ensures early delivery of core functionality while building toward long-term scalability requirements.