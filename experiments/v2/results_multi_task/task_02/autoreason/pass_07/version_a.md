# Notification System Design for 10M MAU Social App - SYNTHESIS

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design delivers core functionality reliably with clear paths for future scaling.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with JWT-based API authentication and internal service authentication
- **Device Token Service**: PostgreSQL-primary token management with Redis caching for race condition prevention
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS with dead letter queues
- **User Preference Service**: Denormalized preference management with write-through caching
- **Template Service**: Content handling with DOMPurify-based HTML sanitization
- **Analytics Service**: Aggregated delivery tracking with GDPR-compliant data collection

### Technology Stack
- **Message Queue**: Amazon SQS with weighted fair queuing across priority levels
- **Database**: PostgreSQL with read replicas, Redis Cluster for caching and session state
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with pre-approved rate limits)
- **SMS**: Twilio (with rate limiting and budget enforcement)
- **Infrastructure**: AWS with auto-scaling groups

**Rationale**: PostgreSQL-primary storage prevents race conditions while managed services reduce operational complexity. Weighted fair queuing ensures all priority levels get processing time.

## 2. Device Token Management with Race Condition Prevention

### 2.1 PostgreSQL-Primary Token Storage with Atomic Operations
```sql
CREATE TABLE device_tokens (
    user_id BIGINT NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    platform VARCHAR(10) NOT NULL CHECK (platform IN ('ios', 'android')),
    token VARCHAR(512) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_valid BOOLEAN DEFAULT true,
    last_failure_at TIMESTAMP NULL,
    failure_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, device_id)
);

-- Indexes for efficient querying
CREATE INDEX idx_device_tokens_user_valid ON device_tokens(user_id) WHERE is_valid = true;
CREATE INDEX idx_device_tokens_platform ON device_tokens(platform);
CREATE INDEX idx_device_tokens_updated ON device_tokens(updated_at);
```

### 2.2 Token Management with Redis Caching Layer
```python
class DeviceTokenManager:
    def __init__(self):
        self.db = PostgreSQLConnection()
        self.redis = RedisCluster(
            nodes=[
                {"host": "redis-1", "port": 7000},
                {"host": "redis-2", "port": 7000}, 
                {"host": "redis-3", "port": 7000}
            ]
        )
        self.cache_ttl = 300  # 5 minutes
        
    def store_token(self, user_id, device_id, platform, token):
        """Store token with atomic upsert in PostgreSQL"""
        query = """
            INSERT INTO device_tokens (user_id, device_id, platform, token, updated_at, is_valid)
            VALUES (%s, %s, %s, %s, NOW(), true)
            ON CONFLICT (user_id, device_id)
            DO UPDATE SET 
                token = EXCLUDED.token,
                updated_at = NOW(),
                is_valid = true,
                failure_count = 0,
                last_failure_at = NULL
        """
        
        with self.db.transaction():
            self.db.execute(query, (user_id, device_id, platform, token))
            
        # Invalidate cache for this user
        cache_key = f"user_tokens:{user_id}"
        self.redis.delete(cache_key)
        
    def get_user_tokens(self, user_id):
        """Get valid tokens with Redis caching"""
        cache_key = f"user_tokens:{user_id}"
        cached_tokens = self.redis.get(cache_key)
        
        if cached_tokens:
            return json.loads(cached_tokens)
            
        # Query valid tokens from PostgreSQL
        query = """
            SELECT device_id, platform, token, failure_count
            FROM device_tokens 
            WHERE user_id = %s AND is_valid = true
            ORDER BY updated_at DESC
        """
        
        tokens = self.db.fetch_all(query, (user_id,))
        
        # Cache for 5 minutes
        self.redis.setex(cache_key, self.cache_ttl, json.dumps(tokens))
        
        return tokens
        
    def cleanup_invalid_tokens(self, failed_tokens):
        """Atomically mark tokens as invalid and clean up cache"""
        for user_id, device_id in failed_tokens:
            query = """
                UPDATE device_tokens 
                SET is_valid = false, 
                    failure_count = failure_count + 1,
                    last_failure_at = NOW()
                WHERE user_id = %s AND device_id = %s
            """
            
            with self.db.transaction():
                self.db.execute(query, (user_id, device_id))
                
            # Invalidate cache
            cache_key = f"user_tokens:{user_id}"
            self.redis.delete(cache_key)
```

**Rationale**: PostgreSQL as primary storage prevents race conditions with atomic upserts. Redis caching reduces database load while maintaining consistency through cache invalidation.

## 3. Weighted Fair Queue Architecture

### 3.1 Fair Processing with Realistic Viral Content Planning
```python
class QueueManager:
    def __init__(self):
        self.queues = {
            'critical': {
                'url': "https://sqs.us-east-1.amazonaws.com/account/notifications-critical",
                'weight': 50,  # Process 50% of cycles
                'dlq_url': "https://sqs.us-east-1.amazonaws.com/account/notifications-critical-dlq"
            },
            'high': {
                'url': "https://sqs.us-east-1.amazonaws.com/account/notifications-high", 
                'weight': 30,  # Process 30% of cycles
                'dlq_url': "https://sqs.us-east-1.amazonaws.com/account/notifications-high-dlq"
            },
            'medium': {
                'url': "https://sqs.us-east-1.amazonaws.com/account/notifications-medium",
                'weight': 15,  # Process 15% of cycles
                'dlq_url': "https://sqs.us-east-1.amazonaws.com/account/notifications-medium-dlq"
            },
            'low': {
                'url': "https://sqs.us-east-1.amazonaws.com/account/notifications-low",
                'weight': 5,   # Process 5% of cycles
                'dlq_url': "https://sqs.us-east-1.amazonaws.com/account/notifications-low-dlq"
            }
        }
        
        # Realistic volume calculations accounting for viral spikes
        self.base_daily_volume = 5_000_000      # 5M base messages/day
        self.viral_spike_multiplier = 20        # 20x spike for viral content
        self.max_hourly_volume = 20_000_000     # 20M messages in worst case hour
        
        # Create weighted schedule
        self.processing_schedule = self._create_weighted_schedule()
        
    def _create_weighted_schedule(self):
        """Create a schedule ensuring all priorities get processing time"""
        schedule = []
        for priority, config in self.queues.items():
            schedule.extend([priority] * config['weight'])
        
        # Shuffle to avoid patterns
        import random
        random.shuffle(schedule)
        return schedule
        
    def process_messages_with_fairness(self):
        """Process messages using weighted fair queuing"""
        cycle_index = 0
        
        while True:
            # Get current priority from schedule
            current_priority = self.processing_schedule[cycle_index % len(self.processing_schedule)]
            queue_config = self.queues[current_priority]
            
            # Process batch from current priority queue
            messages = self.sqs.receive_message(
                QueueUrl=queue_config['url'],
                MaxNumberOfMessages=10,
                WaitTimeSeconds=1,
                MessageAttributeNames=['All']
            )
            
            if messages.get('Messages'):
                self.process_message_batch(messages['Messages'], current_priority)
            else:
                # Brief pause when queue is empty
                time.sleep(0.1)
                
            cycle_index += 1
```

### 3.2 Realistic Capacity Planning
```python
class CapacityPlanner:
    def __init__(self):
        # Based on actual SQS limits and processing time
        self.sqs_inflight_limit = 120000  # Per queue
        self.avg_processing_time_seconds = 2  # FCM/APNs HTTP request time
        self.max_concurrent_processors = 50  # Reasonable for 4 engineers to manage
        
        # Realistic social media usage patterns
        self.daily_active_users = 1_000_000
        self.avg_notifications_per_user = 5
        self.viral_content_probability = 0.01  # 1% chance of viral content daily
        self.viral_spike_multiplier = 20
        
    def calculate_realistic_throughput(self):
        # Base capacity calculation
        throughput_per_queue = self.sqs_inflight_limit / self.avg_processing_time_seconds
        total_throughput = throughput_per_queue * 4  # 4 priority queues
        
        # Account for failure retries (20% failure rate assumption)
        effective_throughput = total_throughput * 0.8
        
        # Viral content planning
        base_daily_messages = self.daily_active_users * self.avg_notifications_per_user
        viral_daily_messages = base_daily_messages * self.viral_spike_multiplier
        worst_case_hourly = viral_daily_messages * 0.5  # 50% in one hour during viral event
        
        return {
            "max_messages_per_second": int(effective_throughput),
            "daily_capacity": int(effective_throughput * 86400),
            "required_for_10m_mau": base_daily_messages,
            "viral_scenario_hourly": worst_case_hourly,
            "capacity_sufficient": effective_throughput * 86400 > viral_daily_messages,
            "estimated_monthly_cost": viral_daily_messages * 30 * 0.0000004
        }
```

**Rationale**: Weighted fair queuing prevents priority starvation while realistic capacity planning accounts for viral content spikes common in social applications.

## 4. In-App Notifications with UUID-Based Delivery Tracking

### 4.1 Efficient PostgreSQL Storage with Device-Specific Delivery
```sql
CREATE TABLE user_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    content JSONB NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    read_at TIMESTAMP NULL
);

-- Efficient indexes
CREATE INDEX idx_notifications_user_created ON user_notifications(user_id, created_at DESC);
CREATE INDEX idx_notifications_unread ON user_notifications(user_id) WHERE read_at IS NULL;

-- Device-specific delivery tracking to prevent duplicates
CREATE TABLE notification_deliveries (
    notification_id UUID REFERENCES user_notifications(id),
    device_id VARCHAR(255) NOT NULL,
    delivered_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (notification_id, device_id)
);

CREATE INDEX idx_deliveries_device ON notification_deliveries(device_id, delivered_at);
```

### 4.2 Notification Service with Device Tracking
```python
class InAppNotificationService:
    def __init__(self):
        self.db = PostgreSQLConnection()
        self.redis = RedisCluster()
        self.polling_interval = 30
        self.max_notifications_per_poll = 50
        
    def store_notification(self, user_id, content, notification_type):
        """Store notification efficiently in single table"""
        query = """
            INSERT INTO user_notifications (user_id, content, notification_type)
            VALUES (%s, %s, %s)
            RETURNING id
        """
        
        with self.db.transaction():
            result = self.db.fetch_one(query, (user_id, content, notification_type))
            notification_id = result['id']
            
            # Clean up old notifications (keep last 100)
            cleanup_query = """
                DELETE FROM user_notifications 
                WHERE user_id = %s 
                AND id NOT IN (
                    SELECT id FROM user_notifications 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 100
                )
            """
            self.db.execute(cleanup_query, (user_id, user_id))
            
        return notification_id
        
    def get_user_notifications(self, user_id, since_timestamp=None, device_id=None, limit=50):
        """Get notifications with delivery tracking to prevent duplicates"""
        # Build query with optional timestamp filter
        conditions = ["n.user_id = %s"]
        params = [user_id]
        
        if since_timestamp:
            conditions.append("n.created_at > %s")
            params.append(since_timestamp)
            
        # Get undelivered notifications for this device
        if device_id:
            conditions.append("""
                NOT EXISTS (
                    SELECT 1 FROM notification_deliveries d 
                    WHERE d.notification_id = n.id AND d.device_id = %s
                )
            """)
            params.append(device_id)
            
        query = f"""
            SELECT n.id, n.content, n.notification_type, n.created_at, n.read_at
            FROM user_notifications n
            WHERE {' AND '.join(conditions)}
            ORDER BY n.created_at DESC
            LIMIT %s
        """
        params.append(limit)
        
        notifications = self.db.fetch_all(query, params)
        
        # Mark as delivered for this device to prevent duplicates
        if notifications and device_id:
            self._mark_delivered(device_id, [n['id'] for n in notifications])
            
        return notifications
        
    def _mark_delivered(self, device_id, notification_ids):
        """Mark notifications as delivered to device"""
        if not notification_ids:
            return
            
        # Batch insert delivery records
        values = [(nid, device_id) for nid in notification_ids]
        query = """
            INSERT INTO notification_deliveries (notification_id, device_id)
            VALUES %s
            ON CONFLICT (notification_id, device_id) DO NOTHING
        """
        
        self.db.execute_values(query, values)
```

### 4.3 Client-Side Implementation with Device Tracking
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
    
    async poll() {
        try {
            const response = await fetch(
                `${this.apiBaseUrl}/notifications?since=${this.lastTimestamp}&device_id=${this.deviceId}`,
                {
                    headers: {
                        'Authorization': `Bearer ${