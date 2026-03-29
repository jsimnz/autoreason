# Notification System Design for 10M MAU Social App - SYNTHESIS

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design acknowledges significant limitations requiring future investment while delivering core functionality reliably.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with authentication
- **Device Token Service**: Dedicated service for managing 20-30M device tokens (partitioned storage)
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS
- **User Preference Service**: Normalized preference management with caching
- **Template Service**: Secure content handling with sanitization
- **Analytics Service**: Accurate delivery tracking with measurable metrics

### Technology Stack
- **Message Queue**: Amazon SQS with separate queues per priority level and DLQ
- **Database**: PostgreSQL with read replicas and partitioned tables, Redis Cluster for tokens/cache
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with proper warming plan and deliverability timeline)
- **SMS**: Twilio (with strict cost controls and daily budgets)
- **Infrastructure**: AWS with auto-scaling groups and WebSocket-specific instances

**Rationale**: Managed services reduce operational complexity while partitioned storage and Redis clustering address realistic scale requirements for device tokens and user preferences.

## 2. Device Token and WebSocket Management at Scale

### 2.1 Device Token Storage at Scale
```sql
-- Partitioned table for 30M+ device tokens
CREATE TABLE device_tokens (
    user_id BIGINT,
    device_id VARCHAR(255),
    platform VARCHAR(10),
    token VARCHAR(512),
    last_active TIMESTAMP,
    is_valid BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY HASH (user_id);

-- Create 16 partitions to distribute load
CREATE TABLE device_tokens_p0 PARTITION OF device_tokens FOR VALUES WITH (MODULUS 16, REMAINDER 0);
-- ... repeat for p1-p15
```

**Redis Cluster Configuration**:
```python
class DeviceTokenManager:
    def __init__(self):
        self.redis_cluster = RedisCluster(
            nodes=[
                {"host": "redis-1", "port": 7000},
                {"host": "redis-2", "port": 7000}, 
                {"host": "redis-3", "port": 7000}
            ]
        )
        
    def store_token(self, user_id, device_id, token):
        key = f"token:{user_id}:{device_id}"
        self.redis_cluster.setex(key, 86400 * 30, token)  # 30-day TTL
        
    def cleanup_invalid_tokens(self):
        # Automatic cleanup of invalid tokens based on FCM/APNs feedback
        invalid_tokens = self.get_failed_delivery_tokens()
        for token in invalid_tokens:
            self.mark_token_invalid(token)
```

### 2.2 Realistic WebSocket Strategy
```python
class WebSocketManager:
    MAX_CONNECTIONS_PER_INSTANCE = 5000  # Conservative estimate
    TARGET_CONCURRENT_USERS = 100000     # 1% of MAU, not 10%
    REQUIRED_INSTANCES = 20               # 100k / 5k per instance
    
    def __init__(self):
        self.connection_limit = 5000
        self.fallback_polling_interval = 30  # seconds
        
    def handle_connection_overflow(self, user_id):
        if self.get_active_connections() >= self.connection_limit:
            # Aggressive fallback to polling for additional users
            return self.setup_polling_fallback(user_id)
        return self.establish_websocket(user_id)
```

**WebSocket Limitations**:
- Support maximum 100k concurrent WebSocket connections (1% of MAU)
- Aggressive fallback to 30-second polling for additional users
- Clear user communication about real-time limitations

## 3. Scalable Database Design

### 3.1 Normalized Preference Schema
```sql
-- Normalized preference storage instead of JSONB
CREATE TABLE user_notification_settings (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    email_frequency VARCHAR(20) DEFAULT 'immediate',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Separate indexed table for category preferences
CREATE TABLE notification_category_settings (
    user_id BIGINT,
    category VARCHAR(50), -- messages, social, system
    channel VARCHAR(20),  -- push, email, sms, in_app
    enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, category, channel)
);

CREATE INDEX idx_category_settings_user ON notification_category_settings(user_id);
```

### 3.2 Redis as Performance Cache, Not Critical Path
```python
class PreferenceService:
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour
        
    def get_user_preferences(self, user_id):
        # Try cache first, but system works without it
        cache_key = f"user_prefs:{user_id}"
        
        try:
            cached = self.redis_cluster.get(cache_key)
            if cached:
                return json.loads(cached)
        except RedisError:
            pass  # Log but continue - cache failure doesn't break system
            
        # Always fetch from DB as source of truth
        prefs = self.db.get_user_preferences(user_id)
        
        # Cache for performance, but don't fail if cache fails
        try:
            self.redis_cluster.setex(cache_key, self.cache_ttl, json.dumps(prefs))
        except RedisError:
            pass  # Log but continue
            
        return prefs
```

### 3.3 Partitioned Delivery History
```sql
-- Monthly partitioned delivery history with automatic cleanup
CREATE TABLE notification_delivery_history (
    id BIGSERIAL,
    user_id BIGINT,
    notification_id UUID,
    channel VARCHAR(20),
    status VARCHAR(20), -- queued, sent_to_provider, delivered, failed
    delivered_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT
) PARTITION BY RANGE (delivered_at);

-- Automated monthly partition creation and cleanup
CREATE TABLE delivery_history_2024_01 PARTITION OF notification_delivery_history 
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

## 4. Channel-Specific Implementations

### 4.1 Push Notifications with Token Management
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
- FCM for Android, APNs for iOS with certificate rotation monitoring
- Partitioned device token storage with automatic invalid token cleanup
- Rich notifications with images/actions for engagement

### 4.2 Email with Deliverability Timeline
```python
class EmailDeliverabilityManager:
    def __init__(self):
        # SES sending limits start low and require gradual increase
        self.current_daily_limit = 200
        self.current_rate_limit = 1  # emails per second
        self.target_daily_limit = 100000  # Will take months to reach
        
    def can_send_email(self):
        daily_sent = self.get_daily_email_count()
        return daily_sent < self.current_daily_limit
```

**Realistic Email Timeline**:
- Month 1: 200 emails/day (testing only)
- Month 2: 1,000 emails/day (limited user testing)  
- Month 3: 10,000 emails/day (gradual rollout)
- Month 4-6: Scale to 100k+ emails/day through SES reputation building

### 4.3 SMS with Cost Controls
```python
class SMSCostController:
    def __init__(self):
        self.daily_budget = 1000  # $1000 daily limit
        self.user_daily_limit = 3  # Max 3 SMS per user per day
        self.cost_per_sms = 0.05  # Conservative estimate
        
    def send_with_fallback(self, user_id, message):
        can_send, reason = self.can_send_sms(user_id)
        if not can_send:
            # Fallback to push notification
            return self.send_push_notification(user_id, message)
        return self.send_sms(user_id, message)
```

### 4.4 In-App with Realistic Capacity
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
- WebSocket connections for up to 100k concurrent users (1% of MAU)
- 30-second polling fallback for additional users
- Local storage for offline capability

## 5. Priority and Batching Logic

### 5.1 Clear Priority Definitions
```python
class NotificationPriority:
    CRITICAL = 1    # Security alerts, account lockouts - NEVER batched
    HIGH = 2        # Direct messages, mentions - NEVER batched
    MEDIUM = 3      # Likes, comments - 5-minute batches
    LOW = 4         # Weekly digests, recommendations - daily batches

class BatchingRules:
    def get_delivery_strategy(self, priority):
        if priority <= NotificationPriority.HIGH:
            return "immediate"
        elif priority == NotificationPriority.MEDIUM:
            return "5_minute_batch"
        else:
            return "daily_batch"
```

### 5.2 Explicit Deduplication Rules
```python
class DeduplicationManager:
    def __init__(self):
        self.dedup_rules = {
            "like": {"window_minutes": 60, "max_notifications": 1},
            "comment": {"window_minutes": 30, "max_notifications": 3},
            "follow": {"window_minutes": 1440, "max_notifications": 1}  # 24 hours
        }
        
    def create_batch(self, notifications):
        # Group by user and channel, apply deduplication
        batches = defaultdict(list)
        for notif in notifications:
            if self.should_send_notification(notif.user_id, notif.type, notif.content_id):
                key = f"{notif.user_id}_{notif.channel}"
                batches[key].append(notif)
        return batches
```

**Tradeoff**: Batching reduces infrastructure costs and prevents notification fatigue but increases latency. Clear rules define which notifications get batched based on user impact.

## 6. User Preference Management

### 6.1 Simplified Preference Resolution
```python
class PreferenceResolver:
    def can_send_to_channel(self, user_id, notification_type, channel):
        prefs = self.get_user_preferences(user_id)
        
        # Channel completely disabled = no notifications
        if not getattr(prefs, f"{channel}_enabled"):
            return False
            
        # Check category-specific preference  
        category = self.get_notification_category(notification_type)
        category_pref = self.get_category_preference(user_id, category, channel)
        
        return category_pref.enabled if category_pref else True
        
    def apply_quiet_hours_rule(self, user_id, notification):
        # Critical notifications ignore quiet hours
        if notification.priority == NotificationPriority.CRITICAL:
            return True
            
        return not self.is_quiet_hours(user_id)
```

### 6.2 Timezone Handling
```python
class TimezoneManager:
    def is_quiet_hours(self, user_id):
        user_prefs = self.get_user_preferences(user_id)
        user_timezone = pytz.timezone(user_prefs.timezone)
        user_time = datetime.now(user_timezone).time()
        
        start = user_prefs.quiet_hours_start
        end = user_prefs.quiet_hours_end
        
        # Handle overnight quiet hours (e.g., 22:00 to 08:00)
        if start > end:
            return user_time >= start or user_time <= end
        else:
            return start <= user_time <= end
```

### 6.3 Default Settings Strategy
- **Opt-in for SMS**: High cost, potential spam concerns
- **Opt-out for push/email**: Better engagement, user can disable
- **Always enabled for critical**: Security notifications override preferences
- **Clear hierarchy**: Channel-level settings override category-level settings

## 7. Failure Handling & Reliability

### 7.1 Comprehensive Retry Strategy
```python
class RetryPolicy:
    def __init__(self):
        self.max_attempts = 3
        self.backoff_multiplier = 2
        self.initial_delay = 1  # second
        
    def should_retry(self, attempt, error):
        if attempt >= self.max_attempts:
            return False
            
        # Don't retry client errors (4xx)
        if isinstance(error, ClientError):
            return False
            
        return True
        
    def get_delay(self, attempt):
        return self.initial_delay * (self.backoff_multiplier ** attempt)
```

### 7.2 Failed Delivery Recovery
```python
class FailedDeliveryHandler:
    def handle_permanent_failure(self, notification, error):
        if notification.priority == NotificationPriority.CRITICAL:
            # Critical notifications require manual intervention
            self.escalate_to_support_team(notification, error)
            
            # Try alternative channels for critical notifications
            if notification.channel == "push":
                self.retry_via_email(notification)
            elif notification.channel == "email":
                self.retry_via_sms(notification)
                
        else:
            # Non-critical failures are logged but not retried
            self.log_failure(notification, error)
            self.update_user_delivery_stats(notification.user_id, "failed")
```

### 7.3 Circuit Breaker Pattern
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

## 8. Monitoring & Analytics

### 8.1 Measurable Delivery Metrics
```python
class DeliveryMetrics:
    def track_notification_attempt(self, notification_id, channel, status):
        # Track at multiple stages for accurate measurement
        stages = {
            "queued": "Notification added to queue",
            "processed": "Picked up by