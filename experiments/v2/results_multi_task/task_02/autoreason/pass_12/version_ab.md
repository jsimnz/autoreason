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

## 2. Device Token Management with Proper Connection Pooling and Token Validation

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
    -- Add validation state for token lifecycle management
    validation_state VARCHAR(20) DEFAULT 'valid' CHECK (validation_state IN ('pending', 'valid', 'invalid')),
    PRIMARY KEY (user_id, device_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Optimized indexes
CREATE INDEX idx_device_tokens_user_valid ON device_tokens(user_id) WHERE is_valid = true AND validation_state = 'valid';
CREATE INDEX idx_device_tokens_validation ON device_tokens(validation_state) WHERE validation_state = 'pending';
```

### 2.2 Robust Token Management with Proper Resource Management
```python
import psycopg2.pool
import redis
import json
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class ValidationState(Enum):
    PENDING = 'pending'
    VALID = 'valid'
    INVALID = 'invalid'

@dataclass
class DeviceToken:
    device_id: str
    platform: str
    token: str
    failure_count: int

class DeviceTokenManager:
    def __init__(self, total_workers=30):
        # Properly sized connection pool for all system workers
        # 30 workers + 10 web handlers + 5 admin/maintenance = 45 connections + overhead
        self.db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=10,
            maxconn=60,  # Generous sizing to prevent connection starvation
            host="postgres-host",
            database="notifications",
            user="app_user",
            password="password",
            connect_timeout=10,
            options="-c statement_timeout=30s"  # Prevent long-running queries
        )
        
        # Simple local Redis for MVP reliability
        self.redis = redis.Redis(
            host='redis-host',
            port=6379,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        self.cache_ttl = 300
        self._lock = threading.RLock()  # For cache coordination
        
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections with proper transaction handling"""
        conn = None
        try:
            conn = self.db_pool.getconn()
            if conn is None:
                raise Exception("Unable to get database connection")
            conn.autocommit = False
            yield conn
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise e
        finally:
            if conn:
                try:
                    if not conn.closed:
                        conn.commit()
                except:
                    conn.rollback()
                finally:
                    self.db_pool.putconn(conn)
    
    def store_token(self, user_id: int, device_id: str, platform: str, token: str) -> bool:
        """Store token with pending validation state for proper lifecycle management"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Store with pending validation state - tokens require validation
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
                    
                    # Cache invalidation within transaction
                    self._invalidate_user_cache_safe(user_id)
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to store token: {e}")
            return False
    
    def get_valid_tokens(self, user_id: int) -> List[DeviceToken]:
        """Get valid, verified tokens with proper cache coordination"""
        cache_key = f"user_tokens:{user_id}"
        
        # Proper cache handling with coordination
        with self._lock:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    token_data = json.loads(cached)
                    return [DeviceToken(**token) for token in token_data]
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
        
        # Query database for valid, verified tokens only
        try:
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
                    
                    rows = cursor.fetchall()
                    tokens = [
                        DeviceToken(
                            device_id=row[0],
                            platform=row[1], 
                            token=row[2],
                            failure_count=row[3]
                        ) for row in rows
                    ]
                    
                    # Cache result with error handling
                    try:
                        token_data = [
                            {
                                'device_id': t.device_id,
                                'platform': t.platform,
                                'token': t.token,
                                'failure_count': t.failure_count
                            } for t in tokens
                        ]
                        self.redis.setex(cache_key, self.cache_ttl, json.dumps(token_data))
                    except Exception as e:
                        logger.warning(f"Cache write error: {e}")
                    
                    return tokens
                    
        except Exception as e:
            logger.error(f"Database error getting tokens: {e}")
            return []
    
    def mark_token_validation_result(self, user_id: int, device_id: str, is_valid: bool) -> bool:
        """Mark token validation result with proper state transitions"""
        try:
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
                    
                    self._invalidate_user_cache_safe(user_id)
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to mark validation result: {e}")
            return False
    
    def mark_token_failure(self, user_id: int, device_id: str) -> bool:
        """Mark token failure with proper transaction handling"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE device_tokens 
                        SET failure_count = failure_count + 1,
                            last_failure_at = NOW(),
                            is_valid = CASE 
                                WHEN failure_count + 1 >= 3 THEN false 
                                ELSE true 
                            END,
                            validation_state = CASE
                                WHEN failure_count + 1 >= 3 THEN %s
                                ELSE validation_state
                            END
                        WHERE user_id = %s AND device_id = %s
                    """, (ValidationState.INVALID.value, user_id, device_id))
                    
                    self._invalidate_user_cache_safe(user_id)
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to mark token failure: {e}")
            return False
    
    def _invalidate_user_cache_safe(self, user_id: int):
        """Safe cache invalidation with error logging"""
        try:
            self.redis.delete(f"user_tokens:{user_id}")
        except Exception as e:
            logger.warning(f"Cache invalidation failed for user {user_id}: {e}")
            # Don't raise - cache failures shouldn't break core functionality
```

## 3. Robust Queue Processing with Realistic Resource Management

### 3.1 Realistic SQS Configuration with Proper Timeouts and Circuit Breakers
```python
import boto3
import concurrent.futures
import threading
import time
import json
import logging
import signal
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class SimpleCircuitBreaker:
    """Simple in-memory circuit breaker for MVP reliability"""
    def __init__(self, name, failure_threshold=5, timeout=30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self._lock = threading.RLock()
    
    def is_open(self):
        with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = CircuitState.HALF_OPEN
                    return False
                return True
            return False
    
    def record_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = CircuitState.CLOSED
    
    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN

@dataclass
class QueueConfig:
    url: str
    dlq_url: str
    worker_count: int
    max_receive_count: int
    visibility_timeout: int
    max_processing_time: int
    retry_delay: int
    batch_size: int

class NotificationProcessor:
    def __init__(self):
        # Realistic visibility timeouts and balanced worker allocation
        self.queues = {
            'critical': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-critical",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-critical-dlq",
                worker_count=6,  # More workers for critical messages
                max_receive_count=3,
                visibility_timeout=120,  # 2 minutes - realistic for processing + retries
                max_processing_time=60,
                retry_delay=5,
                batch_size=1
            ),
            'high': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-high", 
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-high-dlq",
                worker_count=6,
                max_receive_count=3,
                visibility_timeout=90,   # 1.5 minutes
                max_processing_time=45,
                retry_delay=3,
                batch_size=1
            ),
            'medium': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-medium",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-medium-dlq",
                worker_count=8,  # More workers for volume
                max_receive_count=3,
                visibility_timeout=60,   # 1 minute
                max_processing_time=30,
                retry_delay=2,
                batch_size=5  # Batch processing for efficiency
            ),
            'low': QueueConfig(
                url="https://sqs.us-east-1.amazonaws.com/account/notifications-low",
                dlq_url="https://sqs.us-east-1.amazonaws.com/account/notifications-low-dlq",
                worker_count=10,  # Adequate workers for volume
                max_receive_count=3,
                visibility_timeout=45,   # 45 seconds
                max_processing_time=20,
                retry_delay=1,
                batch_size=10  # Higher batching for efficiency
            )
        }
        
        # Total of 30 workers - sized for realistic 10M MAU load
        self.total_workers = sum(config.worker_count for config in self.queues.values())
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.total_workers)
        self.shutdown_event = threading.Event()
        
        # Initialize services
        self.redis = redis.Redis(host='redis-host', port=6379, decode_responses=True)
        self