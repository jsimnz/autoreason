# Notification System Design for 10M MAU Social App - REVISED

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design delivers core functionality reliably with clear paths for future scaling.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with mutual TLS authentication between internal services
- **Device Token Service**: PostgreSQL with connection pooling and distributed locking for consistency
- **Channel Handlers**: Parallel processors for push, email, in-app, and SMS with comprehensive error handling
- **User Preference Service**: Denormalized preference management with write-through caching
- **Template Service**: Content handling with comprehensive injection prevention
- **Analytics Service**: Aggregated delivery tracking with explicit GDPR compliance measures

### Technology Stack
- **Message Queue**: Amazon SQS with parallel processing across priority queues
- **Database**: PostgreSQL with connection pooling, Redis for caching and distributed locking
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with pre-approved rate limits)
- **SMS**: Twilio (with rate limiting and budget enforcement)
- **Infrastructure**: AWS with auto-scaling groups

**Rationale**: PostgreSQL with distributed locking prevents race conditions while managed services reduce operational complexity. Parallel processing maximizes throughput within realistic constraints.

## 2. Device Token Management with Distributed Locking

**Fixes Problem #1: Race condition prevention through proper distributed locking**

### 2.1 PostgreSQL Storage with Connection Pooling
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

### 2.2 Token Management with Distributed Locking
```python
import psycopg2.pool
import redis.lock

class DeviceTokenManager:
    def __init__(self):
        # Fix Problem #12: Add connection pooling
        self.db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=5,
            maxconn=50,
            host="postgres-host",
            database="notifications",
            user="app_user",
            password="password"
        )
        
        self.redis = redis.Redis(
            host="redis-host",
            port=6379,
            decode_responses=True
        )
        self.cache_ttl = 300  # 5 minutes
        
    def store_token(self, user_id, device_id, platform, token):
        """Store token with distributed locking to prevent race conditions"""
        lock_key = f"token_lock:{user_id}:{device_id}"
        
        # Fix Problem #1: Use distributed lock to prevent race conditions
        with redis.lock.Lock(self.redis, lock_key, timeout=10):
            conn = self.db_pool.getconn()
            try:
                with conn.cursor() as cursor:
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
                    cursor.execute(query, (user_id, device_id, platform, token))
                    conn.commit()
                    
                    # Invalidate cache only after successful DB write
                    cache_key = f"user_tokens:{user_id}"
                    self.redis.delete(cache_key)
                    
            finally:
                self.db_pool.putconn(conn)
        
    def get_user_tokens(self, user_id):
        """Get valid tokens with Redis caching"""
        cache_key = f"user_tokens:{user_id}"
        cached_tokens = self.redis.get(cache_key)
        
        if cached_tokens:
            return json.loads(cached_tokens)
            
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT device_id, platform, token, failure_count
                    FROM device_tokens 
                    WHERE user_id = %s AND is_valid = true
                    ORDER BY updated_at DESC
                """
                cursor.execute(query, (user_id,))
                tokens = cursor.fetchall()
                
                # Cache for 5 minutes
                self.redis.setex(cache_key, self.cache_ttl, json.dumps(tokens))
                
                return tokens
        finally:
            self.db_pool.putconn(conn)
```

## 3. Parallel Queue Processing Architecture

**Fixes Problem #2: Replace broken weighted fair queuing with proper parallel processing**
**Fixes Problem #3: Realistic capacity calculations based on worker limits**

### 3.1 Parallel Processing with Realistic Throughput
```python
import concurrent.futures
import threading
from dataclasses import dataclass

@dataclass
class QueueConfig:
    url: str
    dlq_url: str
    worker_count: int
    max_receive_count: int

class ParallelQueueManager:
    def __init__(self):
        # Fix Problem #2: Use parallel processing instead of sequential weighted queuing
        self.queues = {
            'critical': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-critical",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-critical-dlq",
                worker_count=20,  # Most workers for critical
                max_receive_count=3
            ),
            'high': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-high", 
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-high-dlq",
                worker_count=15,
                max_receive_count=3
            ),
            'medium': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-medium",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-medium-dlq",
                worker_count=10,
                max_receive_count=3
            ),
            'low': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-low",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-low-dlq",
                worker_count=5,
                max_receive_count=3
            )
        }
        
        self.total_workers = sum(config.worker_count for config in self.queues.values())
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.total_workers)
        self.shutdown_event = threading.Event()
        
    def start_processing(self):
        """Start parallel processing for all queues"""
        futures = []
        
        for priority, config in self.queues.items():
            for worker_id in range(config.worker_count):
                future = self.executor.submit(
                    self._process_queue_worker, 
                    priority, 
                    config, 
                    worker_id
                )
                futures.append(future)
                
        return futures
        
    def _process_queue_worker(self, priority, config, worker_id):
        """Individual worker processing messages from a specific queue"""
        while not self.shutdown_event.is_set():
            try:
                # Fix Problem #6: Add comprehensive error handling
                messages = self.sqs.receive_message(
                    QueueUrl=config.url,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=20,  # Long polling
                    MessageAttributeNames=['All']
                )
                
                if messages.get('Messages'):
                    self._process_message_batch(messages['Messages'], priority, config)
                    
            except Exception as e:
                logger.error(f"Worker {priority}-{worker_id} error: {e}")
                time.sleep(5)  # Brief pause before retrying
                
    def _process_message_batch(self, messages, priority, config):
        """Process batch with proper error handling and DLQ routing"""
        for message in messages:
            try:
                # Process individual message
                success = self._process_notification_message(message)
                
                if success:
                    # Delete from queue on success
                    self.sqs.delete_message(
                        QueueUrl=config.url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                else:
                    # Let message return to queue for retry
                    pass
                    
            except Exception as e:
                logger.error(f"Message processing failed: {e}")
                # Message will be retried automatically by SQS
```

### 3.2 Realistic Capacity Planning
**Fixes Problem #3: Accurate throughput calculations**

```python
class CapacityPlanner:
    def __init__(self):
        # Fix Problem #3: Base calculations on actual worker capacity
        self.total_workers = 50  # Realistic for 4 engineers to manage
        self.avg_processing_time_seconds = 3  # Including network latency and retries
        self.worker_efficiency = 0.8  # Account for overhead and failures
        
        # Realistic social media usage patterns
        self.daily_active_users = 1_000_000  # 10% of 10M MAU are daily active
        self.avg_notifications_per_user = 5
        
        # Fix Problem #13: Realistic spike planning
        self.viral_spike_multiplier = 3  # More realistic 3x spike
        self.spike_duration_hours = 2  # Viral content peaks for 2 hours
        
    def calculate_realistic_throughput(self):
        # Actual processing capacity based on workers
        max_throughput = (self.total_workers / self.avg_processing_time_seconds) * self.worker_efficiency
        
        # Base daily volume
        base_daily_messages = self.daily_active_users * self.avg_notifications_per_user
        
        # Viral spike planning - spread over 2 hours
        viral_spike_messages = base_daily_messages * (self.viral_spike_multiplier - 1)
        viral_hourly_rate = viral_spike_messages / self.spike_duration_hours
        viral_per_second = viral_hourly_rate / 3600
        
        # Base rate + viral spike
        peak_required_throughput = (base_daily_messages / 86400) + viral_per_second
        
        return {
            "max_messages_per_second": int(max_throughput),
            "daily_capacity": int(max_throughput * 86400),
            "base_daily_requirement": base_daily_messages,
            "peak_throughput_requirement": int(peak_required_throughput),
            "capacity_sufficient": max_throughput > peak_required_throughput,
            "headroom_percentage": ((max_throughput - peak_required_throughput) / max_throughput) * 100
        }
```

## 4. In-App Notifications with Efficient Storage

**Fixes Problem #4: Replace expensive JOIN queries with efficient single-table design**
**Fixes Problem #5: Use cryptographically secure device ID generation**

### 4.1 Efficient Single-Table Storage
```sql
-- Fix Problem #4: Single table design to avoid expensive JOINs
CREATE TABLE user_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    content JSONB NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    read_at TIMESTAMP NULL,
    -- Store delivered device IDs directly in array to avoid JOIN
    delivered_device_ids TEXT[] DEFAULT ARRAY[]::TEXT[]
);

-- Efficient indexes
CREATE INDEX idx_notifications_user_created ON user_notifications(user_id, created_at DESC);
CREATE INDEX idx_notifications_unread ON user_notifications(user_id) WHERE read_at IS NULL;
-- GIN index for array operations
CREATE INDEX idx_notifications_delivered_devices ON user_notifications USING GIN (delivered_device_ids);
```

### 4.2 Notification Service with Array-Based Device Tracking
```python
import secrets
import string

class InAppNotificationService:
    def __init__(self):
        self.db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=5, maxconn=50,
            host="postgres-host", database="notifications"
        )
        self.redis = redis.Redis(host="redis-host", port=6379)
        
    def store_notification(self, user_id, content, notification_type):
        """Store notification efficiently in single table"""
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO user_notifications (user_id, content, notification_type)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """
                cursor.execute(query, (user_id, content, notification_type))
                result = cursor.fetchone()
                notification_id = result[0]
                
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
                cursor.execute(cleanup_query, (user_id, user_id))
                conn.commit()
                
            return notification_id
        finally:
            self.db_pool.putconn(conn)
        
    def get_user_notifications(self, user_id, since_timestamp=None, device_id=None, limit=50):
        """Get notifications with efficient array-based delivery tracking"""
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                conditions = ["user_id = %s"]
                params = [user_id]
                
                if since_timestamp:
                    conditions.append("created_at > %s")
                    params.append(since_timestamp)
                    
                # Fix Problem #4: Use array containment instead of JOIN
                if device_id:
                    conditions.append("NOT (%s = ANY(delivered_device_ids))")
                    params.append(device_id)
                    
                query = f"""
                    SELECT id, content, notification_type, created_at, read_at
                    FROM user_notifications
                    WHERE {' AND '.join(conditions)}
                    ORDER BY created_at DESC
                    LIMIT %s
                """
                params.append(limit)
                
                cursor.execute(query, params)
                notifications = cursor.fetchall()
                
                # Mark as delivered by updating array
                if notifications and device_id:
                    self._mark_delivered(device_id, [n[0] for n in notifications])
                    
                return notifications
        finally:
            self.db_pool.putconn(conn)
        
    def _mark_delivered(self, device_id, notification_ids):
        """Mark notifications as delivered using array append"""
        if not