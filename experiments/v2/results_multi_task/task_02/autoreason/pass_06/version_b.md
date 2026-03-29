# Notification System Design for 10M MAU Social App - REVISED

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design acknowledges significant limitations requiring future investment while delivering core functionality reliably.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with proper JWT authentication and service-to-service auth
- **Device Token Service**: PostgreSQL-primary token management with Redis caching
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS with dead letter queues
- **User Preference Service**: PostgreSQL-based preference management with Redis caching
- **Template Service**: Content handling with DOMPurify-based HTML sanitization
- **Analytics Service**: Aggregated delivery tracking with GDPR-compliant data collection

### Technology Stack
- **Message Queue**: Amazon SQS with dead letter queues and weighted fair queuing
- **Database**: PostgreSQL with read replicas, Redis for caching only
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with pre-approved rate limits)
- **SMS**: Twilio (with rate limiting and budget enforcement)
- **Infrastructure**: AWS with auto-scaling groups

## 2. Device Token Management

**Fixes Problem #1: Eliminates race conditions by using PostgreSQL as primary storage with atomic operations**

### 2.1 PostgreSQL-Primary Token Storage
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

### 2.2 Token Management with Atomic Operations
```python
class DeviceTokenManager:
    def __init__(self):
        self.db = PostgreSQLConnection()
        self.redis = RedisConnection()
        self.cache_ttl = 300  # 5 minutes
        
    def store_token(self, user_id, device_id, platform, token):
        """Store token with atomic upsert"""
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
        
    def mark_token_invalid(self, user_id, device_id, failure_reason=None):
        """Atomically mark token as invalid and update failure count"""
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

## 3. Queue Architecture with Fair Processing

**Fixes Problem #2: Implements weighted fair queuing to prevent starvation**

### 3.1 Weighted Fair Queue Processing
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
        
    def calculate_realistic_throughput(self):
        # Actual throughput = inflight_limit / processing_time
        throughput_per_queue = self.sqs_inflight_limit / self.avg_processing_time_seconds
        total_throughput = throughput_per_queue * 4  # 4 priority queues
        
        # Account for failure retries (20% failure rate assumption)
        effective_throughput = total_throughput * 0.8
        
        return {
            "max_messages_per_second": int(effective_throughput),
            "daily_capacity": int(effective_throughput * 86400),
            "required_for_10m_mau": 5000000,  # 5M daily notifications
            "capacity_sufficient": effective_throughput * 86400 > 5000000
        }
```

## 4. In-App Notifications with Efficient Storage

**Fixes Problem #3: Uses single table storage to eliminate fan-out and memory bloat**

### 4.1 Efficient PostgreSQL Storage
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

-- Delivery tracking table (separate from notification storage)
CREATE TABLE notification_deliveries (
    notification_id UUID REFERENCES user_notifications(id),
    device_id VARCHAR(255) NOT NULL,
    delivered_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (notification_id, device_id)
);

CREATE INDEX idx_deliveries_device ON notification_deliveries(device_id, delivered_at);
```

### 4.2 Efficient Notification Service
```python
class InAppNotificationService:
    def __init__(self):
        self.db = PostgreSQLConnection()
        self.redis = RedisConnection()
        
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
        """Get notifications with delivery tracking"""
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
        
        # Mark as delivered for this device
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

## 5. Authentication Implementation

**Fixes Problem #4: Implements proper JWT validation and service authentication**

### 5.1 JWT Authentication Service
```python
import jwt
from datetime import datetime, timedelta

class AuthenticationService:
    def __init__(self, secret_key, algorithm='HS256'):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry_hours = 24
        
    def validate_jwt_token(self, token):
        """Validate JWT token with proper error handling"""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"require_exp": True}
            )
            
            # Check if token is expired
            exp_timestamp = payload.get('exp')
            if exp_timestamp and datetime.utcnow().timestamp() > exp_timestamp:
                raise jwt.ExpiredSignatureError("Token has expired")
                
            return {
                'valid': True,
                'user_id': payload.get('user_id'),
                'device_id': payload.get('device_id'),
                'expires_at': exp_timestamp
            }
            
        except jwt.ExpiredSignatureError:
            return {'valid': False, 'error': 'token_expired'}
        except jwt.InvalidTokenError:
            return {'valid': False, 'error': 'invalid_token'}
            
    def generate_service_token(self, service_name):
        """Generate service-to-service authentication token"""
        payload = {
            'service': service_name,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=1)
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
    def validate_service_token(self, token, expected_service=None):
        """Validate service-to-service token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if expected_service and payload.get('service') != expected_service:
                return {'valid': False, 'error': 'unauthorized_service'}
                
            return {'valid': True, 'service': payload.get('service')}
            
        except jwt.InvalidTokenError:
            return {'valid': False, 'error': 'invalid_service_token'}

# Middleware for Flask/FastAPI
class AuthMiddleware:
    def __init__(self, auth_service):
        self.auth_service = auth_service
        
    def require_user_auth(self, request):
        """Middleware to validate user JWT tokens"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return {'error': 'missing_authorization'}, 401
            
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        result