# Notification System Design for Social App (10M MAU) - FINAL

## Executive Summary

This proposal outlines a scalable notification system for a social app with 10 million monthly active users, designed to be implemented by 4 backend engineers over 6 months. The system prioritizes operational simplicity and reliability while maintaining the scalability needed for 10M MAU, using proven technologies that the team can realistically manage.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator for all notifications
- **Background Workers**: Specialized job processors for each delivery channel  
- **Job Queue**: Redis-based queue with job persistence and horizontal scaling
- **User Preference Service**: Manages user notification settings with caching
- **Template Engine**: Dynamic content generation with fallbacks
- **Analytics & Monitoring**: Delivery tracking and system health

### Technology Stack
- **Primary Database**: PostgreSQL with partitioning and proper indexing
- **Job Queue**: Redis with Sidekiq/Celery for reliable job processing
- **Cache**: Redis for user preferences and rate limiting  
- **Push Notifications**: Firebase Cloud Messaging (FCM) with proper error handling
- **Email**: SendGrid with realistic volume planning
- **SMS**: Twilio for security-critical notifications only
- **Infrastructure**: AWS with managed services and auto-scaling

**Rationale for Change**: Replaced Kafka with Redis-based job queues to reduce operational complexity while maintaining adequate performance for our scale (Redis handles 100K+ jobs/minute). A 4-person team can manage Redis effectively, while Kafka would require dedicated expertise and operational overhead that exceeds our team capacity.

## 2. Delivery Channels

### 2.1 Push Notifications (Primary Channel)
**Implementation**: Firebase Cloud Messaging with comprehensive error handling
- **Rationale**: Single SDK for iOS/Android, reliable delivery, free tier supports our scale
- **Token Management**: Daily cleanup of invalid tokens, retry logic for token refresh
- **Rate Limiting**: Respect FCM's 600,000 messages/minute limit with exponential backoff
- **Message Types**: 
  - Immediate: Friend requests, mentions, direct messages
  - Batched: Weekly digest, trending content
- **Payload Optimization**: Maximum 4KB payload, compressed JSON structure

```python
class PushNotificationService:
    def send_notification(self, user_id, message):
        token = self.get_valid_token(user_id)
        if not token:
            return False
            
        payload = {
            "to": token,
            "notification": {
                "title": message.title[:100],  # Enforce FCM limits
                "body": message.body[:200]
            },
            "data": {
                "post_id": str(message.post_id),
                "user_id": str(message.user_id),
                "notification_type": message.type
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

### 2.2 Email Notifications (Secondary Channel)
**Implementation**: SendGrid with realistic volume planning
- **Use Cases**: 
  - Weekly digest (batched)
  - Security alerts (immediate)
  - Re-engagement campaigns (scheduled)
- **Volume Planning**: 1M emails/day capacity (SendGrid Pro plan)
- **Template Categories**: Transactional, marketing, security with fallback to plain text
- **List Management**: Automatic unsubscribe handling and bounce processing

### 2.3 In-App Notifications (Polling-Based)
**Implementation**: HTTP polling with efficient caching and partitioned storage
- **Polling Strategy**: 60-second intervals for active users, 5-minute for background
- **Storage**: Partitioned PostgreSQL table with 30-day auto-cleanup
- **Caching**: Redis cache for unread notification counts
- **No WebSockets**: Eliminates connection management complexity

```sql
-- Partitioned table for performance at 10M MAU scale
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

-- Critical indexes for 10M user queries
CREATE INDEX idx_notifications_user_unread ON notifications_2024_01 (user_id, created_at) WHERE read_at IS NULL;
```

**Rationale for Change**: Removed WebSocket complexity which would require connection state management, load balancer sticky sessions, and horizontal scaling challenges. HTTP polling with proper caching provides adequate real-time experience with much lower operational complexity.

### 2.4 SMS (Critical Only)
**Implementation**: Twilio for critical security events
- **Strict Use Cases**: 
  - Security alerts (login from new device)
  - Password reset verification
  - Account recovery
- **Cost Control**: Maximum 1 SMS per user per day, <1% of user base
- **Fallback**: Email if SMS fails or user has no phone number

## 3. Priority and Batching Logic

### 3.1 Priority Levels (Streamlined)
```
CRITICAL (0-1 minute delay):
- Security alerts
- Payment notifications
- Direct messages from close friends

HIGH (1-15 minute delay):
- Friend requests
- Comments on user's posts
- Mentions

MEDIUM (15-60 minute delay):
- Likes on posts
- New follower notifications
- Group activity updates

LOW (Daily digest at 9 AM local time):
- Trending content
- Suggested friends
- Weekly summaries
```

### 3.2 Batching Strategy (Simplified but Effective)
**Time-based Processing**:
- CRITICAL: No batching, immediate processing
- HIGH: Process every 5 minutes in micro-batches
- MEDIUM: Process every 30 minutes with user-level batching
- LOW: Daily digest processing

**User-based Batching for MEDIUM/LOW**:
- Combine similar notification types (e.g., "5 people liked your post")
- Maximum 3 notifications per batch to avoid spam
- Respect user quiet hours (default: 10 PM - 8 AM local time)

```python
class NotificationProcessor:
    QUEUES = {
        'critical': {'delay': 0, 'batch_size': 1, 'workers': 2},
        'high': {'delay': 300, 'batch_size': 1, 'workers': 3},
        'medium': {'delay': 1800, 'batch_size': 5, 'workers': 2},
        'low': {'delay': 86400, 'batch_size': 10, 'workers': 1}
    }
    
    def should_batch(self, notification):
        return (
            notification.priority in ['MEDIUM', 'LOW'] and
            not self.in_quiet_hours(notification.user_id) and
            self.get_recent_count(notification.user_id) < 3
        )
```

**Rationale for Change**: Kept the sophisticated batching logic from Version A as it's essential for user experience at 10M MAU scale, but simplified the implementation to use clear time-based processing windows rather than complex real-time batching algorithms.

## 4. User Preference Management

### 4.1 Preference Schema (Optimized)
```sql
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME DEFAULT '22:00:00',
    quiet_hours_end TIME DEFAULT '08:00:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    preferences JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- JSONB structure for granular preferences
{
  "mentions": {"push": true, "email": false, "sms": false},
  "friend_requests": {"push": true, "email": true, "sms": false},
  "likes": {"push": false, "email": false, "sms": false},
  "security": {"push": true, "email": true, "sms": true}
}

-- Critical indexes for 10M user scale
CREATE INDEX idx_user_prefs_lookup ON user_notification_preferences(user_id);
CREATE INDEX idx_user_prefs_updated ON user_notification_preferences(updated_at);
```

### 4.2 Caching Strategy (Balanced)
```python
class PreferenceService:
    def get_user_preferences(self, user_id):
        cache_key = f"prefs:{user_id}"
        prefs = redis.get(cache_key)
        
        if not prefs:
            prefs = self.db.get_preferences(user_id)
            redis.setex(cache_key, 300, json.dumps(prefs))  # 5-minute cache
            
        return json.loads(prefs) if prefs else self.default_preferences()
    
    def should_send_notification(self, user_id, notification_type, channel):
        prefs = self.get_user_preferences(user_id)
        return prefs.get('preferences', {}).get(notification_type, {}).get(channel, self.get_default(notification_type, channel))
```

**Rationale for Change**: Kept the sophisticated JSONB preference structure from Version A for flexibility at scale, but reduced cache TTL from 30 minutes to 5 minutes to better respect user preference changes, and added proper indexing strategy.

## 5. Infrastructure Choices

### 5.1 Job Queue: Redis with Horizontal Scaling
**Rationale**: 
- Redis handles 100K+ jobs/minute with proper configuration
- Sidekiq (Ruby) or Celery (Python) provide reliability with job persistence
- Much simpler operational model than Kafka for 4-person team
- Can scale horizontally with Redis Cluster when needed

**Queue Configuration**:
```python
# Redis configuration optimized for job processing
REDIS_CONFIG = {
    'host': 'elasticache-cluster.region.amazonaws.com',
    'port': 6379,
    'db': 0,
    'socket_keepalive': True,
    'connection_pool_kwargs': {
        'max_connections': 50,
        'retry_on_timeout': True
    }
}

# Queue structure by priority
QUEUE_STRUCTURE = {
    'notifications:critical': {'workers': 2, 'concurrency': 10},
    'notifications:high': {'workers': 3, 'concurrency': 15},
    'notifications:medium': {'workers': 2, 'concurrency': 10},
    'notifications:low': {'workers': 1, 'concurrency': 5}
}
```

### 5.2 Database: PostgreSQL with Partitioning
**PostgreSQL** (Primary):
- User preferences with JSONB flexibility
- Partitioned notification history (monthly partitions)
- Audit logs with proper indexing

**Redis** (Cache + Queue):
- User preferences (5-minute TTL)
- Rate limiting counters
- Job queue with persistence

### 5.3 Deployment Architecture
```
Application Load Balancer
├── Notification API (3 instances, auto-scaling 2-10)
├── Background Workers  
│   ├── Critical Queue Workers (2 instances)
│   ├── High Priority Workers (3 instances)
│   ├── Medium Priority Workers (2 instances)
│   └── Low Priority Workers (1 instance)
└── Redis Cluster (3 nodes with failover)
```

### 5.4 Cost Estimates (Monthly)
- **SendGrid (1M emails/day)**: ~$500
- **Twilio (5K SMS/month)**: ~$40
- **Firebase**: Free tier sufficient
- **AWS Infrastructure**: 
  - EC2 instances (auto-scaling): ~$600
  - RDS PostgreSQL (Multi-AZ): ~$400
  - ElastiCache Redis: ~$200
  - Load Balancer, data transfer: ~$150
- **Total**: ~$1,890/month

**Rationale for Change**: Replaced Kafka costs (~$500) with additional AWS infrastructure costs for Redis scaling, resulting in similar total cost but much lower operational complexity.

## 6. Failure Handling & Reliability

### 6.1 Retry Strategy with Circuit Breaker
```python
class NotificationRetryHandler:
    RETRY_DELAYS = [30, 300, 1800, 3600]  # 30s, 5m, 30m, 1h
    MAX_RETRIES = 4
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=10,  # failures per 5 minutes
            timeout=300  # 5-minute timeout
        )
    
    def send_with_retry(self, notification, channel):
        if self.circuit_breaker.is_open(channel):
            return self.try_fallback_channel(notification)
            
        for attempt in range(self.MAX_RETRIES):
            try:
                result = self.send_notification(notification, channel)
                if result:
                    self.circuit_breaker.record_success(channel)
                    return True
                    
            except Exception as e:
                self.circuit_breaker.record_failure(channel)
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAYS[attempt]
                    self.schedule_retry(notification, delay)
                    
        return self.send_to_dlq(notification)
```

### 6.2 Dead Letter Queue (DLQ) and Graceful Degradation
- Failed notifications after max retries go to DLQ for manual investigation
- **Channel Failover**: Push fails → Email (if enabled) → In-app notification
- **Database Failures**: Use cached preferences with fallback to critical-only notifications
- **Queue Failures**: Direct synchronous delivery for critical notifications only

### 6.3 Monitoring & Alerting
**Key Metrics**:
- Delivery success rate per channel (target: >95%)
- Average delivery time per priority level
- Queue depth and processing lag (Redis queue monitoring)
- Circuit breaker state changes
- Error rates and retry counts

**Critical Alerts**:
- Delivery success rate < 90% for any channel
- Queue lag > 5 minutes for critical notifications
- DLQ message count > 100/hour
- Circuit breaker opens for any channel

**Rationale**: Kept the comprehensive retry and circuit breaker logic from Version A as it's essential for reliability at 10M MAU scale, but adapted it to work with Redis-based job queues.

## 7. Implementation Timeline (6 Months)

### Month 1-2: Foundation
- Set up Redis job queue infrastructure with proper persistence
- Implement user preference service with PostgreSQL and caching
- Create notification service core with priority handling
- Develop push notification channel with FCM integration and error handling

### Month 3-4: Channel Implementation
- Implement email channel with SendGrid and template management
- Build in-app notification system with partitioned storage and polling
- Add SMS channel with strict security-only controls
- Create batching logic and user preference filtering

### Month 5: Advanced Features & Reliability
- Implement comprehensive retry mechanisms and circuit breakers
- Build monitoring dashboard and alerting system
- Add template engine for dynamic content with fallbacks
- Performance optimization and load testing at scale

### Month 6: Production & Operations
- Security audit and compliance review (GDPR basics)
- Production deployment with gradual rollout (5% → 25% → 100%)
- Create comprehensive documentation and operational runbooks
- Team training on Redis operations and troubleshooting

**Rationale**: Kept the 6-month timeline from Version A as it provides adequate buffer for a system serving 10M MAU, but adjusted milestones to account for Redis learning curve and operational procedures.

## 8. Key Tradeoffs and Rationale

### 8.1 Redis vs. Kafka
**Decision**: Redis-based job queues with horizontal scaling capability
**Rationale**: Redis provides adequate throughput (100K+ jobs/minute) with much lower operational complexity. For a 4-person team serving 10M MAU, operational simplicity is more valuable than theoretical maximum throughput. Redis Cluster can scale horizontally if needed.

### 8.2 WebSocket vs. HTTP Polling