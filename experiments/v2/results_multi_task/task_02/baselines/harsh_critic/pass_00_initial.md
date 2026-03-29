# Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we prioritize core functionality over advanced features, using managed services to minimize operational overhead while maintaining reliability and user experience.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator for all notifications
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS
- **User Preference Service**: Manages notification settings and delivery rules
- **Template Service**: Handles notification content and localization
- **Analytics Service**: Tracks delivery metrics and user engagement

### Technology Stack
- **Message Queue**: Amazon SQS with DLQ for reliability
- **Database**: PostgreSQL for preferences/templates, Redis for real-time data
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES
- **SMS**: Twilio
- **Infrastructure**: AWS with auto-scaling groups

**Rationale**: Managed services reduce operational complexity, allowing the small team to focus on business logic rather than infrastructure management.

## 2. Delivery Channels

### 2.1 Push Notifications
```json
{
  "channel": "push",
  "payload": {
    "title": "New message from John",
    "body": "Hey, are you free tonight?",
    "data": {
      "type": "message",
      "conversation_id": "12345",
      "sender_id": "67890"
    },
    "badge_count": 3
  }
}
```

**Implementation**: 
- FCM for Android, APNs for iOS
- Device token management with automatic cleanup of invalid tokens
- Rich notifications with images/actions for engagement

### 2.2 Email
```json
{
  "channel": "email",
  "payload": {
    "template_id": "weekly_digest",
    "recipient": "user@example.com",
    "variables": {
      "user_name": "Alice",
      "unread_count": 15,
      "top_posts": [...]
    }
  }
}
```

**Implementation**:
- Amazon SES with bounce/complaint handling
- HTML templates with fallback text versions
- Unsubscribe links with one-click compliance

### 2.3 In-App Notifications
```json
{
  "channel": "in_app",
  "payload": {
    "id": "notif_12345",
    "type": "friend_request",
    "title": "Sarah wants to connect",
    "timestamp": "2024-01-15T10:30:00Z",
    "read": false,
    "actions": ["accept", "decline"]
  }
}
```

**Implementation**:
- WebSocket connections for real-time delivery
- Fallback to polling for unreliable connections
- Local storage for offline capability

### 2.4 SMS
```json
{
  "channel": "sms",
  "payload": {
    "phone": "+1234567890",
    "message": "Your verification code is 123456",
    "type": "verification"
  }
}
```

**Implementation**:
- Twilio for global coverage
- Rate limiting to prevent abuse
- Cost optimization through channel fallback

## 3. Priority and Batching Logic

### 3.1 Priority Levels
```python
class Priority(Enum):
    CRITICAL = 1    # Security alerts, account issues
    HIGH = 2        # Direct messages, mentions
    MEDIUM = 3      # Likes, comments, friend requests  
    LOW = 4         # Weekly digests, recommendations
```

### 3.2 Batching Strategy

**Real-time Queue** (Priority 1-2):
- Immediate processing
- No batching
- Dedicated workers with higher concurrency

**Batched Queue** (Priority 3-4):
- 5-minute batching windows
- Up to 100 notifications per batch
- Deduplication logic to prevent spam

```python
class BatchProcessor:
    def __init__(self):
        self.batch_size = 100
        self.batch_timeout = 300  # 5 minutes
        
    def should_batch(self, notification):
        return notification.priority >= Priority.MEDIUM
        
    def create_batch(self, notifications):
        # Group by user and channel
        batches = defaultdict(list)
        for notif in notifications:
            key = f"{notif.user_id}_{notif.channel}"
            batches[key].append(notif)
        return batches
```

**Tradeoff**: Batching reduces infrastructure costs and prevents notification fatigue but increases latency for lower-priority notifications. This is acceptable for social app use cases where immediate delivery isn't critical for all notification types.

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
        "messages": {"push": true, "email": true, "sms": false},
        "social": {"push": true, "email": false, "sms": false},
        "system": {"push": true, "email": true, "sms": true}
    }',
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.2 Preference Resolution Logic
```python
class PreferenceResolver:
    def should_deliver(self, user_id, notification_type, channel):
        prefs = self.get_user_preferences(user_id)
        
        # Check channel enabled
        if not prefs.channel_preferences[channel]['enabled']:
            return False
            
        # Check category preferences
        category = self.get_notification_category(notification_type)
        if not prefs.category_preferences[category][channel]:
            return False
            
        # Check quiet hours for push notifications
        if channel == 'push' and self.is_quiet_hours(prefs):
            return False
            
        return True
```

### 4.3 Default Settings Strategy
- **Opt-in for SMS**: High cost, potential spam concerns
- **Opt-out for push/email**: Better engagement, user can disable
- **Always enabled for critical**: Security notifications override preferences

## 5. Infrastructure Design

### 5.1 System Architecture
```
[API Gateway] → [Notification Service] → [SQS Queues] → [Channel Workers]
                         ↓
[User Preferences] ← [PostgreSQL] → [Redis Cache]
                         ↓
[Analytics] ← [CloudWatch/DataDog] → [Monitoring]
```

### 5.2 Scaling Strategy

**Horizontal Scaling**:
- Auto Scaling Groups for notification workers
- SQS for natural load distribution
- Redis cluster for cache scaling

**Capacity Planning**:
- Peak load: 50,000 notifications/minute (assuming 5% DAU engagement)
- Worker capacity: 100 notifications/second per instance
- Required instances: 10-15 during peak hours

### 5.3 Database Design

**PostgreSQL** (Persistent Data):
- User preferences
- Notification templates
- Delivery history (30-day retention)

**Redis** (Cache Layer):
- User preference cache (TTL: 1 hour)
- Rate limiting counters
- Real-time notification queue for WebSocket delivery

```python
# Caching strategy
class PreferenceCache:
    def get_preferences(self, user_id):
        cache_key = f"prefs:{user_id}"
        cached = redis.get(cache_key)
        
        if not cached:
            prefs = db.get_user_preferences(user_id)
            redis.setex(cache_key, 3600, json.dumps(prefs))
            return prefs
            
        return json.loads(cached)
```

## 6. Failure Handling & Reliability

### 6.1 Retry Strategy
```python
class RetryPolicy:
    def __init__(self):
        self.max_attempts = 3
        self.backoff_multiplier = 2
        self.initial_delay = 1  # second
        
    def should_retry(self, attempt, error):
        if attempt >= self.max_attempts:
            return False
            
        # Don't retry client errors
        if isinstance(error, ClientError):
            return False
            
        return True
        
    def get_delay(self, attempt):
        return self.initial_delay * (self.backoff_multiplier ** attempt)
```

### 6.2 Dead Letter Queue Handling
- Failed notifications after 3 attempts go to DLQ
- Daily DLQ processing job for manual investigation
- Alerts for DLQ depth > 1000 messages

### 6.3 Circuit Breaker Pattern
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpenError()
                
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
```

### 6.4 Monitoring & Alerting

**Key Metrics**:
- Delivery rate by channel (target: >98%)
- Processing latency (target: <5s for high priority)
- Queue depth (alert if >10,000 messages)
- Error rate by channel (alert if >2%)

**Alert Thresholds**:
- Critical: System completely down
- High: Delivery rate <95% for 5 minutes
- Medium: Queue depth growing consistently
- Low: Individual channel delivery issues

## 7. Implementation Timeline (6 months)

### Month 1-2: Core Infrastructure
- Set up SQS queues and basic notification service
- Implement user preference storage and management
- Basic push notification delivery (FCM/APNs)

### Month 3-4: Multi-Channel Support
- Email delivery with SES integration
- In-app notifications with WebSocket support
- SMS delivery with Twilio
- Template management system

### Month 5: Advanced Features
- Batching and priority logic
- Analytics and monitoring
- Circuit breakers and retry logic

### Month 6: Polish & Scale Testing
- Performance optimization
- Load testing with simulated traffic
- Documentation and runbooks

## 8. Key Tradeoffs & Rationale

### Managed Services vs Self-Hosted
**Decision**: Use managed services (SQS, SES, Twilio)
**Rationale**: 4-engineer team cannot maintain reliable email/SMS infrastructure. Managed services provide better deliverability and compliance.

### Synchronous vs Asynchronous Processing
**Decision**: Asynchronous with queues
**Rationale**: Prevents API timeouts and allows better resource utilization, though adds complexity.

### SQL vs NoSQL for Preferences
**Decision**: PostgreSQL with JSONB
**Rationale**: Structured preference data with flexibility for custom fields. Team likely has more SQL expertise.

### Real-time vs Batched Processing
**Decision**: Hybrid approach based on priority
**Rationale**: Balances user experience (real-time for important notifications) with cost efficiency (batching for low-priority).

### Push vs Pull for In-App
**Decision**: WebSocket push with polling fallback
**Rationale**: Better user experience with real-time updates, but polling ensures reliability for poor connections.

## 9. Success Metrics

- **Delivery Rate**: >98% successful delivery across all channels
- **Latency**: <5 seconds for high-priority notifications, <5 minutes for batched
- **User Engagement**: Open rates >15% for push, >5% for email
- **System Uptime**: 99.9% availability
- **Cost Efficiency**: <$0.01 per notification delivered

This design provides a robust, scalable notification system that can grow with the application while remaining manageable by a small engineering team.