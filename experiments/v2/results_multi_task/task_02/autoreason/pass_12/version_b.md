# Notification System Design for 10M MAU Social App - REVISED

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

## 2. Device Token Management with Proper Connection Pooling

**Fixes Problems**: #1 (Connection Pool Undersizing), #4 (Infinite Pending State), #5 (Cache Invalidation), #8 (Transaction Scope)

### 2.1 PostgreSQL Storage with Automatic Token Validation
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
    PRIMARY KEY (user_id, device_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Optimized indexes
CREATE INDEX idx_device_tokens_user_valid ON device_tokens(user_id) WHERE is_valid = true;
```

### 2.2 Properly Sized Token Management with Atomic Operations
```python
import psycopg2.pool
import redis
import json
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Tuple, Optional

@dataclass
class DeviceToken:
    device_id: str
    platform: str
    token: str
    failure_count: int

class DeviceTokenManager:
    def __init__(self, total_workers=30):  # Account for all workers in system
        # **FIXES PROBLEM #1**: Properly sized connection pool for all system workers
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
        """Context manager for database connections with proper cleanup"""
        conn = None
        try:
            conn = self.db_pool.getconn()
            if conn is None:
                raise Exception("Unable to get database connection")
            # **FIXES PROBLEM #8**: Proper transaction scope with rollback on error
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
        """**FIXES PROBLEM #4**: Store token as immediately valid (no pending state)"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Simple atomic upsert - tokens are immediately valid for MVP
                    query = """
                        INSERT INTO device_tokens (
                            user_id, device_id, platform, token, updated_at, 
                            is_valid, failure_count
                        )
                        VALUES (%s, %s, %s, %s, NOW(), true, 0)
                        ON CONFLICT (user_id, device_id)
                        DO UPDATE SET 
                            token = EXCLUDED.token,
                            platform = EXCLUDED.platform,
                            updated_at = NOW(),
                            is_valid = true,
                            failure_count = 0,
                            last_failure_at = NULL
                    """
                    cursor.execute(query, (user_id, device_id, platform, token))
                    
                    # **FIXES PROBLEM #5**: Cache invalidation within transaction
                    self._invalidate_user_cache_safe(user_id)
                    return True
                    
        except Exception as e:
            print(f"Failed to store token: {e}")
            return False
    
    def get_valid_tokens(self, user_id: int) -> List[DeviceToken]:
        """Get valid tokens with proper cache invalidation handling"""
        cache_key = f"user_tokens:{user_id}"
        
        # **FIXES PROBLEM #5**: Proper cache miss handling with coordination
        with self._lock:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    token_data = json.loads(cached)
                    return [DeviceToken(**token) for token in token_data]
            except Exception as e:
                print(f"Cache read error: {e}")
        
        # Query database for valid tokens
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT device_id, platform, token, failure_count
                        FROM device_tokens 
                        WHERE user_id = %s AND is_valid = true
                        ORDER BY updated_at DESC
                    """, (user_id,))
                    
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
                        print(f"Cache write error: {e}")
                    
                    return tokens
                    
        except Exception as e:
            print(f"Database error getting tokens: {e}")
            return []
    
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
                            END
                        WHERE user_id = %s AND device_id = %s
                    """, (user_id, device_id))
                    
                    # Cache invalidation within transaction
                    self._invalidate_user_cache_safe(user_id)
                    return True
                    
        except Exception as e:
            print(f"Failed to mark token failure: {e}")
            return False
    
    def _invalidate_user_cache_safe(self, user_id: int):
        """**FIXES PROBLEM #5**: Safe cache invalidation with error logging"""
        try:
            self.redis.delete(f"user_tokens:{user_id}")
        except Exception as e:
            print(f"Cache invalidation failed for user {user_id}: {e}")
            # Don't raise - cache failures shouldn't break core functionality
```

## 3. Robust Queue Processing with Realistic Resource Management

**Fixes Problems**: #3 (SQS Timeout Configuration), #6 (Queue Backpressure), #11 (Priority Queue Design), #10 (Resource Cleanup)

### 3.1 Realistic SQS Configuration with Proper Timeouts
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
        # **FIXES PROBLEM #3 & #11**: Realistic visibility timeouts and balanced worker allocation
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
                worker_count=10,  # **FIXES PROBLEM #11**: Adequate workers for volume
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
        self.token_manager = DeviceTokenManager(total_workers=self.total_workers)
        
        # Simple in-memory circuit breakers for MVP (fixes race condition issues)
        self.circuit_breakers = self._init_circuit_breakers()
        
        self.sqs = boto3.client('sqs', region_name='us-east-1')
        
        # Initialize channel handlers and analytics
        self.channel_handlers = ChannelHandlers()
        self.analytics = SimpleAnalyticsBuffer()  # Implemented below
        
        # **FIXES PROBLEM #6**: Improved backpressure with gradual throttling
        self.queue_depth_threshold = 5000  # Higher threshold
        self.severe_threshold = 10000      # Severe backpressure threshold
        self.backpressure_level = 0        # 0=none, 1=light, 2=severe
        
        # **FIXES PROBLEM #10**: Proper shutdown handling
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _init_circuit_breakers(self):
        """Initialize simple in-memory circuit breakers (fixes race conditions)"""
        return {
            'fcm': SimpleCircuitBreaker("fcm", failure_threshold=5, timeout=30),
            'apns': SimpleCircuitBreaker("apns", failure_threshold=5, timeout=30), 
            'ses': SimpleCircuitBreaker("ses", failure_threshold=3, timeout=60),
            'sms': SimpleCircuitBreaker("sms", failure_threshold=3, timeout=60)
        }
    
    def start_processing(self):
        """Start queue processing with improved backpressure monitoring"""
        # **FIXES PROBLEM #6**: More frequent monitoring with gradual response
        threading.Thread(target=self._monitor_queue_depth, daemon=True).start()
        
        for priority, config in self.queues.items():
            for worker_id in range(config.worker_count):
                self.executor.submit(self._process_queue, priority, config, worker_id)
    
    def _monitor_queue_depth(self):
        """**FIXES PROBLEM #6**: Gradual backpressure with faster monitoring"""
        while not self.shutdown_event.is_set():
            try:
                total_messages = 0
                for config in self.queues.values():
                    response = self.sqs.get_queue_attributes(
                        QueueUrl=config.url,
                        AttributeNames=['ApproximateNumberOfMessages']
                    )
                    total_messages += int(response['Attributes']['ApproximateNumberOfMessages'])
                
                # Gradual backpressure levels
                if total_messages > self.severe_threshold:
                    self.backpressure_level = 2
                    logger.warning(f"Severe backpressure: {total_messages} messages")
                elif total_messages > self.queue_depth_threshold:
                    self