# Notification System Design for 10M MAU Social App - SYNTHESIS

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design delivers core functionality reliably with clear paths for future scaling.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with JWT-based API authentication and internal service authentication
- **Device Token Service**: PostgreSQL-primary token management with write-through caching for consistency
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS with dead letter queues
- **User Preference Service**: Denormalized preference management with write-through caching
- **Template Service**: Content handling with DOMPurify-based HTML sanitization
- **Analytics Service**: Aggregated delivery tracking with GDPR-compliant data collection

### Technology Stack
- **Message Queue**: Amazon SQS with queue-depth-aware processing
- **Database**: PostgreSQL with read replicas and connection pooling, Redis for caching
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with pre-approved rate limits)
- **SMS**: Twilio (with rate limiting and budget enforcement)
- **Infrastructure**: AWS with auto-scaling groups

**Rationale**: PostgreSQL-primary storage with write-through caching ensures consistency while managed services reduce operational complexity. Queue-depth-aware processing prevents resource waste while maintaining fairness.

## 2. Device Token Management with Consistency Guarantees

### 2.1 Write-Through Caching for Consistency
```python
class DeviceTokenManager:
    def __init__(self):
        self.db = PostgreSQLConnectionPool(
            min_connections=5,
            max_connections=20,
            connection_timeout=30
        )
        self.redis = Redis(host="redis-primary", port=6379)
        self.cache_ttl = 300  # 5 minutes
        
    def store_token(self, user_id, device_id, platform, token):
        """Store token with write-through caching for consistency"""
        # Validate token format before storing
        if not self._validate_token_format(token, platform):
            raise ValueError(f"Invalid {platform} token format")
            
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
            # Write to database first
            self.db.execute(query, (user_id, device_id, platform, token))
            
            # Write-through cache update in same transaction context
            cache_key = f"user_tokens:{user_id}"
            updated_tokens = self._fetch_tokens_from_db(user_id)
            self.redis.setex(cache_key, self.cache_ttl, json.dumps(updated_tokens))
        
    def _validate_token_format(self, token, platform):
        """Validate FCM/APNs token format"""
        if platform == 'android':
            # FCM tokens are typically 152+ characters
            return len(token) > 140 and token.replace(':', '').replace('-', '').replace('_', '').isalnum()
        elif platform == 'ios':
            # APNs tokens are 64 hex characters
            return len(token) == 64 and all(c in '0123456789abcdefABCDEF' for c in token)
        return False
        
    def get_user_tokens(self, user_id):
        """Get valid tokens with consistent caching"""
        cache_key = f"user_tokens:{user_id}"
        cached_tokens = self.redis.get(cache_key)
        
        if cached_tokens:
            return json.loads(cached_tokens)
            
        # Fallback to database
        tokens = self._fetch_tokens_from_db(user_id)
        self.redis.setex(cache_key, self.cache_ttl, json.dumps(tokens))
        return tokens
        
    def _fetch_tokens_from_db(self, user_id):
        """Fetch tokens from database with read replica support"""
        query = """
            SELECT device_id, platform, token, failure_count
            FROM device_tokens 
            WHERE user_id = %s AND is_valid = true
            ORDER BY updated_at DESC
        """
        return self.db.fetch_all(query, (user_id,), use_replica=True)
```

### 2.2 Database Schema
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

**Rationale**: Write-through caching eliminates race conditions while providing fast reads. Token validation prevents invalid tokens from entering the system, reducing downstream failures.

## 3. Queue-Depth-Aware Processing with Fair Scheduling

### 3.1 Dynamic Queue Processing Based on Actual Load
```python
class QueueManager:
    def __init__(self):
        self.queues = {
            'critical': {
                'url': "https://sqs.us-east-1.amazonaws.com/account/notifications-critical",
                'min_weight': 40,  # Minimum 40% when queues have messages
                'dlq_url': "https://sqs.us-east-1.amazonaws.com/account/notifications-critical-dlq"
            },
            'high': {
                'url': "https://sqs.us-east-1.amazonaws.com/account/notifications-high", 
                'min_weight': 30,
                'dlq_url': "https://sqs.us-east-1.amazonaws.com/account/notifications-high-dlq"
            },
            'medium': {
                'url': "https://sqs.us-east-1.amazonaws.com/account/notifications-medium",
                'min_weight': 20,
                'dlq_url': "https://sqs.us-east-1.amazonaws.com/account/notifications-medium-dlq"
            },
            'low': {
                'url': "https://sqs.us-east-1.amazonaws.com/account/notifications-low",
                'min_weight': 10,
                'dlq_url': "https://sqs.us-east-1.amazonaws.com/account/notifications-low-dlq"
            }
        }
        
        # Realistic volume calculations accounting for viral spikes
        self.base_daily_volume = 3_000_000      # 3M base messages/day (1M DAU * 3 notifications)
        self.viral_spike_multiplier = 10        # 10x spike for viral content
        self.max_hourly_volume = 5_000_000      # 5M messages in worst case hour
        
    def get_queue_depths(self):
        """Get current queue depths to guide processing"""
        depths = {}
        for priority, config in self.queues.items():
            try:
                response = self.sqs.get_queue_attributes(
                    QueueUrl=config['url'],
                    AttributeNames=['ApproximateNumberOfMessages']
                )
                depths[priority] = int(response['Attributes']['ApproximateNumberOfMessages'])
            except Exception as e:
                logger.warning(f"Failed to get depth for {priority} queue: {e}")
                depths[priority] = 0
        return depths
        
    def calculate_processing_allocation(self, queue_depths):
        """Calculate how many messages to process from each queue"""
        total_messages = sum(queue_depths.values())
        if total_messages == 0:
            return {priority: 0 for priority in self.queues.keys()}
            
        # Calculate allocation based on queue depth and minimum weights
        allocation = {}
        remaining_capacity = 100
        
        # First, ensure minimum processing for non-empty queues
        for priority in ['critical', 'high', 'medium', 'low']:
            if queue_depths[priority] > 0:
                min_allocation = min(
                    self.queues[priority]['min_weight'],
                    remaining_capacity,
                    queue_depths[priority]
                )
                allocation[priority] = min_allocation
                remaining_capacity -= min_allocation
            else:
                allocation[priority] = 0
                
        # Distribute remaining capacity based on queue depth
        if remaining_capacity > 0:
            depth_sum = sum(max(0, queue_depths[p] - allocation[p]) for p in allocation.keys())
            if depth_sum > 0:
                for priority in allocation.keys():
                    remaining_depth = max(0, queue_depths[priority] - allocation[priority])
                    additional = int((remaining_depth / depth_sum) * remaining_capacity)
                    allocation[priority] += additional
                    
        return allocation
        
    def process_messages_with_depth_awareness(self):
        """Process messages based on actual queue depths"""
        while True:
            queue_depths = self.get_queue_depths()
            allocation = self.calculate_processing_allocation(queue_depths)
            
            # Process messages according to calculated allocation
            for priority, message_count in allocation.items():
                if message_count > 0:
                    self.process_queue_batch(priority, min(message_count, 10))
                    
            # Brief pause between processing cycles
            time.sleep(1)
```

### 3.2 Realistic Capacity Planning
```python
class CapacityPlanner:
    def __init__(self):
        # Realistic SQS processing limits
        self.sqs_batch_size = 10  # SQS max batch size
        self.avg_network_latency_ms = 50  # Realistic AWS latency
        self.fcm_processing_time_ms = 200  # FCM HTTP request time
        self.total_processing_time_s = (self.avg_network_latency_ms + self.fcm_processing_time_ms) / 1000
        
        # Realistic concurrent processing
        self.max_concurrent_workers = 20  # Manageable for 4 engineers
        self.messages_per_worker_per_second = 1 / self.total_processing_time_s  # ~4 messages/second
        
        # Social media usage patterns
        self.daily_active_users = 1_000_000  # 1M of 10M MAU
        self.avg_notifications_per_user = 3  # Conservative estimate
        self.peak_hour_multiplier = 4  # 4x average during peak hour
        self.viral_content_probability = 0.01  # 1% chance of viral content daily
        self.viral_spike_multiplier = 10
        
    def calculate_realistic_throughput(self):
        """Calculate achievable throughput with realistic constraints"""
        # Per-worker throughput
        worker_throughput = self.messages_per_worker_per_second * 0.8  # 80% efficiency
        
        # Total system throughput
        total_throughput = worker_throughput * self.max_concurrent_workers
        
        # Daily capacity
        daily_capacity = total_throughput * 86400
        
        # Required capacity
        base_daily_messages = self.daily_active_users * self.avg_notifications_per_user
        viral_daily_messages = base_daily_messages * self.viral_spike_multiplier
        peak_hourly_messages = viral_daily_messages * 0.5  # 50% in one hour during viral event
        required_peak_throughput = peak_hourly_messages / 3600
        
        return {
            "max_messages_per_second": int(total_throughput),
            "daily_capacity": int(daily_capacity),
            "required_daily": base_daily_messages,
            "viral_scenario_daily": viral_daily_messages,
            "required_peak_throughput": int(required_peak_throughput),
            "capacity_sufficient": total_throughput > required_peak_throughput * 1.5,  # 50% headroom
            "estimated_monthly_cost": self._calculate_monthly_cost(base_daily_messages)
        }
        
    def _calculate_monthly_cost(self, daily_messages):
        """Realistic cost calculation including all services"""
        monthly_messages = daily_messages * 30
        
        # SQS costs ($0.40 per million requests)
        sqs_cost = (monthly_messages / 1_000_000) * 0.40
        
        # Database costs (RDS PostgreSQL db.t3.large)
        db_cost = 200  # ~$200/month for db.t3.large
        
        # Redis costs (ElastiCache t3.micro)
        redis_cost = 15  # ~$15/month for t3.micro
        
        # EC2 costs (t3.medium instances)
        ec2_cost = 100  # ~$100/month for 3 t3.medium instances
        
        return {
            "sqs": sqs_cost,
            "database": db_cost,
            "redis": redis_cost,
            "compute": ec2_cost,
            "total": sqs_cost + db_cost + redis_cost + ec2_cost
        }
```

**Rationale**: Queue-depth-aware processing prevents resource waste while maintaining fairness through minimum weight guarantees. Realistic capacity planning accounts for viral content spikes common in social applications.

## 4. Partitioned In-App Notifications with Simple State Tracking

### 4.1 Scalable Database Schema
```sql
-- Partitioned table for scalability
CREATE TABLE user_notifications (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    read_at TIMESTAMP NULL
) PARTITION BY HASH (user_id);

-- Create 16 partitions for 10M users
CREATE TABLE user_notifications_00 PARTITION OF user_notifications FOR VALUES WITH (modulus 16, remainder 0);
CREATE TABLE user_notifications_01 PARTITION OF user_notifications FOR VALUES WITH (modulus 16, remainder 1);
-- ... create remaining 14 partitions

-- Efficient indexes on each partition
CREATE INDEX idx_notifications_user_created_00 ON user_notifications_00(user_id, created_at DESC);
CREATE INDEX idx_notifications_unread_00 ON user_notifications_00(user_id) WHERE read_at IS NULL;
-- ... create indexes on remaining partitions

-- Simple last-seen tracking per user
CREATE TABLE user_notification_state (
    user_id BIGINT PRIMARY KEY,
    last_seen_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.2 Simplified Notification Service
```python
class InAppNotificationService:
    def __init__(self):
        self.db = PostgreSQLConnectionPool(
            min_connections=5,
            max_connections=20
        )
        self.redis = Redis()
        self.max_notifications_per_user = 100
        
    def store_notification(self, user_id, content, notification_type):
        """Store notification with automatic cleanup"""
        with self.db.transaction():
            # Insert new notification
            query = """
                INSERT INTO user_notifications (user_id, content, notification_type)
                VALUES (%s, %s, %s)
                RETURNING id
            """
            result = self.db.fetch_