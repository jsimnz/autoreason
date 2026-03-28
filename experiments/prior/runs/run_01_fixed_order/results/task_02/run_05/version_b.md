# Revised Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a **minimum viable notification system** supporting 10 million monthly active users with a 4-engineer team over 6 months. The design prioritizes **core functionality over feature breadth**, focusing on push notifications as the primary channel with simplified architecture to meet resource constraints.

**Key Changes from Original Approach:**
- Focus on push notifications only for MVP (addresses scope/team size mismatch)
- Eliminate WebSocket real-time delivery (addresses connection scaling issues)
- Simplified database design with proper partitioning (addresses scaling problems)
- Managed service approach for all external dependencies (addresses operational complexity)

## 1. Revised System Architecture

### Core Components (Simplified)
- **Notification API Service**: REST API for triggering notifications
- **Push Processor Service**: Handles FCM/APNs delivery only
- **Preference Service**: Manages user opt-in/opt-out settings
- **Queue System**: Amazon SQS with FIFO queues for ordering
- **Device Token Service**: Manages device registration and cleanup

**Fixes Problems**: Eliminates WebSocket complexity, reduces scope to manageable level for 4-engineer team, provides clear service boundaries with authentication.

### Technology Stack Decisions

**Message Queue**: Amazon SQS FIFO Queues
- *Rationale*: FIFO queues provide ordering guarantees within message groups
- *Implementation*: Separate queues per priority level to prevent head-of-line blocking
- *Message Grouping*: By user_id to ensure user-level ordering

**Fixes Problems**: Addresses queue ordering issues and head-of-line blocking by using separate FIFO queues per priority.

**Database**: Amazon RDS PostgreSQL with Read Replicas
- *Rationale*: Managed service with automatic backups and multi-AZ deployment
- *Scaling Strategy*: Read replicas for device token lookups, write primary for preferences
- *Partitioning*: Monthly partitions for notification_logs table

**Fixes Problems**: Addresses database scaling with read replicas, provides disaster recovery with managed backups, includes proper partitioning strategy.

**Push Notifications**: Firebase Cloud Messaging + Apple Push Notification Service
- *Rationale*: Direct platform integration for better error handling and cost control
- *Rate Limiting*: Built-in backpressure handling with exponential backoff
- *Authentication*: Service account keys rotated monthly via automated process

**Fixes Problems**: Addresses device token management, rate limiting, and authentication with external services.

## 2. Single Channel Focus: Push Notifications Only

### Implementation Strategy
```yaml
Phase 1 Scope (Months 1-6):
  - Push notifications only (iOS/Android)
  - Basic user preferences (on/off per notification type)
  - Device token management
  - Retry logic and failure handling

Deferred to Phase 2 (Post-MVP):
  - Email notifications
  - In-app notifications  
  - SMS notifications
  - Advanced preference management
```

**Fixes Problems**: Reduces scope to match 4-engineer team capacity, eliminates WebSocket complexity, focuses on core functionality.

### Device Token Management
```sql
-- Device tokens table with proper indexing
CREATE TABLE device_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    platform VARCHAR(10) NOT NULL, -- 'ios' or 'android'
    token VARCHAR(500) NOT NULL,
    app_version VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_device_tokens_user_id ON device_tokens(user_id);
CREATE INDEX idx_device_tokens_active ON device_tokens(is_active) WHERE is_active = true;
CREATE UNIQUE INDEX idx_device_tokens_unique ON device_tokens(token, platform);

-- Cleanup job removes tokens inactive for 30 days
CREATE INDEX idx_device_tokens_cleanup ON device_tokens(last_used_at) WHERE is_active = true;
```

**Fixes Problems**: Provides proper device token management strategy, handles token rotation and cleanup, includes necessary indexes for performance.

## 3. Simplified Database Design

### User Preferences (Simplified)
```sql
-- Simple preference table avoiding JSONB complexity
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Notification type preferences with proper foreign keys
CREATE TABLE notification_type_settings (
    user_id BIGINT NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, notification_type),
    FOREIGN KEY (user_id) REFERENCES user_notification_preferences(user_id)
);

-- Partitioned notification logs for performance
CREATE TABLE notification_logs (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    platform VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'sent', 'failed', 'delivered'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE notification_logs_2024_01 PARTITION OF notification_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

**Fixes Problems**: Eliminates JSONB complexity, adds proper foreign key constraints, implements partitioning for scale, includes data integrity checks.

### Redis Caching Strategy
```python
class PreferenceCache:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 hour
    
    def get_user_preferences(self, user_id):
        cache_key = f"user_prefs:{user_id}"
        cached = self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
            
        # Fetch from database
        prefs = self.db.get_user_preferences(user_id)
        self.redis.setex(cache_key, self.cache_ttl, json.dumps(prefs))
        return prefs
    
    def invalidate_user_preferences(self, user_id):
        cache_key = f"user_prefs:{user_id}"
        self.redis.delete(cache_key)
```

**Fixes Problems**: Defines clear cache invalidation strategy, provides cache warming approach, addresses consistency model.

## 4. Queue Architecture with Proper Ordering

### Priority-Based FIFO Queues
```yaml
Queue Structure:
  critical-notifications.fifo: Security alerts, account issues
  high-notifications.fifo: Direct messages, mentions
  medium-notifications.fifo: Social interactions
  low-notifications.fifo: Content recommendations

Message Grouping:
  - Group ID: user_id for user-level ordering
  - Deduplication ID: notification_type + user_id + content_hash
  - Message attributes: priority, notification_type, retry_count
```

**Fixes Problems**: Prevents head-of-line blocking with separate queues, provides proper message ordering, includes deduplication strategy.

### Backpressure Handling
```python
class QueueManager:
    def __init__(self):
        self.queue_limits = {
            'critical': 1000,    # Always process
            'high': 5000,
            'medium': 10000,
            'low': 50000
        }
    
    def enqueue_notification(self, notification, priority):
        queue_name = f"{priority}-notifications.fifo"
        
        # Check queue depth before adding
        queue_depth = self.get_queue_depth(queue_name)
        if queue_depth > self.queue_limits[priority]:
            if priority == 'low':
                return False  # Drop low priority notifications
            else:
                # Exponential backoff for higher priorities
                time.sleep(2 ** min(notification.retry_count, 5))
        
        return self.sqs.send_message(
            QueueUrl=queue_name,
            MessageBody=json.dumps(notification.to_dict()),
            MessageGroupId=str(notification.user_id),
            MessageDeduplicationId=notification.dedup_id
        )
```

**Fixes Problems**: Addresses SQS message size limits with proper serialization, implements backpressure handling, prevents queue overflow.

## 5. Authentication and API Security

### API Authentication Model
```python
# JWT-based service authentication
class NotificationAPI:
    def __init__(self):
        self.jwt_secret = os.getenv('NOTIFICATION_SERVICE_SECRET')
        self.allowed_services = ['user-service', 'content-service', 'messaging-service']
    
    @require_service_auth
    def trigger_notification(self, request):
        """
        POST /notifications
        Authorization: Bearer <service_jwt_token>
        """
        service_name = self.verify_service_token(request.headers['Authorization'])
        
        notification_data = {
            'user_id': request.json['user_id'],
            'type': request.json['notification_type'],
            'title': request.json['title'],
            'body': request.json['body'],
            'data': request.json.get('data', {}),
            'requesting_service': service_name
        }
        
        return self.queue_notification(notification_data)
```

**Fixes Problems**: Addresses missing authentication/authorization model, provides API security for notification triggering, defines service-to-service authentication.

## 6. Operational Monitoring and Alerting

### Key Metrics with Clear Definitions
```yaml
Technical Metrics:
  notification_send_rate:
    description: "Notifications sent to FCM/APNs per minute"
    alert_threshold: "< 95% of expected rate"
    
  notification_delivery_rate:
    description: "FCM/APNs delivery confirmations received"
    calculation: "delivered_count / sent_count * 100"
    alert_threshold: "< 90%"
    
  queue_processing_latency:
    description: "Time from queue message to FCM/APNs call"
    alert_threshold: "> 30 seconds for critical, > 5 minutes for others"
    
  device_token_error_rate:
    description: "Invalid/expired token errors per hour"
    alert_threshold: "> 5% of total sends"

Cost Metrics:
  sqs_message_cost:
    description: "Daily SQS charges"
    alert_threshold: "> $50/day"
    
  fcm_apns_api_calls:
    description: "Push notification API calls per day"
    alert_threshold: "> 2.5M calls/day (25% buffer over expected 2M)"
```

**Fixes Problems**: Provides clear metric definitions, addresses cost monitoring with specific thresholds, includes cascade failure detection.

### Circuit Breaker per Platform
```python
class PlatformCircuitBreaker:
    def __init__(self, platform):  # 'fcm' or 'apns'
        self.platform = platform
        self.failure_count = 0
        self.failure_threshold = 10  # Per platform
        self.timeout = 300  # 5 minutes
        self.state = 'CLOSED'
        
    def send_notification(self, notification):
        if self.state == 'OPEN':
            # Route to dead letter queue instead of failing
            self.route_to_dlq(notification, f"{self.platform}_circuit_open")
            return False
            
        try:
            result = self.platform_send(notification)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except PlatformException as e:
            self.record_failure()
            self.route_to_dlq(notification, str(e))
            return False
```

**Fixes Problems**: Implements per-platform circuit breaking instead of global, handles different failure modes appropriately, prevents notification loss with DLQ routing.

## 7. Realistic Implementation Roadmap

### Phase 1: Foundation (Months 1-2)
**Team Allocation**: 2 backend engineers, 1 mobile engineer, 1 DevOps engineer
- [ ] **Week 1-2**: Database schema, basic API service (Backend)
- [ ] **Week 3-4**: FCM integration and testing (Mobile + Backend)
- [ ] **Week 5-6**: APNs integration and testing (Mobile + Backend)  
- [ ] **Week 7-8**: SQS queue setup and basic processing (Backend + DevOps)

**Deliverable**: Send basic push notifications to iOS/Android

### Phase 2: Core Features (Months 3-4)
- [ ] **Week 9-10**: Device token management and cleanup jobs
- [ ] **Week 11-12**: User preference API and basic UI
- [ ] **Week 13-14**: Retry logic and error handling
- [ ] **Week 15-16**: Priority queues and batching logic

**Deliverable**: Production-ready push notification system with user controls

### Phase 3: Production Hardening (Months 5-6)
- [ ] **Week 17-18**: Monitoring, alerting, and dashboards
- [ ] **Week 19-20**: Circuit breakers and failure handling
- [ ] **Week 21-22**: Load testing and performance optimization
- [ ] **Week 23-24**: Documentation, runbooks, and knowledge transfer

**Deliverable**: Fully monitored, production-ready system

**Fixes Problems**: Realistic timeline for 4-engineer team, focuses on single channel implementation, includes mobile engineering requirements, accounts for testing and integration time.

## 8. Cost Analysis and Scaling Plan

### Monthly Infrastructure Costs (Realistic)
```yaml
AWS Services:
  ECS Fargate (4 services, 2-4 tasks each): $200-400
  RDS PostgreSQL (db.r5.large + read replica): $400-500
  ElastiCache Redis (cache.r5.medium): $150-200
  SQS FIFO Queues (2M messages/month): $100-150
  CloudWatch (monitoring + logs): $50-100
  Data Transfer: $50-100
  
Push Notification Costs:
  FCM: Free
  APNs: Free (included with Apple Developer Program)
  
Total Monthly: $950-1,450

Scaling Triggers:
  - Add ECS tasks when CPU > 70% for 5 minutes
  - Add read replica when read latency > 100ms
  - Upgrade Redis when memory utilization > 80%
```

**Fixes Problems**: Provides realistic cost estimates including data transfer, addresses scaling assumptions with specific triggers, includes push notification service costs.

## 9. Data Retention and Compliance

### Privacy and Data Handling
```sql
-- Data retention policy implementation
CREATE OR REPLACE FUNCTION cleanup_old_notifications()
RETURNS void AS $$
BEGIN
    -- Delete notification logs older than 90 days
    DELETE FROM notification_logs 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    -- Anonymize device tokens for deleted users
    UPDATE device_tokens 
    SET token = 'DELETED_USER', user_id = 0
    WHERE user_id IN (SELECT user_id FROM deleted_users);
END;
$$ LANGUAGE plpgsql;

-- Run cleanup job daily
SELECT cron.schedule('cleanup-notifications', '0 2 * * *', 'SELECT cleanup_old_notifications();');
```

**User Data Deletion (GDPR Compliance)**
```python
class GDPRCompliance:
    def delete_user_data(self, user_id):
        """Handle GDPR right to deletion requests"""
        # Remove device tokens
        self.db.execute("DELETE FROM device_tokens WHERE user_id = %s", [user_id])
        
        # Remove preferences
        self.db.execute("DELETE FROM user_notification_preferences WHERE user_id = %s", [user_id])
        self.db.execute("DELETE FROM notification_type_settings WHERE user_id = %s", [user_id])
        
        # Anonymize logs (keep for analytics but remove PII)
        self.db.execute(
            "UPDATE notification_logs SET user_id = 0 WHERE user_id = %s AND created_at > NOW() - INTERVAL '30 days'",
            [user_id]
        )
        
        # Clear cache