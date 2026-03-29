# Notification System Design for 10M MAU Social App - SYNTHESIS

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design acknowledges significant limitations requiring future investment while delivering core functionality reliably.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with JWT-based API authentication and internal service authentication
- **Device Token Service**: Distributed token management with consistent hashing
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS
- **User Preference Service**: Denormalized preference management with write-through caching
- **Template Service**: Content handling with DOMPurify-based HTML sanitization
- **Analytics Service**: Aggregated delivery tracking with GDPR-compliant data collection

### Technology Stack
- **Message Queue**: Amazon SQS with separate priority queues
- **Database**: PostgreSQL with read replicas, Redis Cluster for tokens/cache/shared state
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with 12-month deliverability plan)
- **SMS**: Twilio (with rate limiting and budget enforcement)
- **Infrastructure**: AWS with auto-scaling groups

**Rationale**: Managed services reduce operational complexity while distributed storage and separate priority queues address realistic performance requirements.

## 2. Device Token Management

### 2.1 Distributed Token Storage with Consistent Hashing
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
        
    def _get_token_key(self, user_id, device_id):
        # Use device_id in key to distribute across partitions
        return f"token:{device_id}:{user_id}"
        
    def _get_user_devices_key(self, user_id):
        # Separate set to track user's devices
        return f"user_devices:{user_id}"
        
    def store_token(self, user_id, device_id, platform, token):
        token_key = self._get_token_key(user_id, device_id)
        user_devices_key = self._get_user_devices_key(user_id)
        
        token_data = {
            "user_id": user_id,
            "device_id": device_id,
            "platform": platform,
            "token": token,
            "created_at": int(time.time()),
            "is_valid": True
        }
        
        # Store individual token with its own TTL
        self.redis_cluster.setex(token_key, 86400 * 90, json.dumps(token_data))
        
        # Track device in user's device set
        self.redis_cluster.sadd(user_devices_key, device_id)
        self.redis_cluster.expire(user_devices_key, 86400 * 90)
        
        # Async backup to PostgreSQL for disaster recovery only
        self.queue_token_backup(user_id, device_id, platform, token)
        
    def get_user_tokens(self, user_id):
        user_devices_key = self._get_user_devices_key(user_id)
        device_ids = self.redis_cluster.smembers(user_devices_key)
        
        valid_tokens = []
        invalid_devices = []
        
        for device_id in device_ids:
            token_key = self._get_token_key(user_id, device_id)
            token_data = self.redis_cluster.get(token_key)
            
            if token_data:
                token_info = json.loads(token_data)
                if token_info.get("is_valid", True):
                    valid_tokens.append(token_info)
                else:
                    invalid_devices.append(device_id)
            else:
                # Token expired or missing
                invalid_devices.append(device_id)
                
        # Clean up invalid devices from user set
        if invalid_devices:
            self.redis_cluster.srem(user_devices_key, *invalid_devices)
                
        return valid_tokens
        
    def cleanup_invalid_tokens(self, failed_tokens):
        # Properly remove invalid tokens instead of just marking them
        for user_id, device_id in failed_tokens:
            token_key = self._get_token_key(user_id, device_id)
            user_devices_key = self._get_user_devices_key(user_id)
            
            # Remove token completely
            self.redis_cluster.delete(token_key)
            self.redis_cluster.srem(user_devices_key, device_id)
            
            # Remove from PostgreSQL backup
            self.remove_token_from_postgres(user_id, device_id)
```

### 2.2 PostgreSQL Backup (Disaster Recovery Only)
```sql
-- Simple backup table, not used for queries
CREATE TABLE device_token_backup (
    user_id BIGINT,
    device_id VARCHAR(255),
    platform VARCHAR(10),
    token VARCHAR(512),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, device_id)
);

CREATE INDEX idx_device_tokens_created ON device_token_backup(created_at);
```

## 3. Message Queue Architecture

### 3.1 Separate Priority Queues with Realistic Volume Planning
```python
class MessageQueueManager:
    def __init__(self):
        # Separate queues for true priority handling
        self.queues = {
            'critical': "https://sqs.us-east-1.amazonaws.com/account/notifications-critical",
            'high': "https://sqs.us-east-1.amazonaws.com/account/notifications-high", 
            'medium': "https://sqs.us-east-1.amazonaws.com/account/notifications-medium",
            'low': "https://sqs.us-east-1.amazonaws.com/account/notifications-low"
        }
        
        # Realistic volume calculations accounting for viral spikes
        self.base_daily_volume = 5_000_000      # 5M base messages/day
        self.viral_spike_multiplier = 20        # 20x spike for viral content
        self.max_hourly_volume = 20_000_000     # 20M messages in worst case hour
        self.max_messages_per_second = 5556     # Worst case throughput needed
        
    def send_notification(self, notification):
        priority_queue = self.queues.get(notification.priority, self.queues['medium'])
        
        message_body = {
            'user_id': notification.user_id,
            'notification_id': notification.id,
            'channel': notification.channel,
            'content': notification.content,
            'timestamp': int(time.time())
        }
        
        # Delay low priority messages for batching
        delay_seconds = 0
        if notification.priority == NotificationPriority.LOW:
            delay_seconds = 300  # 5 minute delay for batching
        
        self.sqs.send_message(
            QueueUrl=priority_queue,
            MessageBody=json.dumps(message_body),
            DelaySeconds=delay_seconds
        )
        
    def process_messages_with_priority(self):
        # Process queues in strict priority order
        queue_order = ['critical', 'high', 'medium', 'low']
        
        while True:
            processed_any = False
            
            for priority in queue_order:
                queue_url = self.queues[priority]
                messages = self.sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=1  # Short polling for higher priority
                )
                
                if messages.get('Messages'):
                    self.process_message_batch(messages['Messages'], priority)
                    processed_any = True
                    
                    # Only process lower priority if high priority queue is empty
                    if priority in ['critical', 'high']:
                        break
                        
            if not processed_any:
                time.sleep(1)  # Brief pause when all queues empty
```

### 3.2 Realistic Capacity Planning with Viral Content
```python
class QueueCapacityPlanner:
    def __init__(self):
        # Realistic social media usage patterns
        self.daily_active_users = 1_000_000
        self.avg_notifications_per_user = 5
        self.viral_content_probability = 0.01  # 1% chance of viral content daily
        self.viral_spike_multiplier = 20
        
    def calculate_requirements(self):
        base_daily_messages = self.daily_active_users * self.avg_notifications_per_user
        
        # Account for viral spikes
        viral_daily_messages = base_daily_messages * self.viral_spike_multiplier
        worst_case_hourly = viral_daily_messages * 0.5  # 50% in one hour during viral event
        
        # Add safety margin for multiple viral events
        peak_messages_per_second = (worst_case_hourly / 3600) * 1.5
        
        # Check against SQS limits per queue
        queues_needed = math.ceil(peak_messages_per_second / 3000)  # 3K/sec per queue safely
        
        return {
            "base_daily_volume": base_daily_messages,
            "viral_daily_volume": viral_daily_messages,
            "worst_case_hourly": worst_case_hourly,
            "peak_messages_per_second": peak_messages_per_second,
            "queues_needed_per_priority": queues_needed,
            "estimated_monthly_cost": viral_daily_messages * 30 * 0.0000004
        }
```

## 4. In-App Notifications with Proper Data Integrity

### 4.1 UUID-Based Storage with Device-Specific Delivery Tracking
```python
class InAppNotificationService:
    def __init__(self):
        self.polling_interval = 30
        self.max_notifications_per_poll = 50
        
    def store_notification(self, user_id, notification):
        # Use UUID to prevent timestamp collisions
        notification_id = str(uuid.uuid4())
        notification_key = f"user_notifications:{user_id}"
        
        timestamp = int(time.time() * 1000)  # Millisecond precision
        
        notification_data = {
            'id': notification_id,
            'content': notification.content,
            'type': notification.type,
            'created_at': timestamp,
            'read': False
        }
        
        # Store notification with unique ID as member
        pipe = self.redis_cluster.pipeline()
        pipe.zadd(notification_key, {notification_id: timestamp})
        pipe.hset(f"notification_data:{notification_id}", mapping=notification_data)
        pipe.expire(f"notification_data:{notification_id}", 86400 * 7)
        
        # Keep only last 100 notifications
        pipe.zremrangebyrank(notification_key, 0, -101)
        pipe.expire(notification_key, 86400 * 7)
        pipe.execute()
        
        return notification_id
        
    def get_user_notifications(self, user_id, since_timestamp=None, device_id=None):
        # Track delivery per device to prevent duplicates
        notification_key = f"user_notifications:{user_id}"
        delivery_key = f"delivered:{user_id}:{device_id}" if device_id else None
        
        min_score = since_timestamp or 0
        max_score = int(time.time() * 1000)
        
        # Get notification IDs in time range
        notification_ids = self.redis_cluster.zrangebyscore(
            notification_key,
            min_score,
            max_score,
            withscores=True,
            start=0,
            num=self.max_notifications_per_poll
        )
        
        if not notification_ids:
            return []
            
        # Get delivered set for this device to filter duplicates
        delivered_ids = set()
        if delivery_key:
            delivered_ids = self.redis_cluster.smembers(delivery_key)
            
        # Fetch notification data for undelivered notifications
        new_notifications = []
        newly_delivered = []
        
        for notification_id, timestamp in notification_ids:
            if notification_id not in delivered_ids:
                data_key = f"notification_data:{notification_id}"
                notification_data = self.redis_cluster.hgetall(data_key)
                
                if notification_data:
                    notification_data['timestamp'] = int(timestamp)
                    new_notifications.append(notification_data)
                    newly_delivered.append(notification_id)
                    
        # Mark as delivered for this device atomically
        if newly_delivered and delivery_key:
            pipe = self.redis_cluster.pipeline()
            pipe.sadd(delivery_key, *newly_delivered)
            pipe.expire(delivery_key, 86400 * 7)  # 7 day delivery tracking
            pipe.execute()
            
        return sorted(new_notifications, key=lambda x: x['timestamp'], reverse=True)
```

### 4.2 Client-Side Implementation with Device Tracking
```javascript
class InAppNotificationClient {
    constructor(apiBaseUrl, authToken) {
        this.apiBaseUrl = apiBaseUrl;
        this.authToken = authToken;
        this.pollingInterval = 30000; // 30 seconds
        this.lastTimestamp = 0;
        this.isPolling = false;
        // Generate device ID for delivery tracking
        this.deviceId = this.getOrCreateDeviceId();
    }
    
    getOrCreateDeviceId() {
        let deviceId = localStorage.getItem('notification_device_id');
        if (!deviceId) {
            deviceId = 'device_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('notification_device_id', deviceId);
        }
        return deviceId;
    }
    
    startPolling() {
        if (this.isPolling) return;
        this.isPolling = true;
        this.poll();
    }
    
    async poll() {
        try {
            const response = await fetch(
                `${this.apiBaseUrl}/notifications?since=${this.lastTimestamp}&device_id=${this.deviceId}`,
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
}
```

## 5. User Preference Management

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
        "system": {"push": true, "email": true, "sms": false, "in_