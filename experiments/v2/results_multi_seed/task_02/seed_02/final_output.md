# Notification System Design for Social App (10M MAU) - CORRECTED

## Executive Summary

This proposal outlines a notification system design for a social app with 10 million monthly active users. **Critical corrections**: Accurate cost projections ($200K+ monthly), realistic SMS strategy (no bulk SMS), proper infrastructure sizing for 100M+ daily notifications, and achievable 8-month timeline with additional staffing requirements.

## 1. Corrected Scale Analysis & Realistic Cost Projections

### 1.1 Accurate Load Estimates
- 10M MAU × 30% daily active = 3M DAU
- Social apps generate 25-40 notifications per active user daily
- **Daily volume: 75M-120M notifications**
- Peak load: 2,000-3,000 notifications/second
- Monthly volume: 2.4B-3.6B notifications

### 1.2 **CORRECTED** Cost Analysis
```
Realistic Monthly Costs:
Push Notifications: $0 (FCM free tier covers this volume)
Email (SendGrid): $2,400-3,600 (120M emails @ $0.02-0.03 each)
SMS: $0 (ELIMINATED - see strategy below)
DynamoDB: $112K writes + $15K reads + $8K storage = $135K
Lambda: $8K-12K (based on 100M+ invocations)
SQS: $2K-3K
Infrastructure (RDS, Redis, monitoring): $8K-12K
Total: $165K-185K monthly
```

**SMS Strategy Change**: SMS eliminated for bulk notifications due to cost ($450K-1.8M monthly). Reserved only for account security (2FA, password resets) with separate budget allocation.

## 2. Corrected Technology Stack for Scale

### 2.1 Revised Architecture
```
Production Stack:
- Queue System: Amazon SQS Standard (not FIFO - see concurrency fix)
- Notification History: Amazon DynamoDB with careful cost management
- User Preferences: PostgreSQL (managed via RDS)
- Cache: Redis Cluster (distributed for Lambda state)
- Processing: AWS Lambda with reserved concurrency
- Load Balancing: Multiple regions to distribute Lambda limits
```

### 2.2 **FIXED** Lambda Concurrency Strategy
```yaml
Lambda Configuration:
  Reserved Concurrency: 3,500 per region (requires limit increase request)
  Regions: us-east-1, us-west-2 (distribute load)
  Function Memory: 512MB (balance cost vs performance)
  Timeout: 30 seconds
  
Concurrency Request Process:
  1. Submit AWS support case for 10,000 concurrent executions
  2. Provide detailed usage patterns and business justification
  3. Timeline: 2-3 weeks for approval
  4. Implement gradual scaling testing
```

## 3. **CORRECTED** Queue Architecture

### 3.1 SQS Standard Queues (Not FIFO)
```
Queue Structure:
- notifications-critical-standard (immediate processing)
- notifications-high-standard (5-minute batching)
- notifications-medium-standard (30-minute batching)
- notifications-low-standard (daily digest)

Rationale for Standard Queues:
- SQS Standard: 3,000+ messages/second (meets our peak requirement)
- SQS FIFO: 300 messages/second (insufficient for critical notifications)
- Trade-off: Potential duplicate delivery vs. sufficient throughput
```

### 3.2 **FIXED** Duplicate Message Handling
```python
import hashlib
import time

class DeduplicationService:
    def __init__(self):
        self.redis_client = redis.Redis(decode_responses=True)
    
    def is_duplicate(self, notification_data):
        """Prevent duplicate processing with Redis-based deduplication"""
        # Create deterministic hash from notification content
        content_hash = hashlib.sha256(
            f"{notification_data['user_id']}-{notification_data['type']}-{notification_data['content']}".encode()
        ).hexdigest()
        
        dedup_key = f"dedup:{content_hash}"
        
        # Use Redis SET with NX (only set if not exists) and EX (expiration)
        result = self.redis_client.set(dedup_key, "1", nx=True, ex=300)  # 5-minute window
        return result is None  # None means key already existed (duplicate)
    
    def mark_processed(self, notification_id):
        """Mark notification as successfully processed"""
        self.redis_client.setex(f"processed:{notification_id}", 3600, "1")
```

## 4. **FIXED** FCM Token Management

### 4.1 Corrected Token Schema
```sql
-- Fixed schema without non-existent device_id
CREATE TABLE fcm_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    token VARCHAR(1024) NOT NULL UNIQUE,
    platform VARCHAR(20) NOT NULL, -- ios, android, web
    app_version VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    
    INDEX idx_user_tokens (user_id, is_active),
    INDEX idx_token_lookup (token)
);
```

### 4.2 **CORRECTED** Token Management Implementation
```python
class FCMTokenManager:
    def register_token(self, user_id, token, platform, app_version=None):
        """Register new FCM token from client"""
        try:
            # Check if token already exists
            existing = self.db.execute(
                "SELECT id FROM fcm_tokens WHERE token = %s AND is_active = true",
                (token,)
            ).fetchone()
            
            if existing:
                # Update last_used timestamp
                self.db.execute(
                    "UPDATE fcm_tokens SET last_used = NOW(), user_id = %s WHERE token = %s",
                    (user_id, token)
                )
            else:
                # Insert new token
                self.db.execute(
                    """INSERT INTO fcm_tokens (user_id, token, platform, app_version) 
                       VALUES (%s, %s, %s, %s)""",
                    (user_id, token, platform, app_version)
                )
                
        except IntegrityError:
            # Handle race condition where token was inserted between check and insert
            pass
    
    def handle_invalid_token(self, token, error_type):
        """Handle FCM errors like NotRegistered, InvalidRegistration"""
        if error_type in ['NotRegistered', 'InvalidRegistration']:
            self.db.execute(
                "UPDATE fcm_tokens SET is_active = false WHERE token = %s",
                (token,)
            )
    
    def get_user_tokens(self, user_id):
        """Get all active tokens for a user"""
        return self.db.execute(
            """SELECT token, platform FROM fcm_tokens 
               WHERE user_id = %s AND is_active = true 
               ORDER BY last_used DESC""",
            (user_id,)
        ).fetchall()
```

## 5. **FIXED** Rate Limiting with Atomic Operations

### 5.1 Corrected Redis Rate Limiting
```python
class AtomicRateLimiter:
    def __init__(self):
        self.redis_client = redis.Redis()
    
    def check_rate_limit(self, user_id, notification_type):
        """Thread-safe rate limiting using Lua script"""
        
        # Lua script for atomic rate limiting
        lua_script = """
        local key = KEYS[1]
        local limit = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local current_time = tonumber(ARGV[3])
        
        -- Remove expired entries
        redis.call('ZREMRANGEBYSCORE', key, 0, current_time - window)
        
        -- Check current count
        local current_count = redis.call('ZCARD', key)
        if current_count >= limit then
            return 0  -- Rate limit exceeded
        end
        
        -- Add current request
        redis.call('ZADD', key, current_time, current_time)
        redis.call('EXPIRE', key, window)
        
        return 1  -- Request allowed
        """
        
        # Get user's rate limit preference
        max_per_hour = self.get_user_rate_limit(user_id, notification_type)
        
        key = f"rate_limit:{user_id}:{notification_type}"
        current_time = time.time()
        
        result = self.redis_client.eval(
            lua_script, 
            1, 
            key, 
            max_per_hour, 
            3600,  # 1 hour window
            current_time
        )
        
        return bool(result)
```

## 6. **CORRECTED** DynamoDB Cost Management

### 6.1 Optimized DynamoDB Schema
```python
# Cost-optimized DynamoDB design
{
    "TableName": "notification_history",
    "KeySchema": [
        {"AttributeName": "user_id_month", "KeyType": "HASH"},  # Partition by user+month
        {"AttributeName": "timestamp_id", "KeyType": "RANGE"}   # Sort by timestamp+uuid
    ],
    "AttributeDefinitions": [
        {"AttributeName": "user_id_month", "AttributeType": "S"},
        {"AttributeName": "timestamp_id", "AttributeType": "S"}
    ],
    "BillingMode": "PROVISIONED",  # More cost-effective at high volume
    "ProvisionedThroughput": {
        "ReadCapacityUnits": 1000,   # ~$116/month
        "WriteCapacityUnits": 2000   # ~$232/month
    },
    "GlobalSecondaryIndexes": [{
        "IndexName": "notification-type-index",
        "KeySchema": [
            {"AttributeName": "notification_type", "KeyType": "HASH"},
            {"AttributeName": "timestamp_id", "KeyType": "RANGE"}
        ],
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 100,
            "WriteCapacityUnits": 2000
        }
    }],
    "StreamSpecification": {
        "StreamEnabled": False  # Disable to reduce costs
    }
}
```

### 6.2 Notification Content Size Limits
```python
class NotificationValidator:
    MAX_TITLE_LENGTH = 100
    MAX_BODY_LENGTH = 500
    MAX_TOTAL_SIZE = 4000  # bytes (DynamoDB item size affects cost)
    
    def validate_and_truncate(self, notification):
        """Enforce size limits to control DynamoDB costs"""
        
        # Truncate title and body
        notification['title'] = notification['title'][:self.MAX_TITLE_LENGTH]
        notification['body'] = notification['body'][:self.MAX_BODY_LENGTH]
        
        # Check total serialized size
        serialized = json.dumps(notification, ensure_ascii=False)
        if len(serialized.encode('utf-8')) > self.MAX_TOTAL_SIZE:
            # Remove optional fields to reduce size
            optional_fields = ['metadata', 'custom_data', 'image_url']
            for field in optional_fields:
                if field in notification:
                    del notification[field]
                    serialized = json.dumps(notification, ensure_ascii=False)
                    if len(serialized.encode('utf-8')) <= self.MAX_TOTAL_SIZE:
                        break
        
        return notification
```

## 7. **FIXED** Circuit Breaker with Persistence

### 7.1 Redis-Backed Circuit Breaker
```python
class PersistentCircuitBreaker:
    def __init__(self, service_name, failure_threshold=5, recovery_timeout=60):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.redis_client = redis.Redis()
        
    def get_state(self):
        """Get circuit breaker state from Redis"""
        state_key = f"circuit_breaker:{self.service_name}"
        state_data = self.redis_client.hgetall(state_key)
        
        if not state_data:
            return {
                'state': 'CLOSED',
                'failure_count': 0,
                'last_failure_time': 0
            }
        
        return {
            'state': state_data.get('state', 'CLOSED'),
            'failure_count': int(state_data.get('failure_count', 0)),
            'last_failure_time': float(state_data.get('last_failure_time', 0))
        }
    
    def update_state(self, state_data):
        """Update circuit breaker state in Redis"""
        state_key = f"circuit_breaker:{self.service_name}"
        self.redis_client.hset(state_key, mapping=state_data)
        self.redis_client.expire(state_key, 86400)  # 24 hour expiry
    
    def call_service(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        state = self.get_state()
        current_time = time.time()
        
        if state['state'] == 'OPEN':
            if current_time - state['last_failure_time'] > self.recovery_timeout:
                state['state'] = 'HALF_OPEN'
                self.update_state(state)
            else:
                raise Exception(f"Circuit breaker OPEN for {self.service_name}")
        
        try:
            result = func(*args, **kwargs)
            
            # Success - reset if we were in HALF_OPEN
            if state['state'] == 'HALF_OPEN':
                state.update({
                    'state': 'CLOSED',
                    'failure_count': 0,
                    'last_failure_time': 0
                })
                self.update_state(state)
            
            return result
            
        except Exception as e:
            state['failure_count'] += 1
            state['last_failure_time'] = current_time
            
            if state['failure_count'] >= self.failure_threshold:
                state['state'] = 'OPEN'
            
            self.update_state(state)
            raise e
```

## 8. **CORRECTED** GDPR and Data Retention

### 8.1 Consistent Data Retention Policy
```sql
-- Unified data retention with user control
CREATE TABLE user_data_retention (
    user_id UUID PRIMARY KEY,
    notification_history_retention_days INTEGER DEFAULT 90,
    preference_data_retention_days INTEGER DEFAULT 2555, -- 7 years
    analytics_retention_days INTEGER DEFAULT 730, -- 2 years
    gdpr_deletion_requested BOOLEAN DEFAULT FALSE,
    gdpr_deletion_date TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 8.2 GDPR Deletion Implementation
```python
class GDPRComplianceService:
    def request_data_deletion(self, user_id):
        """Handle GDPR deletion request"""
        
        # Mark user for deletion
        self.db.execute(
            """UPDATE user_data_retention 
               SET gdpr_deletion_requested = TRUE, 
                   gdpr_deletion_date = NOW() + INTERVAL '30 days'
               WHERE user_id = %s""",
            (user_id,)
        )
        
        # Immediate anonymization of notification history
        self.anonymize_notification_history(user_id)
        
    def anonymize_notification_history(self, user_id):
        """Replace PII with anonymized data"""
        
        # DynamoDB update to remove PII
        user_id_month_keys = self.get_user_partition_keys(user_id)
        
        for partition_key in user_id_month_keys:
            # Query all items for this user partition
            response = self.dynamodb.query(
                TableName='notification_history',
                KeyConditionExpression='user_id_month = :pk',
                ExpressionAttribut