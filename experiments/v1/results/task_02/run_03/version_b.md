# Notification System Design for Social App (10M MAU) - REVISED

## Executive Summary

This proposal outlines a pragmatic notification system for a social app with 10 million monthly active users, designed to be implemented by 4 backend engineers over 6 months. The system prioritizes operational simplicity and reliability over architectural complexity, using proven technologies that the team can realistically manage.

## 1. System Architecture Overview

### Core Components
- **Notification API**: REST API for triggering notifications
- **Background Workers**: Simple job processors for each delivery channel  
- **Job Queue**: Redis-based queue with job persistence
- **User Preference Service**: Simple key-value preference storage
- **Template Service**: Basic template rendering with fallbacks
- **Monitoring**: Essential metrics and alerting

### Technology Stack
- **Primary Database**: PostgreSQL with proper indexing and partitioning
- **Job Queue**: Redis with Sidekiq/Celery for reliable job processing
- **Cache**: Redis for user preferences and rate limiting  
- **Push Notifications**: Firebase Cloud Messaging (FCM) with proper error handling
- **Email**: SendGrid with realistic volume planning
- **SMS**: Twilio for security-critical notifications only
- **Infrastructure**: AWS with managed services and auto-scaling

**FIXES PROBLEMS**: #1 (removes Kafka complexity), #8 (realistic tech choices for 4-person team)

## 2. Delivery Channels

### 2.1 Push Notifications (Primary Channel)
**Implementation**: Firebase Cloud Messaging with proper token management
- **Token Management**: Daily cleanup of invalid tokens, retry logic for token refresh
- **Rate Limiting**: Respect FCM's 600,000 messages/minute limit with exponential backoff
- **Payload Optimization**: Maximum 4KB payload, compressed JSON structure
- **Platform Differences**: Separate handling for iOS (APNs) and Android specifics

```python
class PushNotificationService:
    def send_notification(self, user_id, message):
        token = self.get_valid_token(user_id)
        if not token:
            return False
            
        payload = {
            "to": token,
            "notification": {
                "title": message.title[:100],  # Enforce limits
                "body": message.body[:200]
            },
            "data": {
                "type": message.type,
                "id": str(message.id)
            }
        }
        
        try:
            response = self.fcm_client.send(payload)
            if response.failure_count > 0:
                self.handle_invalid_tokens(response.results)
            return response.success_count > 0
        except Exception as e:
            self.logger.error(f"FCM error: {e}")
            return False
```

**FIXES PROBLEMS**: #3 (proper FCM handling), #9 (error handling)

### 2.2 Email Notifications (Secondary Channel)
**Implementation**: SendGrid with realistic volume planning
- **Volume Planning**: 1M emails/day capacity (SendGrid Pro plan ~$500/month)
- **Template Management**: Pre-built templates with fallback to plain text
- **List Management**: Automatic unsubscribe handling and bounce processing
- **Delivery Windows**: Batch sending during optimal hours (9 AM - 5 PM recipient time)

### 2.3 In-App Notifications (Polling-Based)
**Implementation**: HTTP polling with efficient caching
- **Polling Strategy**: 60-second intervals for active users, 5-minute for background
- **Storage**: Partitioned PostgreSQL table with 30-day auto-cleanup
- **Caching**: Redis cache for unread notification counts
- **No WebSockets**: Eliminates connection management complexity

```sql
-- Partitioned table for performance
CREATE TABLE notifications (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT,
    read_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Monthly partitions with automatic cleanup
CREATE TABLE notifications_2024_01 PARTITION OF notifications 
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

**FIXES PROBLEMS**: #2 (removes WebSocket complexity), #4 (proper partitioning)

### 2.4 SMS (Security Only)
**Implementation**: Twilio for critical security events
- **Strict Use Cases**: Login from new device, password reset, account recovery
- **Cost Control**: Maximum 1 SMS per user per day
- **Fallback**: Email if SMS fails or user has no phone number

## 3. Simplified Priority and Processing

### 3.1 Priority Levels (Simplified)
```
IMMEDIATE (< 1 minute):
- Security alerts
- Direct messages from verified friends

STANDARD (< 15 minutes):  
- Friend requests, mentions, comments
- Most social interactions

DIGEST (Daily batch at 9 AM local time):
- Weekly summaries, trending content
- Low-priority social updates
```

### 3.2 Processing Strategy
- **No Complex Batching**: Simple time-based processing queues
- **Queue Structure**: Three Redis queues with different processing intervals
- **Worker Allocation**: 2 workers for immediate, 3 for standard, 1 for digest

```python
# Simple queue processing
class NotificationProcessor:
    QUEUES = {
        'immediate': {'delay': 0, 'workers': 2},
        'standard': {'delay': 60, 'workers': 3}, 
        'digest': {'delay': 3600, 'workers': 1}
    }
    
    def process_notification(self, notification):
        queue = self.determine_queue(notification)
        redis.lpush(f"notifications:{queue}", json.dumps(notification))
```

**FIXES PROBLEMS**: #5 (eliminates complex batching), #11 (clear priority definitions)

## 4. User Preference Management (Simplified)

### 4.1 Simplified Preference Schema
```sql
CREATE TABLE user_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_start INTEGER DEFAULT 22, -- Hour of day (0-23)
    quiet_end INTEGER DEFAULT 8,    -- Hour of day (0-23)
    timezone VARCHAR(50) DEFAULT 'UTC',
    email_digest BOOLEAN DEFAULT true,
    security_sms BOOLEAN DEFAULT true,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Separate table for granular preferences (optional)
CREATE TABLE notification_type_preferences (
    user_id BIGINT,
    notification_type VARCHAR(50),
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT false,
    PRIMARY KEY (user_id, notification_type)
);

-- Critical indexes
CREATE INDEX idx_user_prefs_lookup ON user_preferences(user_id);
CREATE INDEX idx_notification_type_prefs ON notification_type_preferences(user_id, notification_type);
```

### 4.2 Caching Strategy
- **Cache Duration**: 5 minutes (not 30) to respect user preference changes
- **Cache Key Strategy**: Simple user_id-based keys
- **Fallback**: Default preferences if cache/DB unavailable

```python
class PreferenceService:
    def get_preferences(self, user_id):
        cache_key = f"prefs:{user_id}"
        prefs = redis.get(cache_key)
        
        if not prefs:
            prefs = self.db.get_user_preferences(user_id)
            redis.setex(cache_key, 300, json.dumps(prefs))  # 5 min cache
            
        return json.loads(prefs) if prefs else self.default_preferences()
```

**FIXES PROBLEMS**: #4 (proper indexing), #12 (simplified schema, shorter cache duration)

## 5. Infrastructure Choices (Realistic)

### 5.1 Job Queue: Redis + Background Workers
**Rationale**: 
- Redis handles 100K+ jobs/minute with proper configuration
- Sidekiq (Ruby) or Celery (Python) provide reliability with job persistence
- Much simpler than Kafka with adequate performance for our scale
- Team can manage Redis operations easily

**Queue Configuration**:
```python
# Redis configuration for job persistence
redis_config = {
    'host': 'redis-cluster.aws.com',
    'port': 6379,
    'db': 0,
    'socket_keepalive': True,
    'socket_keepalive_options': {},
    'connection_pool_kwargs': {
        'max_connections': 100,
        'retry_on_timeout': True
    }
}
```

### 5.2 Database: PostgreSQL with Partitioning
**PostgreSQL Optimizations**:
- Monthly partitions for notification history
- Proper indexing on user_id and created_at
- Connection pooling with PgBouncer
- Read replicas for analytics queries

### 5.3 Deployment Architecture
```
Application Load Balancer
├── Notification API (3 instances, auto-scaling 2-10)
├── Background Workers  
│   ├── Immediate Queue Workers (2 instances)
│   ├── Standard Queue Workers (3 instances)
│   └── Digest Queue Workers (1 instance)
└── Redis Cluster (3 nodes with failover)
```

### 5.4 Realistic Cost Estimates (Monthly)
- **SendGrid (1M emails/day)**: ~$500
- **Twilio (5K SMS/month)**: ~$40
- **Firebase**: Free tier sufficient for push notifications
- **AWS Infrastructure**: 
  - EC2 instances (auto-scaling): ~$600
  - RDS PostgreSQL (Multi-AZ): ~$400
  - ElastiCache Redis: ~$200
  - Load Balancer, data transfer: ~$150
- **Total**: ~$1,890/month

**FIXES PROBLEMS**: #6 (realistic cost estimates), #1 (eliminates Kafka costs)

## 6. Failure Handling & Reliability (Production-Ready)

### 6.1 Retry Strategy with Circuit Breaker
```python
class NotificationRetryHandler:
    def __init__(self):
        self.max_retries = 3
        self.retry_delays = [30, 300, 1800]  # 30s, 5m, 30m
        self.circuit_breaker = CircuitBreaker()
    
    def send_with_retry(self, notification, channel):
        if self.circuit_breaker.is_open(channel):
            return self.try_fallback_channel(notification)
            
        for attempt in range(self.max_retries):
            try:
                result = self.send_notification(notification, channel)
                if result:
                    self.circuit_breaker.record_success(channel)
                    return True
                    
            except Exception as e:
                self.circuit_breaker.record_failure(channel)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delays[attempt])
                    
        return self.handle_final_failure(notification)

class CircuitBreaker:
    def __init__(self):
        self.failure_counts = {}
        self.last_failure_times = {}
        self.failure_threshold = 10  # failures per 5 minutes
        self.timeout = 300  # 5 minutes
    
    def is_open(self, service):
        now = time.time()
        if service in self.last_failure_times:
            if now - self.last_failure_times[service] > self.timeout:
                self.failure_counts[service] = 0
                return False
        return self.failure_counts.get(service, 0) >= self.failure_threshold
```

### 6.2 Graceful Degradation
1. **Push notification fails** → Try email if user has email preferences enabled
2. **Email fails** → Store for retry, show in-app notification
3. **All channels fail** → Store in failed_notifications table for manual review
4. **Database unavailable** → Use default preferences, log to file system

### 6.3 Monitoring & Alerting (Essential Metrics Only)
**Key Metrics**:
- Successful delivery rate per channel (measured at API level)
- Queue depth and processing lag
- Failed job count in dead letter queue
- Circuit breaker state changes

**Alerts** (PagerDuty integration):
- Queue depth > 1000 messages for immediate queue
- Failed job rate > 5% over 10 minutes
- Any circuit breaker opens
- Database connection pool exhaustion

**FIXES PROBLEMS**: #7 (proper circuit breaker), #10 (focused monitoring), #13 (proper retry logic)

## 7. Implementation Timeline (Realistic)

### Month 1: Foundation & Learning
- Set up basic Redis job queue infrastructure
- Implement user preference service with PostgreSQL
- Create simple notification API endpoints
- **Team Learning**: Redis operations, job queue patterns

### Month 2: Push Notifications
- Integrate Firebase Cloud Messaging with proper error handling
- Implement token management and cleanup processes
- Build retry logic and basic monitoring
- **Testing**: Load testing with realistic message volumes

### Month 3: Email & SMS Channels
- Integrate SendGrid with template management
- Add Twilio for security SMS (limited scope)
- Implement preference-based channel selection
- **Security**: Add API authentication and rate limiting

### Month 4: In-App & Polish
- Build in-app notification polling system
- Implement partitioned storage with cleanup
- Add comprehensive error handling and logging
- **Performance**: Database optimization and indexing

### Month 5: Production Preparation
- Security audit and penetration testing
- Disaster recovery procedures and runbooks
- Performance testing at full scale
- **Compliance**: Basic GDPR compliance for EU users

### Month 6: Deployment & Monitoring
- Gradual production rollout (5% → 25% → 100% over 3 weeks)
- Monitor key metrics and tune performance
- Team training on operations and troubleshooting
- **Documentation**: Complete operational procedures

**FIXES PROBLEMS**: #8 (realistic timeline with learning time and buffers)

## 8. Security and Compliance

### 8.1 Authentication & Authorization
- API key authentication for internal services
- Rate limiting: 100 requests/minute per API key
- Input validation and sanitization for all notification content

### 8.2 Data Protection
- Encrypt notification content in Redis queues (AES-256)
- Audit log for all notification sends (user_id, type, timestamp)
- GDPR compliance: User data deletion within 30 days of request

### 8.3 Abuse Prevention
- Per-user rate limits: Maximum 10 notifications/hour
- Content filtering for spam detection
- Automatic disable for users with high bounce rates

```python
class SecurityMiddleware:
    def validate_notification(self, notification):
        # Rate limiting
        if self.exceeded_rate_limit(notification.user_id):
            raise RateLimitExceeded()
            
        # Content validation
        if self.contains_spam(notification.content):
            raise ContentViolation()
            
        # User verification
        if not self.is_valid_user(notification.user_id):
            raise InvalidUser()
```

**FIXES PROBLEMS**: #14 (security and compliance), #9 (authentication)

## 9. Success Metrics (Measurable)

### 9.1 Technical Metrics
- **System Availability**: 99.5% uptime (allows for maintenance windows)
- **Message Processing**: 95% of messages processed within SLA times
- **Error Rate**: <2% failed deliveries due to system errors
- **Queue Performance**: Average queue depth <100 messages

### 9.2 Business Metrics
- **Delivery Success**: >90% successful delivery to intended channel
- **User Engagement**: Measure click-through rates for each notification type
- **Preference Adoption**: Track users who customize notification preferences
- **Cost Efficiency**: Stay within $2000/month operational budget

### 9.3 Operational Metrics
- **Mean Time to Recovery**: <30 minutes for system outages
- **Alert Response**: <5 minutes response to critical alerts
- **Documentation Coverage**: 100% of procedures documented
- **Team Knowledge**: All 4 engineers can handle basic operations

**FIXES PROBLEMS**: #10 (measurable metrics with clear definitions)

## 10. Key Tradeoffs and Rationale

### 10.1 Redis vs. Kafka
**Decision**: Redis-based job queues
**Rationale**: Redis provides adequate throughput (100K+ jobs/minute) with much lower operational complexity. A 4-person team can manage Redis effectively, while Kafka would require dedicated expertise.