# Notification System Design for 10M MAU Social App - SYNTHESIS

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design delivers core functionality reliably with clear paths for future scaling.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with mutual TLS authentication between internal services
- **Device Token Service**: PostgreSQL with Redis Sentinel clustering for high availability
- **Channel Handlers**: Parallel processors for push, email, in-app, and SMS with circuit breaker patterns
- **User Preference Service**: Denormalized preference management with versioned caching
- **Template Service**: Jinja2-based content handling with sandboxed execution
- **Analytics Service**: Event-driven tracking with separate data pipeline

### Technology Stack
- **Message Queue**: Amazon SQS with properly configured visibility timeouts
- **Database**: PostgreSQL with optimized connection pooling, Redis Sentinel for distributed operations
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with pre-approved rate limits)
- **SMS**: Twilio (with rate limiting and budget enforcement)
- **Infrastructure**: AWS with auto-scaling groups

**Rationale**: Redis Sentinel clustering eliminates single points of failure while optimized connection pooling prevents resource exhaustion. Circuit breakers ensure graceful degradation under load.

## 2. Device Token Management with Complete Lifecycle Protection

**Addresses: Race condition prevention, high availability, token validation lifecycle**

### 2.1 PostgreSQL Storage with Token Lifecycle Management
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
    -- Add validation state tracking
    validation_state VARCHAR(20) DEFAULT 'pending' CHECK (validation_state IN ('pending', 'valid', 'invalid', 'validating')),
    validation_worker_id VARCHAR(100) NULL,
    validation_expires_at TIMESTAMP NULL,
    PRIMARY KEY (user_id, device_id)
);

-- Efficient indexes
CREATE INDEX idx_device_tokens_user_valid ON device_tokens(user_id) WHERE is_valid = true AND validation_state = 'valid';
CREATE INDEX idx_device_tokens_validation ON device_tokens(validation_state, validation_expires_at);
CREATE INDEX idx_device_tokens_updated ON device_tokens(updated_at);
```

### 2.2 Token Management with Complete Race Condition Prevention
```python
import psycopg2.pool
import redis.sentinel
import uuid
from enum import Enum

class ValidationState(Enum):
    PENDING = 'pending'
    VALID = 'valid'
    INVALID = 'invalid'
    VALIDATING = 'validating'

class DeviceTokenManager:
    def __init__(self):
        # Optimized connection pooling to prevent exhaustion
        self.db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=15,  # Smaller pool to prevent exhaustion
            host="postgres-host",
            database="notifications",
            user="app_user",
            password="password"
        )
        
        # Redis Sentinel for high availability
        sentinel = redis.sentinel.Sentinel([
            ('redis-sentinel-1', 26379),
            ('redis-sentinel-2', 26379),
            ('redis-sentinel-3', 26379)
        ])
        self.redis = sentinel.master_for('notifications', decode_responses=True)
        self.cache_ttl = 300
        self.worker_id = str(uuid.uuid4())
        
    def store_token(self, user_id, device_id, platform, token):
        """Store token with complete lifecycle race condition prevention"""
        lock_key = f"token_lifecycle:{user_id}:{device_id}"
        
        with self.redis.lock(lock_key, timeout=30, blocking_timeout=5):
            conn = self.db_pool.getconn()
            try:
                with conn.cursor() as cursor:
                    # Check for ongoing validation
                    cursor.execute("""
                        SELECT validation_state, validation_worker_id, validation_expires_at
                        FROM device_tokens 
                        WHERE user_id = %s AND device_id = %s
                    """, (user_id, device_id))
                    
                    existing = cursor.fetchone()
                    
                    # If validation is in progress and not expired, wait
                    if existing and existing[0] == 'validating':
                        if existing[2] and existing[2] > datetime.now():
                            raise ValueError("Token validation in progress")
                    
                    # Store new token with pending validation
                    query = """
                        INSERT INTO device_tokens (
                            user_id, device_id, platform, token, updated_at, 
                            is_valid, validation_state
                        )
                        VALUES (%s, %s, %s, %s, NOW(), true, %s)
                        ON CONFLICT (user_id, device_id)
                        DO UPDATE SET 
                            token = EXCLUDED.token,
                            updated_at = NOW(),
                            is_valid = true,
                            failure_count = 0,
                            last_failure_at = NULL,
                            validation_state = %s,
                            validation_worker_id = NULL,
                            validation_expires_at = NULL
                    """
                    cursor.execute(query, (
                        user_id, device_id, platform, token, 
                        ValidationState.PENDING.value,
                        ValidationState.PENDING.value
                    ))
                    conn.commit()
                    
                    # Invalidate cache with versioning
                    self._invalidate_user_cache(user_id)
                    
            finally:
                self.db_pool.putconn(conn)
    
    def get_user_tokens(self, user_id):
        """Get valid tokens with versioned caching"""
        # Check cache version first
        version_key = f"user_tokens_version:{user_id}"
        cache_key = f"user_tokens:{user_id}"
        
        cached_version = self.redis.get(f"{cache_key}:version")
        current_version = self.redis.get(version_key)
        
        if cached_version and cached_version == current_version:
            cached_tokens = self.redis.get(cache_key)
            if cached_tokens:
                return json.loads(cached_tokens)
            
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT device_id, platform, token, failure_count
                    FROM device_tokens 
                    WHERE user_id = %s AND is_valid = true AND validation_state = 'valid'
                    ORDER BY updated_at DESC
                """
                cursor.execute(query, (user_id,))
                tokens = cursor.fetchall()
                
                # Cache with version
                pipe = self.redis.pipeline()
                pipe.setex(cache_key, self.cache_ttl, json.dumps(tokens))
                pipe.setex(f"{cache_key}:version", self.cache_ttl, current_version or "1")
                pipe.execute()
                
                return tokens
        finally:
            self.db_pool.putconn(conn)
    
    def _invalidate_user_cache(self, user_id):
        """Invalidate cache with versioning to prevent race conditions"""
        version_key = f"user_tokens_version:{user_id}"
        cache_key = f"user_tokens:{user_id}"
        
        pipe = self.redis.pipeline()
        pipe.incr(version_key)
        pipe.delete(cache_key)
        pipe.delete(f"{cache_key}:version")
        pipe.execute()
```

## 3. Parallel Queue Processing with Proper Resource Management

**Addresses: Realistic capacity planning, proper SQS configuration, circuit breaker patterns**

### 3.1 SQS Configuration with Proper Timeouts and Parallel Processing
```python
import boto3
import concurrent.futures
import threading
from dataclasses import dataclass
from circuit_breaker import CircuitBreaker

@dataclass
class QueueConfig:
    url: str
    dlq_url: str
    worker_count: int
    max_receive_count: int
    visibility_timeout: int  # Must be longer than max processing time
    max_processing_time: int

class ParallelQueueManager:
    def __init__(self):
        # Realistic worker allocation to prevent connection exhaustion
        self.queues = {
            'critical': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-critical",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-critical-dlq",
                worker_count=8,
                max_receive_count=3,
                visibility_timeout=300,  # 5 minutes for retries and external API calls
                max_processing_time=240
            ),
            'high': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-high", 
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-high-dlq",
                worker_count=6,
                max_receive_count=3,
                visibility_timeout=300,
                max_processing_time=240
            ),
            'medium': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-medium",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-medium-dlq",
                worker_count=4,
                max_receive_count=3,
                visibility_timeout=180,
                max_processing_time=120
            ),
            'low': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-low",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-low-dlq",
                worker_count=2,
                max_receive_count=3,
                visibility_timeout=120,
                max_processing_time=60
            )
        }
        
        self.total_workers = sum(config.worker_count for config in self.queues.values())
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.total_workers)
        self.shutdown_event = threading.Event()
        
        # Circuit breakers for external services
        self.fcm_breaker = CircuitBreaker(failure_threshold=5, timeout=30)
        self.apns_breaker = CircuitBreaker(failure_threshold=5, timeout=30)
        self.ses_breaker = CircuitBreaker(failure_threshold=3, timeout=60)
        
        self.sqs = boto3.client('sqs', region_name='us-east-1')
        
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
                messages = self.sqs.receive_message(
                    QueueUrl=config.url,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=20,  # Long polling
                    MessageAttributeNames=['All'],
                    VisibilityTimeout=config.visibility_timeout
                )
                
                if messages.get('Messages'):
                    self._process_message_batch(messages['Messages'], priority, config)
                    
            except Exception as e:
                logger.error(f"Worker {priority}-{worker_id} error: {e}")
                time.sleep(5)  # Brief pause before retrying
                
    def _process_notification_message(self, message):
        """Complete notification processing implementation"""
        try:
            message_data = json.loads(message['Body'])
            user_id = message_data.get('user_id')
            content = message_data.get('content')
            channels = message_data.get('channels', [])
            
            processing_results = {}
            
            for channel in channels:
                try:
                    if channel == 'push':
                        result = self._send_push_notification(user_id, content)
                    elif channel == 'email':
                        result = self._send_email_notification(user_id, content)
                    elif channel == 'sms':
                        result = self._send_sms_notification(user_id, content)
                    elif channel == 'in_app':
                        result = self._store_in_app_notification(user_id, content)
                    else:
                        result = {'success': False, 'error': f'Unknown channel: {channel}'}
                        
                    processing_results[channel] = result
                    
                except Exception as e:
                    processing_results[channel] = {'success': False, 'error': str(e)}
            
            # Consider message successful if any channel succeeded
            success = any(result.get('success', False) for result in processing_results.values())
            
            # Log results for analytics
            self._log_notification_result(message_data, processing_results)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to process notification message: {e}")
            return False
```

### 3.2 Realistic Capacity Planning
```python
class CapacityPlanner:
    def __init__(self):
        # Realistic worker capacity based on 4 engineers managing system
        self.total_workers = 20  # Conservative for operational stability
        self.avg_processing_time_seconds = 3  # Including network latency and retries
        self.worker_efficiency = 0.8  # Account for overhead and failures
        
        # Realistic social media usage patterns
        self.daily_active_users = 1_000_000  # 10% of 10M MAU are daily active
        self.avg_notifications_per_user = 5
        
        # Realistic spike planning
        self.viral_spike_multiplier = 3  # 3x spike during viral events
        self.spike_duration_hours = 2  # Viral content peaks for 2 hours
        
    def calculate_realistic_throughput(self):
        # Actual processing capacity based on workers
        max_throughput = (self.total_workers / self.avg_processing_time_seconds) * self.worker_efficiency
        
        # Base daily volume
        base_daily_messages = self.daily_active_users * self.avg_notifications_per_user
        
        # Viral spike planning
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
            "headroom_percentage": ((max_throughput - peak_required_