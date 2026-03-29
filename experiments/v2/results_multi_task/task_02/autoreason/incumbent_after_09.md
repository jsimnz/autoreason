# Notification System Design for 10M MAU Social App - REVISED

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design delivers core functionality reliably with clear paths for future scaling.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with JWT-based service authentication
- **Device Token Service**: PostgreSQL with Redis clustering and optimized connection management
- **Channel Handlers**: Parallel processors for push, email, in-app, and SMS with circuit breaker patterns
- **User Preference Service**: Denormalized preference management with versioned caching
- **Template Service**: Jinja2-based content handling with sandboxed execution
- **Analytics Service**: Event-driven tracking with separate data pipeline

### Technology Stack
- **Message Queue**: Amazon SQS with properly configured visibility timeouts
- **Database**: PostgreSQL with optimized connection pooling, Redis Cluster for distributed operations
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with pre-approved rate limits)
- **SMS**: Twilio (with rate limiting and budget enforcement)
- **Infrastructure**: AWS with auto-scaling groups

**Rationale**: Redis clustering eliminates single points of failure while proper connection pooling prevents resource exhaustion. Circuit breakers and exponential backoff ensure graceful degradation.

## 2. Device Token Management with Comprehensive Race Condition Prevention

**Fixes Problem #1: Complete token lifecycle race condition prevention**
**Fixes Problem #3: Redis clustering eliminates single point of failure**

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

-- Indexes for efficient querying and validation
CREATE INDEX idx_device_tokens_user_valid ON device_tokens(user_id) WHERE is_valid = true AND validation_state = 'valid';
CREATE INDEX idx_device_tokens_validation ON device_tokens(validation_state, validation_expires_at);
```

### 2.2 Token Management with Complete Lifecycle Protection
```python
import psycopg2.pool
import redis.sentinel
import uuid
import time
from enum import Enum

class ValidationState(Enum):
    PENDING = 'pending'
    VALID = 'valid'
    INVALID = 'invalid'
    VALIDATING = 'validating'

class DeviceTokenManager:
    def __init__(self):
        # Fix Problem #2: Optimized connection pooling
        self.db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=15,  # Much smaller pool to prevent exhaustion
            host="postgres-host",
            database="notifications",
            user="app_user",
            password="password"
        )
        
        # Fix Problem #3: Redis Cluster for high availability
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
        # Fix Problem #1: Lock entire token lifecycle, not just storage
        lock_key = f"token_lifecycle:{user_id}:{device_id}"
        
        with self.redis.lock(lock_key, timeout=30, blocking_timeout=5):
            conn = self.db_pool.getconn()
            try:
                with conn.cursor() as cursor:
                    # First, check if there's an ongoing validation for this token
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
    
    def mark_token_for_validation(self, user_id, device_id):
        """Atomically claim token for validation to prevent concurrent validation"""
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                # Atomically claim token for validation
                cursor.execute("""
                    UPDATE device_tokens 
                    SET validation_state = %s,
                        validation_worker_id = %s,
                        validation_expires_at = NOW() + INTERVAL '5 minutes'
                    WHERE user_id = %s AND device_id = %s 
                    AND validation_state IN (%s, %s)
                    AND (validation_expires_at IS NULL OR validation_expires_at < NOW())
                    RETURNING token, platform
                """, (
                    ValidationState.VALIDATING.value,
                    self.worker_id,
                    user_id, 
                    device_id,
                    ValidationState.PENDING.value,
                    ValidationState.VALID.value
                ))
                
                result = cursor.fetchone()
                conn.commit()
                return result
        finally:
            self.db_pool.putconn(conn)
    
    def complete_token_validation(self, user_id, device_id, is_valid):
        """Complete validation process atomically"""
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                new_state = ValidationState.VALID.value if is_valid else ValidationState.INVALID.value
                
                cursor.execute("""
                    UPDATE device_tokens 
                    SET validation_state = %s,
                        is_valid = %s,
                        validation_worker_id = NULL,
                        validation_expires_at = NULL,
                        failure_count = CASE WHEN %s THEN 0 ELSE failure_count + 1 END,
                        last_failure_at = CASE WHEN %s THEN NULL ELSE NOW() END
                    WHERE user_id = %s AND device_id = %s 
                    AND validation_worker_id = %s
                """, (new_state, is_valid, is_valid, is_valid, user_id, device_id, self.worker_id))
                
                conn.commit()
                self._invalidate_user_cache(user_id)
        finally:
            self.db_pool.putconn(conn)
    
    def _invalidate_user_cache(self, user_id):
        """Invalidate cache with versioning to prevent race conditions"""
        # Fix Problem #9: Use versioned cache invalidation
        version_key = f"user_tokens_version:{user_id}"
        cache_key = f"user_tokens:{user_id}"
        
        # Increment version and delete cache atomically
        pipe = self.redis.pipeline()
        pipe.incr(version_key)
        pipe.delete(cache_key)
        pipe.execute()
```

## 3. Robust Queue Processing with Proper Resource Management

**Fixes Problem #2: Optimized connection pooling**
**Fixes Problem #4: Correct SQS visibility timeout configuration**
**Fixes Problem #5: Complete notification processing implementation**
**Fixes Problem #11: Exponential backoff and circuit breaker patterns**

### 3.1 SQS Configuration with Proper Timeouts
```python
import boto3
import concurrent.futures
import threading
import time
import random
from dataclasses import dataclass
from circuit_breaker import CircuitBreaker

@dataclass
class QueueConfig:
    url: str
    dlq_url: str
    worker_count: int
    max_receive_count: int
    # Fix Problem #4: Proper visibility timeout configuration
    visibility_timeout: int  # Must be longer than max processing time
    max_processing_time: int

class NotificationProcessor:
    def __init__(self):
        # Fix Problem #4: Configure SQS with appropriate timeouts
        self.queues = {
            'critical': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-critical",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-critical-dlq",
                worker_count=8,  # Reduced to prevent connection exhaustion
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
        
        # Fix Problem #11: Circuit breakers for external services
        self.fcm_breaker = CircuitBreaker(failure_threshold=5, timeout=30)
        self.apns_breaker = CircuitBreaker(failure_threshold=5, timeout=30)
        self.ses_breaker = CircuitBreaker(failure_threshold=3, timeout=60)
        
        self.sqs = boto3.client('sqs', region_name='us-east-1')
        
        # Initialize channel handlers with connection limits
        self.fcm_handler = FCMHandler(max_connections=5)
        self.apns_handler = APNSHandler(max_connections=5)
        self.email_handler = EmailHandler(max_connections=3)
        self.sms_handler = SMSHandler(max_connections=2)
        
    def _process_notification_message(self, message):
        """
        Fix Problem #5: Complete notification processing implementation
        """
        try:
            message_data = json.loads(message['Body'])
            notification_type = message_data.get('type')
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
    
    def _send_push_notification(self, user_id, content):
        """Send push notification with circuit breaker protection"""
        try:
            # Get valid tokens for user
            tokens = self.token_manager.get_valid_tokens(user_id)
            if not tokens:
                return {'success': False, 'error': 'No valid tokens'}
            
            results = []
            
            for token_info in tokens:
                device_id, platform, token, failure_count = token_info
                
                # Skip tokens with recent failures
                if failure_count > 3:
                    continue
                
                try:
                    if platform == 'ios':
                        with self.apns_breaker:
                            result = self.apns_handler.send_notification(token, content)
                    else:  # android
                        with self.fcm_breaker:
                            result = self.fcm_handler.send_notification(token, content)
                    
                    if result.get('success'):
                        # Mark token as validated
                        self.token_manager.complete_token_validation(user_id, device_id, True)
                        results.append({'device_id': device_id, 'success': True})
                    elif result.get('invalid_token'):
                        # Mark token as invalid
                        self.token_manager.complete_token_validation(user_id, device_id, False)
                        results.append({'device_id': device_id, 'success': False, 'error': 'Invalid token'})
                    else:
                        results.append({'device_id': device_id