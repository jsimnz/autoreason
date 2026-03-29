# Notification System Design for 10M MAU Social App - SYNTHESIS

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design delivers core functionality reliably with clear paths for future scaling.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with JWT-based service authentication
- **Device Token Service**: PostgreSQL with local Redis caching and optimized connection management
- **Channel Handlers**: Parallel processors for push, email, in-app, and SMS with circuit breaker patterns
- **User Preference Service**: Denormalized preference management with local caching
- **Template Service**: Pre-approved template system with parameterized content
- **Analytics Service**: Asynchronous event logging with buffering

### Technology Stack
- **Message Queue**: Amazon SQS with properly configured visibility timeouts and DLQ
- **Database**: PostgreSQL with optimized connection pooling, local Redis for caching
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with pre-approved rate limits)
- **SMS**: Twilio (with rate limiting and budget enforcement)
- **Infrastructure**: AWS with auto-scaling groups

**Rationale**: Local Redis caching provides simplicity and reliability for MVP while PostgreSQL handles persistent state. Managed services reduce operational complexity for the small team.

## 2. Device Token Management with Atomic Operations

**Addresses**: Race condition prevention, simple atomic operations, efficient caching

### 2.1 PostgreSQL Storage with Lifecycle Tracking
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
    -- Add validation state for token lifecycle management
    validation_state VARCHAR(20) DEFAULT 'valid' CHECK (validation_state IN ('pending', 'valid', 'invalid')),
    PRIMARY KEY (user_id, device_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Optimized indexes
CREATE INDEX idx_device_tokens_user_valid ON device_tokens(user_id) WHERE is_valid = true AND validation_state = 'valid';
CREATE INDEX idx_device_tokens_validation ON device_tokens(validation_state) WHERE validation_state = 'pending';
```

### 2.2 Simplified Token Management with Atomic Operations
```python
import psycopg2.pool
import redis
import json
import time
from contextlib import contextmanager
from enum import Enum

class ValidationState(Enum):
    PENDING = 'pending'
    VALID = 'valid'
    INVALID = 'invalid'

class DeviceTokenManager:
    def __init__(self):
        # Properly sized connection pool for worker count
        self.db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=5,
            maxconn=20,  # Sized for total workers + overhead
            host="postgres-host",
            database="notifications",
            user="app_user",
            password="password",
            connect_timeout=10
        )
        
        # Simple local Redis for MVP reliability
        self.redis = redis.Redis(
            host='redis-host',
            port=6379,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        self.cache_ttl = 300
        
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections with timeout"""
        conn = None
        try:
            conn = self.db_pool.getconn()
            if conn is None:
                raise Exception("Unable to get database connection")
            yield conn
        finally:
            if conn:
                self.db_pool.putconn(conn)
    
    def store_token(self, user_id, device_id, platform, token):
        """Store token with simple atomic operation and validation state"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Simple atomic upsert with validation state
                query = """
                    INSERT INTO device_tokens (
                        user_id, device_id, platform, token, updated_at, 
                        is_valid, failure_count, validation_state
                    )
                    VALUES (%s, %s, %s, %s, NOW(), true, 0, %s)
                    ON CONFLICT (user_id, device_id)
                    DO UPDATE SET 
                        token = EXCLUDED.token,
                        platform = EXCLUDED.platform,
                        updated_at = NOW(),
                        is_valid = true,
                        failure_count = 0,
                        last_failure_at = NULL,
                        validation_state = %s
                """
                cursor.execute(query, (
                    user_id, device_id, platform, token,
                    ValidationState.PENDING.value,
                    ValidationState.PENDING.value
                ))
                conn.commit()
                
                # Simple cache invalidation
                self._invalidate_user_cache(user_id)
    
    def get_valid_tokens(self, user_id):
        """Get valid tokens with local caching"""
        cache_key = f"user_tokens:{user_id}"
        
        # Try cache first
        try:
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except:
            pass  # Cache failure shouldn't break functionality
        
        # Query database for valid, verified tokens
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT device_id, platform, token, failure_count
                    FROM device_tokens 
                    WHERE user_id = %s 
                    AND is_valid = true 
                    AND validation_state = %s
                    ORDER BY updated_at DESC
                """, (user_id, ValidationState.VALID.value))
                
                tokens = cursor.fetchall()
                
                # Cache result with error handling
                try:
                    self.redis.setex(cache_key, self.cache_ttl, json.dumps(tokens))
                except:
                    pass
                
                return tokens
    
    def mark_token_validation_result(self, user_id, device_id, is_valid):
        """Mark token validation result atomically"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                if is_valid:
                    cursor.execute("""
                        UPDATE device_tokens 
                        SET validation_state = %s,
                            is_valid = true,
                            failure_count = 0,
                            last_failure_at = NULL
                        WHERE user_id = %s AND device_id = %s
                    """, (ValidationState.VALID.value, user_id, device_id))
                else:
                    cursor.execute("""
                        UPDATE device_tokens 
                        SET validation_state = %s,
                            is_valid = false,
                            failure_count = failure_count + 1,
                            last_failure_at = NOW()
                        WHERE user_id = %s AND device_id = %s
                    """, (ValidationState.INVALID.value, user_id, device_id))
                
                conn.commit()
                self._invalidate_user_cache(user_id)
    
    def _invalidate_user_cache(self, user_id):
        """Simple cache invalidation"""
        try:
            self.redis.delete(f"user_tokens:{user_id}")
        except:
            pass  # Cache failures shouldn't break core functionality
```

## 3. Robust Queue Processing with Proper Resource Management

**Addresses**: Connection pooling, SQS configuration, circuit breakers, backpressure handling

### 3.1 SQS Configuration with Proper Timeouts and DLQ
```python
import boto3
import concurrent.futures
import threading
import time
import json
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class SharedCircuitBreaker:
    """Shared circuit breaker state across workers using Redis"""
    def __init__(self, redis_client, name, failure_threshold=5, timeout=30):
        self.redis = redis_client
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state_key = f"circuit:{name}:state"
        self.failure_key = f"circuit:{name}:failures"
        self.last_failure_key = f"circuit:{name}:last_failure"
    
    def is_open(self):
        try:
            state = self.redis.get(self.state_key) or CircuitState.CLOSED.value
            if state == CircuitState.OPEN.value:
                last_failure = self.redis.get(self.last_failure_key)
                if last_failure and time.time() - float(last_failure) > self.timeout:
                    self.redis.set(self.state_key, CircuitState.HALF_OPEN.value)
                    return False
                return True
            return False
        except:
            return False  # Fail safe - allow requests if Redis is down
    
    def record_success(self):
        try:
            self.redis.delete(self.failure_key)
            self.redis.set(self.state_key, CircuitState.CLOSED.value)
        except:
            pass
    
    def record_failure(self):
        try:
            failures = self.redis.incr(self.failure_key)
            self.redis.set(self.last_failure_key, time.time())
            if failures >= self.failure_threshold:
                self.redis.set(self.state_key, CircuitState.OPEN.value)
        except:
            pass

@dataclass
class QueueConfig:
    url: str
    dlq_url: str
    worker_count: int
    max_receive_count: int
    visibility_timeout: int  # Must be longer than max processing time + retry delays
    max_processing_time: int
    retry_delay: int

class NotificationProcessor:
    def __init__(self):
        # Properly configured queues with appropriate timeouts
        self.queues = {
            'critical': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-critical",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-critical-dlq",
                worker_count=4,
                max_receive_count=3,
                visibility_timeout=900,  # 15 minutes - accounts for retries and external API timeouts
                max_processing_time=300,
                retry_delay=60
            ),
            'high': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-high", 
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-high-dlq",
                worker_count=3,
                max_receive_count=3,
                visibility_timeout=600,  # 10 minutes
                max_processing_time=240,
                retry_delay=30
            ),
            'medium': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-medium",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-medium-dlq",
                worker_count=3,
                max_receive_count=3,
                visibility_timeout=400,  # 6.7 minutes
                max_processing_time=180,
                retry_delay=15
            ),
            'low': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-low",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-low-dlq",
                worker_count=2,
                max_receive_count=3,
                visibility_timeout=300,  # 5 minutes
                max_processing_time=120,
                retry_delay=5
            )
        }
        
        # Total of 12 workers - manageable for connection pooling
        self.total_workers = sum(config.worker_count for config in self.queues.values())
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.total_workers)
        self.shutdown_event = threading.Event()
        
        # Initialize services
        self.redis = redis.Redis(host='redis-host', port=6379, decode_responses=True)
        self.token_manager = DeviceTokenManager()
        
        # Shared circuit breakers for external services
        self.fcm_breaker = SharedCircuitBreaker(self.redis, "fcm", failure_threshold=5, timeout=30)
        self.apns_breaker = SharedCircuitBreaker(self.redis, "apns", failure_threshold=5, timeout=30)
        self.ses_breaker = SharedCircuitBreaker(self.redis, "ses", failure_threshold=3, timeout=60)
        self.sms_breaker = SharedCircuitBreaker(self.redis, "sms", failure_threshold=3, timeout=60)
        
        self.sqs = boto3.client('sqs', region_name='us-east-1')
        
        # Initialize channel handlers with connection limits
        self.channel_handlers = ChannelHandlers()
        self.analytics = AnalyticsBuffer()
        
        # Backpressure monitoring
        self.queue_depth_threshold = 1000
        self.backpressure_active = False
        
    def start_processing(self):
        """Start queue processing with backpressure monitoring"""
        # Monitor queue depth for backpressure
        threading.Thread(target=self._monitor_queue_depth, daemon=True).start()
        
        for priority, config in self.queues.items():
            for _ in range(config.worker_count):
                self.executor.submit(self._process_queue, priority, config)
    
    def _monitor_queue_depth(self):
        """Monitor queue depth and activate backpressure for low priority queues"""
        while not self.shutdown_event.is_set():
            try:
                total_messages = 0
                for config in self.queues.values():
                    response = self.sqs.get_queue_attributes(
                        QueueUrl=config.url,
                        AttributeNames=['ApproximateNumberOfMessages']
                    )
                    total_messages += int(response['Attributes']['ApproximateNumberOfMessages'])
                
                self.backpressure_active = total_messages > self.queue_depth_threshold
                if self.backpressure_active:
                    logger.warning(f"Backpressure activated: {total_messages} messages queued")
                
            except Exception as e:
                logger.error(f"Queue monitoring error: {e}")
            
            time.sleep(30)
    
    def _process_queue(self, priority, config):
        """Process messages from a specific queue with comprehensive error handling"""
        while not self.shutdown_event.is_set():
            try:
                # Apply backpressure to low priority queues
                if self.backpressure_active and priority in ['low', 'medium']:
                    time.sleep(10)
                    continue
                
                response = self.sqs.receive_message(
                    QueueUrl=config.url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,  # Long polling
                    VisibilityTimeoutSeconds=config.visibility_timeout
                )
                
                messages = response.get('Messages', [])
                if not messages:
                    continue
                
                message = messages[0]
                