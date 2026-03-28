# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system for a social app with 10 million monthly active users, designed to be implemented by 4 backend engineers over 6 months. The system prioritizes reliability, user experience, and cost-effectiveness while maintaining operational simplicity given team constraints.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator for all notifications
- **Channel Handlers**: Specialized handlers for each delivery channel
- **Queue System**: Apache Kafka for reliable message processing
- **User Preference Service**: Manages user notification settings
- **Template Engine**: Dynamic content generation
- **Analytics & Monitoring**: Delivery tracking and system health

### Technology Stack
- **Primary Database**: PostgreSQL for user preferences and notification logs
- **Message Queue**: Apache Kafka (managed service like Confluent Cloud)
- **Cache**: Redis for user preferences and rate limiting
- **Push Notifications**: Firebase Cloud Messaging (FCM) for Android/iOS
- **Email**: SendGrid for transactional emails
- **SMS**: Twilio for SMS delivery
- **Infrastructure**: AWS with managed services

## 2. Delivery Channels

### 2.1 Push Notifications (Primary Channel)
**Implementation**: Firebase Cloud Messaging
- **Rationale**: Single SDK for iOS/Android, reliable delivery, free tier supports our scale
- **Message Types**: 
  - Immediate: Friend requests, mentions, direct messages
  - Batched: Weekly digest, trending content
- **Payload Structure**:
```json
{
  "notification": {
    "title": "{{user_name}} mentioned you",
    "body": "Check out what they said!",
    "click_action": "OPEN_POST",
    "icon": "notification_icon"
  },
  "data": {
    "post_id": "12345",
    "user_id": "67890",
    "notification_type": "mention"
  }
}
```

### 2.2 Email Notifications (Secondary Channel)
**Implementation**: SendGrid
- **Use Cases**: 
  - Weekly digest (batched)
  - Security alerts (immediate)
  - Re-engagement campaigns (scheduled)
- **Template Categories**: Transactional, marketing, security
- **Daily Limits**: 100,000 emails/day (SendGrid Essentials plan)

### 2.3 In-App Notifications (Real-time)
**Implementation**: WebSocket connections with fallback to HTTP polling
- **Storage**: PostgreSQL with 30-day retention
- **Real-time Updates**: Socket.io for active users
- **Fallback**: HTTP polling every 30 seconds for WebSocket failures

### 2.4 SMS (Critical Only)
**Implementation**: Twilio
- **Strict Use Cases**: 
  - Security alerts (login from new device)
  - Payment confirmations
  - Account recovery
- **Cost Consideration**: ~$0.0075/SMS, budgeted for <1% of user base

## 3. Priority and Batching Logic

### 3.1 Priority Levels
```
CRITICAL (0-5 min delay):
- Security alerts
- Payment notifications
- Direct messages from close friends

HIGH (5-15 min delay):
- Friend requests
- Comments on user's posts
- Mentions

MEDIUM (15-60 min delay):
- Likes on posts
- New follower notifications
- Group activity updates

LOW (1-24 hour delay):
- Trending content
- Suggested friends
- Weekly digests
```

### 3.2 Batching Strategy
**Time-based Batching**:
- LOW priority: Batch every 4 hours
- MEDIUM priority: Batch every 30 minutes
- HIGH priority: Batch every 5 minutes
- CRITICAL priority: No batching

**User-based Batching**:
- Combine similar notification types (e.g., "5 people liked your post")
- Maximum 3 notifications per batch to avoid spam
- Respect user quiet hours (default: 10 PM - 8 AM local time)

### 3.3 Implementation
```python
class NotificationBatcher:
    def should_batch(self, notification):
        return (
            notification.priority in ['LOW', 'MEDIUM'] and
            not self.in_quiet_hours(notification.user_id) and
            self.get_recent_count(notification.user_id) < 3
        )
    
    def create_batch(self, notifications):
        grouped = self.group_by_type(notifications)
        return self.generate_batch_message(grouped)
```

## 4. User Preference Management

### 4.1 Preference Schema
```sql
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME DEFAULT '22:00:00',
    quiet_hours_end TIME DEFAULT '08:00:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    preferences JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- JSONB structure for granular preferences
{
  "mentions": {"push": true, "email": false, "sms": false},
  "friend_requests": {"push": true, "email": true, "sms": false},
  "likes": {"push": false, "email": false, "sms": false},
  "security": {"push": true, "email": true, "sms": true}
}
```

### 4.2 Default Preferences Strategy
- **Opt-in for SMS**: Disabled by default due to cost
- **Opt-out for push/email**: Enabled by default with easy unsubscribe
- **Smart defaults**: High-value notifications enabled, low-value disabled
- **Progressive disclosure**: Show preference options after user engagement

### 4.3 Preference API
```python
class PreferenceService:
    def get_user_preferences(self, user_id):
        # Check Redis cache first, fallback to DB
        return self.cache.get(f"prefs:{user_id}") or self.db.get_preferences(user_id)
    
    def should_send_notification(self, user_id, notification_type, channel):
        prefs = self.get_user_preferences(user_id)
        return prefs.get(notification_type, {}).get(channel, False)
```

## 5. Infrastructure Choices

### 5.1 Message Queue: Apache Kafka
**Rationale**: 
- Handles 10M+ messages/day with horizontal scaling
- Built-in partitioning for parallel processing
- Message retention for replay capability
- Managed service reduces operational overhead

**Topic Structure**:
```
notifications.critical    (1 partition, 1-hour retention)
notifications.high        (3 partitions, 24-hour retention)
notifications.medium      (5 partitions, 24-hour retention)
notifications.low         (10 partitions, 7-day retention)
```

### 5.2 Database: PostgreSQL + Redis
**PostgreSQL** (Primary):
- User preferences (JSONB for flexibility)
- Notification history and analytics
- Audit logs

**Redis** (Cache):
- User preferences (30-minute TTL)
- Rate limiting counters
- Real-time notification queues for in-app

### 5.3 Deployment Architecture
```
Load Balancer (ALB)
├── Notification API (3 instances, auto-scaling)
├── Channel Workers
│   ├── Push Worker (2 instances)
│   ├── Email Worker (2 instances)
│   ├── SMS Worker (1 instance)
│   └── In-App Worker (2 instances)
└── WebSocket Service (2 instances)
```

### 5.4 Cost Estimates (Monthly)
- **Kafka (Confluent Cloud)**: ~$500
- **SendGrid (100K emails/day)**: ~$90
- **Twilio (10K SMS/month)**: ~$75
- **Firebase**: Free tier sufficient
- **AWS Infrastructure**: ~$800
- **Total**: ~$1,465/month

## 6. Failure Handling & Reliability

### 6.1 Retry Strategy
```python
class RetryHandler:
    RETRY_DELAYS = [30, 300, 1800, 3600]  # 30s, 5m, 30m, 1h
    MAX_RETRIES = 4
    
    def handle_failure(self, notification, attempt):
        if attempt < self.MAX_RETRIES:
            delay = self.RETRY_DELAYS[attempt]
            self.schedule_retry(notification, delay)
        else:
            self.send_to_dlq(notification)
```

### 6.2 Dead Letter Queue (DLQ)
- Failed notifications after max retries go to DLQ
- Manual investigation and reprocessing capability
- Alert system for DLQ threshold breaches (>100 messages/hour)

### 6.3 Circuit Breaker Pattern
```python
class ChannelCircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
```

### 6.4 Monitoring & Alerting
**Key Metrics**:
- Delivery success rate per channel (target: >95%)
- Average delivery time per priority level
- Queue depth and processing lag
- Error rates and retry counts

**Alerts**:
- Delivery success rate < 90% for any channel
- Queue lag > 10 minutes for critical notifications
- DLQ message count > 100/hour
- Circuit breaker state changes

### 6.5 Graceful Degradation
1. **Channel Failures**: Fall back to alternative channels based on user preferences
2. **Database Failures**: Use cached preferences, default to critical notifications only
3. **Queue Failures**: Direct synchronous delivery for critical notifications
4. **Template Failures**: Use fallback static templates

## 7. Implementation Timeline (6 Months)

### Month 1-2: Foundation
- Set up Kafka infrastructure and basic message flow
- Implement user preference service and API
- Create notification service core with priority handling
- Develop push notification channel (FCM integration)

### Month 3-4: Channel Implementation
- Implement email channel with SendGrid
- Build in-app notification system with WebSocket
- Add SMS channel with strict controls
- Create batching logic and user preference filtering

### Month 5: Advanced Features
- Implement retry mechanisms and circuit breakers
- Build analytics dashboard and monitoring
- Add template engine for dynamic content
- Performance optimization and load testing

### Month 6: Production & Polish
- Security audit and compliance review
- Production deployment with gradual rollout
- Documentation and runbook creation
- Team training and knowledge transfer

## 8. Key Tradeoffs and Rationale

### 8.1 Managed Services vs. Self-Hosted
**Decision**: Use managed services (Confluent Cloud, SendGrid, Twilio)
**Rationale**: With only 4 engineers and 6 months, operational complexity must be minimized. Managed services provide reliability and scalability while allowing the team to focus on business logic.

### 8.2 Real-time vs. Near Real-time
**Decision**: Near real-time with batching for most notifications
**Rationale**: True real-time is expensive and complex. Batching reduces costs and user notification fatigue while maintaining acceptable user experience for a social app.

### 8.3 Database Choice
**Decision**: PostgreSQL + Redis hybrid approach
**Rationale**: PostgreSQL provides ACID compliance for critical preference data and supports JSONB for flexibility. Redis handles high-frequency reads and rate limiting efficiently.

### 8.4 Channel Prioritization
**Decision**: Push > In-App > Email > SMS
**Rationale**: Push notifications have highest engagement and lowest cost. SMS is expensive and intrusive, reserved for critical use cases only.

## 9. Success Metrics

### 9.1 Technical Metrics
- **System Availability**: 99.9% uptime
- **Delivery Success Rate**: >95% for all channels
- **Latency**: <5 minutes for critical, <1 hour for others
- **Cost per Notification**: <$0.001

### 9.2 Business Metrics
- **User Engagement**: 15%+ increase in DAU
- **Notification CTR**: >8% for push, >3% for email
- **Opt-out Rate**: <5% monthly churn
- **User Satisfaction**: >4.0/5.0 in app store reviews

This notification system design balances scalability, reliability, and development velocity while staying within the constraints of team size and timeline. The focus on managed services and proven technologies ensures successful delivery within the 6-month timeframe.