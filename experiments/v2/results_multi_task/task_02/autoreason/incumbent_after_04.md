# Notification System Design for 10M MAU Social App - REVISED

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design acknowledges significant limitations requiring future investment while delivering core functionality reliably.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with JWT-based API authentication
- **Device Token Service**: Centralized token management with Redis-only storage
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS
- **User Preference Service**: Denormalized preference management with write-through caching
- **Template Service**: Content handling with HTML sanitization and XSS protection
- **Analytics Service**: Aggregated delivery tracking with privacy-compliant metrics

### Technology Stack
- **Message Queue**: Amazon SQS with priority-based routing using message attributes
- **Database**: PostgreSQL with read replicas, Redis Cluster for tokens/cache/shared state
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with 12-month deliverability plan)
- **SMS**: Twilio (with distributed cost controls)
- **Infrastructure**: AWS with auto-scaling groups

**Rationale**: Managed services reduce operational complexity while Redis-first storage and denormalized preferences address realistic performance requirements.

## 2. Device Token Management (Fixes Redis/PostgreSQL redundancy and partitioning problems)

### 2.1 Redis-Only Token Storage
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
        
    def get_user_tokens(self, user_id):
        user_key = f"user_tokens:{user_id}"
        token_data = self.redis_cluster.hgetall(user_key)
        
        valid_tokens = []
        for device_id, data in token_data.items():
            token_info = json.loads(data)
            if token_info.get("is_valid", True):
                valid_tokens.append(token_info)
                
        return valid_tokens
        
    def cleanup_invalid_tokens(self, failed_tokens):
        # Mark tokens invalid based on FCM/APNs feedback
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
-- Simple backup table, not used for queries
CREATE TABLE device_token_backup (
    user_id BIGINT,
    device_id VARCHAR(255),
    platform VARCHAR(10),
    token VARCHAR(512),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, device_id)
);
```

## 3. Message Queue Architecture (Fixes SQS scaling and queue sizing problems)

### 3.1 Priority Routing with Message Attributes
```python
class MessageQueueManager:
    def __init__(self):
        # Single queue with priority routing via message attributes
        self.queue_url = "https://sqs.us-east-1.amazonaws.com/account/notifications"
        self.dlq_url = "https://sqs.us-east-1.amazonaws.com/account/notifications-dlq"
        
        # Calculated based on 10M MAU, 10% daily active, 5 notifications/day avg
        self.expected_daily_volume = 5_000_000  # 5M messages/day
        self.peak_hourly_volume = 500_000       # 10% of daily in peak hour
        self.messages_per_second = 140          # Peak throughput needed
        
    def send_notification(self, notification):
        message_attributes = {
            'priority': {
                'StringValue': str(notification.priority),
                'DataType': 'Number'
            },
            'channel': {
                'StringValue': notification.channel,
                'DataType': 'String'
            },
            'user_id': {
                'StringValue': str(notification.user_id),
                'DataType': 'Number'
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
        
    def process_messages_by_priority(self):
        # Receive messages with priority filtering
        while True:
            # Process high priority first
            high_priority_messages = self.receive_messages_with_filter(
                'priority', ['1', '2']
            )
            if high_priority_messages:
                self.process_immediately(high_priority_messages)
                continue
                
            # Then medium/low priority
            other_messages = self.receive_messages_with_filter(
                'priority', ['3', '4']
            )
            if other_messages:
                self.process_with_batching(other_messages)
            else:
                time.sleep(1)  # No messages, brief pause
```

### 3.2 Queue Capacity Planning
```python
class QueueCapacityPlanner:
    def __init__(self):
        # Based on realistic usage patterns
        self.daily_active_users = 1_000_000  # 10% of 10M MAU
        self.avg_notifications_per_user = 5
        self.peak_hour_multiplier = 0.15     # 15% of daily volume in peak hour
        
        # SQS limits and costs
        self.sqs_message_limit = 120_000     # messages per second per queue
        self.message_retention_days = 14     # SQS maximum
        
    def calculate_requirements(self):
        daily_messages = self.daily_active_users * self.avg_notifications_per_user
        peak_hour_messages = daily_messages * self.peak_hour_multiplier
        peak_messages_per_second = peak_hour_messages / 3600
        
        return {
            "daily_volume": daily_messages,
            "peak_hour_volume": peak_hour_messages,
            "peak_messages_per_second": peak_messages_per_second,
            "within_sqs_limits": peak_messages_per_second < self.sqs_message_limit,
            "estimated_monthly_cost": daily_messages * 30 * 0.0000004  # $0.40 per million
        }
```

## 4. In-App Notifications Without WebSockets (Fixes WebSocket scaling and consistency problems)

### 4.1 Polling-Only Strategy
```python
class InAppNotificationService:
    def __init__(self):
        # No WebSockets - polling only for MVP
        self.polling_interval = 30  # seconds
        self.max_notifications_per_poll = 50
        
    def get_user_notifications(self, user_id, since_timestamp=None):
        """
        RESTful endpoint for polling notifications
        """
        # Get unread notifications from Redis sorted set
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
            num=self.max_notifications_per_poll
        )
        
        result = []
        for notification_data, timestamp in notifications:
            notification = json.loads(notification_data)
            notification['timestamp'] = int(timestamp)
            result.append(notification)
            
        return sorted(result, key=lambda x: x['timestamp'], reverse=True)
        
    def store_notification(self, user_id, notification):
        """
        Store notification for in-app delivery
        """
        notification_key = f"user_notifications:{user_id}"
        timestamp = int(time.time())
        
        # Store with timestamp as score for efficient time-based queries
        self.redis_cluster.zadd(
            notification_key,
            {json.dumps(notification): timestamp}
        )
        
        # Keep only last 100 notifications per user
        self.redis_cluster.zremrangebyrank(notification_key, 0, -101)
        
        # Set TTL to prevent indefinite growth
        self.redis_cluster.expire(notification_key, 86400 * 7)  # 7 days
```

### 4.2 Client-Side Implementation
```javascript
class InAppNotificationClient {
    constructor(apiBaseUrl, authToken) {
        this.apiBaseUrl = apiBaseUrl;
        this.authToken = authToken;
        this.pollingInterval = 30000; // 30 seconds
        this.lastTimestamp = 0;
        this.isPolling = false;
    }
    
    startPolling() {
        if (this.isPolling) return;
        this.isPolling = true;
        this.poll();
    }
    
    async poll() {
        try {
            const response = await fetch(
                `${this.apiBaseUrl}/notifications?since=${this.lastTimestamp}`,
                {
                    headers: {
                        'Authorization': `Bearer ${this.authToken}`
                    }
                }
            );
            
            const notifications = await response.json();
            
            if (notifications.length > 0) {
                this.handleNewNotifications(notifications);
                this.lastTimestamp = Math.max(...notifications.map(n => n.timestamp));
            }
            
        } catch (error) {
            console.error('Notification polling error:', error);
        }
        
        if (this.isPolling) {
            setTimeout(() => this.poll(), this.pollingInterval);
        }
    }
    
    handleNewNotifications(notifications) {
        // Update UI with new notifications
        notifications.forEach(notification => {
            this.displayNotification(notification);
        });
    }
}
```

## 5. User Preference Management (Fixes database call complexity and cache consistency problems)

### 5.1 Denormalized Preference Storage
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
    
    -- Quiet hours
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Email frequency
    email_frequency VARCHAR(20) DEFAULT 'immediate',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_prefs_user_id ON user_notification_preferences(user_id);
```

### 5.2 Write-Through Cache Strategy
```python
class PreferenceService:
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour
        
    def get_user_preferences(self, user_id):
        cache_key = f"user_prefs:{user_id}"
        
        # Try cache first
        try:
            cached = self.redis_cluster.get(cache_key)
            if cached:
                return json.loads(cached)
        except RedisError as e:
            logger.warning(f"Cache read failed for user {user_id}: {e}")
            
        # Fetch from database
        prefs = self.db.get_user_preferences(user_id)
        if not prefs:
            prefs = self.create_default_preferences(user_id)
            
        # Write to cache (write-through)
        try:
            self.redis_cluster.setex(cache_key, self.cache_ttl, json.dumps(prefs))
        except RedisError as e:
            logger.warning(f"Cache write failed for user {user_id}: {e}")
            
        return prefs
        
    def update_user_preferences(self, user_id, updates):
        # Update database first
        updated_prefs = self.db.update_user_preferences(user_id, updates)
        
        # Invalidate cache to ensure consistency
        cache_key = f"user_prefs:{user_id}"
        try:
            self.redis_cluster.delete(cache_key)
        except RedisError as e:
            logger.warning(f"Cache invalidation failed for user {user_id}: {e}")
            
        return updated_prefs
        
    def can_send_notification(self, user_id, notification_type, channel):
        prefs = self.get_user_preferences(user_id)
        
        # Single database call gets all needed preference data
        
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
            if self.is_quiet_hours_cached(prefs):
                return False, "quiet_hours"
                
        return True, "allowed"
        
    def is_quiet_hours_cached(self, prefs):
        """
        Pre-calculate quiet hours to avoid expensive timezone operations
        """
        # Use cached timezone calculation
        user_timezone = pytz.timezone(prefs.timezone)
        user_time = datetime.now(user_timezone).time()
        
        start = prefs.quiet_hours_start
        end = prefs.quiet_hours_end
        
        if start > end:  # Overnight quiet hours
            return user_time >= start or user_time <= end
        else:
            return start <= user_time <= end