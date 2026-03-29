# Notification System Design for 10M MAU Social App - SYNTHESIS

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design acknowledges significant limitations requiring future investment while delivering core functionality reliably.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with JWT-based API authentication
- **Device Token Service**: Redis-first token management with PostgreSQL backup for disaster recovery
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS
- **User Preference Service**: Denormalized preference management with write-through caching
- **Template Service**: Content handling with HTML sanitization and XSS protection
- **Analytics Service**: Aggregated delivery tracking with privacy-compliant metrics

### Technology Stack
- **Message Queue**: Amazon SQS with priority-based routing using message attributes
- **Database**: PostgreSQL with read replicas and partitioned tables, Redis Cluster for tokens/cache
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with proper warming plan and deliverability timeline)
- **SMS**: Twilio (with strict cost controls and daily budgets)
- **Infrastructure**: AWS with auto-scaling groups

**Rationale**: Managed services reduce operational complexity while Redis-first storage and denormalized preferences address realistic performance requirements.

## 2. Device Token Management

### 2.1 Redis-First Token Storage with PostgreSQL Backup
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
        
    def store_token(self, user_id, device_id, platform, token):
        # Single source of truth in Redis
        user_key = f"user_tokens:{user_id}"
        token_data = {
            "device_id": device_id,
            "platform": platform,
            "token": token,
            "last_active": int(time.time()),
            "is_valid": True
        }
        
        # Store as hash for efficient partial updates
        self.redis_cluster.hset(user_key, device_id, json.dumps(token_data))
        self.redis_cluster.expire(user_key, 86400 * 90)  # 90-day TTL
        
        # Async backup to PostgreSQL for disaster recovery only
        self.queue_token_backup(user_id, device_id, platform, token)
        
    def cleanup_invalid_tokens(self, failed_tokens):
        # Automatic cleanup based on FCM/APNs feedback
        for user_id, device_id in failed_tokens:
            user_key = f"user_tokens:{user_id}"
            token_data = self.redis_cluster.hget(user_key, device_id)
            if token_data:
                token_info = json.loads(token_data)
                token_info["is_valid"] = False
                self.redis_cluster.hset(user_key, device_id, json.dumps(token_info))
```

**PostgreSQL backup schema (disaster recovery only)**:
```sql
-- Partitioned table for disaster recovery
CREATE TABLE device_token_backup (
    user_id BIGINT,
    device_id VARCHAR(255),
    platform VARCHAR(10),
    token VARCHAR(512),
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY HASH (user_id);

-- Create 16 partitions to distribute load
CREATE TABLE device_token_backup_p0 PARTITION OF device_token_backup FOR VALUES WITH (MODULUS 16, REMAINDER 0);
```

## 3. Message Queue Architecture

### 3.1 Priority Routing with Realistic Capacity Planning
```python
class MessageQueueManager:
    def __init__(self):
        # Single queue with priority routing via message attributes
        self.queue_url = "https://sqs.us-east-1.amazonaws.com/account/notifications"
        self.dlq_url = "https://sqs.us-east-1.amazonaws.com/account/notifications-dlq"
        
        # Calculated based on 10M MAU, 10% daily active, 5 notifications/day avg
        self.expected_daily_volume = 5_000_000  # 5M messages/day
        self.peak_hourly_volume = 750_000       # 15% of daily in peak hour
        self.messages_per_second = 210          # Peak throughput needed
        
    def send_notification(self, notification):
        message_attributes = {
            'priority': {
                'StringValue': str(notification.priority),
                'DataType': 'Number'
            },
            'channel': {
                'StringValue': notification.channel,
                'DataType': 'String'
            }
        }
        
        # Delay low priority messages for batching
        delay_seconds = 0
        if notification.priority == NotificationPriority.LOW:
            delay_seconds = 300  # 5 minute delay for batching
            
        self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(notification.to_dict()),
            MessageAttributes=message_attributes,
            DelaySeconds=delay_seconds
        )
```

## 4. In-App Notifications with Realistic Scaling

### 4.1 WebSocket + Polling Hybrid Strategy
```python
class InAppNotificationService:
    MAX_WEBSOCKET_CONNECTIONS = 100000  # 1% of MAU
    POLLING_INTERVAL = 30  # seconds
    
    def __init__(self):
        self.websocket_manager = WebSocketManager()
        self.current_websocket_count = 0
        
    def establish_connection(self, user_id):
        if self.current_websocket_count < self.MAX_WEBSOCKET_CONNECTIONS:
            return self.websocket_manager.create_connection(user_id)
        else:
            # Fallback to polling for additional users
            return self.setup_polling_fallback(user_id)
            
    def get_user_notifications(self, user_id, since_timestamp=None):
        """RESTful endpoint for polling notifications"""
        notification_key = f"user_notifications:{user_id}"
        
        # Use score as timestamp for time-based queries
        min_score = since_timestamp or 0
        max_score = int(time.time())
        
        notifications = self.redis_cluster.zrangebyscore(
            notification_key, 
            min_score, 
            max_score,
            withscores=True,
            start=0,
            num=50
        )
        
        result = []
        for notification_data, timestamp in notifications:
            notification = json.loads(notification_data)
            notification['timestamp'] = int(timestamp)
            result.append(notification)
            
        return sorted(result, key=lambda x: x['timestamp'], reverse=True)
```

**WebSocket Limitations**:
- Support maximum 100k concurrent WebSocket connections (1% of MAU)
- Aggressive fallback to 30-second polling for additional users
- Clear user communication about real-time limitations

## 5. User Preference Management

### 5.1 Denormalized Preference Storage with Write-Through Cache
```sql
-- Single table with denormalized preferences for performance
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    
    -- Channel-level settings
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    
    -- Category preferences as JSONB for flexibility
    category_preferences JSONB DEFAULT '{
        "messages": {"push": true, "email": true, "sms": false, "in_app": true},
        "social": {"push": true, "email": false, "sms": false, "in_app": true},
        "system": {"push": true, "email": true, "sms": false, "in_app": true}
    }',
    
    -- Quiet hours with timezone
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 5.2 Robust Cache Strategy
```python
class PreferenceService:
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour
        
    def get_user_preferences(self, user_id):
        cache_key = f"user_prefs:{user_id}"
        
        # Try cache first, but system works without it
        try:
            cached = self.redis_cluster.get(cache_key)
            if cached:
                return json.loads(cached)
        except RedisError as e:
            logger.warning(f"Cache read failed for user {user_id}: {e}")
            
        # Always fetch from DB as source of truth
        prefs = self.db.get_user_preferences(user_id)
        if not prefs:
            prefs = self.create_default_preferences(user_id)
            
        # Cache for performance, but don't fail if cache fails
        try:
            self.redis_cluster.setex(cache_key, self.cache_ttl, json.dumps(prefs))
        except RedisError as e:
            logger.warning(f"Cache write failed for user {user_id}: {e}")
            
        return prefs
        
    def can_send_notification(self, user_id, notification_type, channel):
        prefs = self.get_user_preferences(user_id)
        
        # Check channel enabled
        channel_enabled = getattr(prefs, f"{channel}_enabled", True)
        if not channel_enabled:
            return False, "channel_disabled"
            
        # Check category preference
        category = self.get_notification_category(notification_type)
        category_prefs = prefs.category_preferences.get(category, {})
        category_enabled = category_prefs.get(channel, True)
        if not category_enabled:
            return False, "category_disabled"
            
        # Check quiet hours (only for non-critical notifications)
        if notification_type != NotificationPriority.CRITICAL:
            if self.is_quiet_hours(prefs):
                return False, "quiet_hours"
                
        return True, "allowed"
```

## 6. Priority and Batching Logic

### 6.1 Clear Priority Definitions with Batching Rules
```python
class NotificationPriority:
    CRITICAL = 1    # Security alerts, account lockouts - NEVER batched
    HIGH = 2        # Direct messages, mentions - NEVER batched
    MEDIUM = 3      # Likes, comments - 5-minute batches
    LOW = 4         # Weekly digests, recommendations - daily batches

class BatchingManager:
    def __init__(self):
        self.dedup_rules = {
            "like": {"window_minutes": 60, "max_notifications": 1},
            "comment": {"window_minutes": 30, "max_notifications": 3},
            "follow": {"window_minutes": 1440, "max_notifications": 1}  # 24 hours
        }
        
    def get_delivery_strategy(self, priority):
        if priority <= NotificationPriority.HIGH:
            return "immediate"
        elif priority == NotificationPriority.MEDIUM:
            return "5_minute_batch"
        else:
            return "daily_batch"
            
    def create_batch(self, notifications):
        # Group by user and channel, apply deduplication
        batches = defaultdict(list)
        for notif in notifications:
            if self.should_send_notification(notif.user_id, notif.type, notif.content_id):
                key = f"{notif.user_id}_{notif.channel}"
                batches[key].append(notif)
        return batches
```

## 7. Channel-Specific Implementations

### 7.1 Email with Realistic Deliverability Timeline
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

### 7.2 SMS with Strict Cost Controls
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

## 8. Failure Handling & Reliability

### 8.1 Comprehensive Retry Strategy with Circuit Breaker
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
```

## 9. Key Tradeoffs and Limitations

### 9.1 Acknowledged Constraints
- **WebSocket Capacity**: Only 100k concurrent connections (1% of MAU), rest use polling
- **Email Deliverability**: 6-month timeline to reach full volume due to SES warming requirements
- **SMS Budget**: Strict daily limits with push notification fallbacks