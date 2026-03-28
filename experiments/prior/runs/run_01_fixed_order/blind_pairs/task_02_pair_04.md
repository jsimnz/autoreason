# Blind Evaluation: task_02_pair_04

## Task
Design the notification system for a social app with 10M MAU. Cover: delivery channels (push, email, in-app, SMS), priority and batching logic, user preference management, infrastructure choices, and failure handling. The team has 4 backend engineers and 6 months. Be specific about tradeoffs you're making and why.

---

## Proposal X

# Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a scalable notification system supporting 10 million monthly active users with a 4-engineer team over 6 months. The design prioritizes reliability, user experience, and operational simplicity while making strategic tradeoffs to meet resource constraints.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator for all notifications
- **Channel Handlers**: Dedicated processors for each delivery channel
- **User Preference Service**: Manages user notification settings
- **Queue System**: Handles batching and priority routing
- **Analytics Service**: Tracks delivery metrics and user engagement

### Technology Stack Decisions

**Message Queue**: Amazon SQS + DLQ
- *Rationale*: Managed service reduces operational overhead for small team
- *Tradeoff*: Higher per-message cost vs. self-managed Kafka, but eliminates infrastructure management

**Database**: PostgreSQL primary + Redis cache
- *Rationale*: Team likely familiar with PostgreSQL; Redis for high-frequency preference lookups
- *Tradeoff*: Single database vs. microservices approach for faster initial development

**Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- *Rationale*: Direct integration reduces complexity vs. third-party aggregators
- *Tradeoff*: Platform-specific handling vs. unified API for better control and cost

## 2. Delivery Channels Implementation

### Push Notifications (Primary Channel)
```yaml
Implementation:
  - FCM for Android
  - APNs for iOS
  - Device token management in PostgreSQL
  - Retry logic: 3 attempts with exponential backoff

Capacity Planning:
  - Peak: 50K notifications/minute
  - Daily volume: 2M push notifications
  - Token refresh handling: Daily batch job
```

### In-App Notifications
```yaml
Implementation:
  - WebSocket connections for real-time delivery
  - Fallback to REST API polling (30-second intervals)
  - Message persistence: 30 days in PostgreSQL

Technical Details:
  - Connection pooling: 10K concurrent WebSocket connections
  - Message format: JSON with read/unread status
  - Offline message queue per user (max 100 messages)
```

### Email Notifications
```yaml
Implementation:
  - Amazon SES for delivery
  - Template system using Handlebars
  - Bounce/complaint handling via SES webhooks

Constraints:
  - Daily digest only (not real-time)
  - Maximum 1 email per user per day
  - Unsubscribe handling with one-click compliance
```

### SMS (Limited Implementation)
```yaml
Implementation:
  - Amazon SNS for delivery
  - US/Canada only initially
  - Critical notifications only (security alerts, password resets)

Rationale:
  - High cost limits usage to essential notifications
  - Regulatory compliance complexity deferred
```

## 3. Priority and Batching Logic

### Priority Levels
```yaml
CRITICAL (0-30 seconds):
  - Security alerts
  - Account lockouts
  - Payment failures
  - Direct messages from verified accounts

HIGH (0-5 minutes):
  - Direct messages
  - Mentions
  - Live event notifications
  - Friend requests

MEDIUM (5-60 minutes):
  - Likes on posts
  - Comments on posts
  - New followers
  - Group invitations

LOW (1-24 hours):
  - Trending content suggestions
  - Weekly digest
  - Feature announcements
```

### Batching Strategy
```python
# Pseudo-code for batching logic
class NotificationBatcher:
    def batch_notifications(self, notifications):
        batches = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }
        
        for notification in notifications:
            priority = self.determine_priority(notification)
            batches[priority].append(notification)
            
            # Batch size limits
            if len(batches[priority]) >= self.get_batch_size(priority):
                self.process_batch(batches[priority], priority)
                batches[priority] = []
    
    def get_batch_size(self, priority):
        return {
            'critical': 1,      # Immediate processing
            'high': 100,        # Small batches for speed
            'medium': 1000,     # Larger batches for efficiency
            'low': 5000         # Maximum efficiency
        }[priority]
```

## 4. User Preference Management

### Preference Categories
```yaml
Channel Preferences:
  - Push: enabled/disabled per notification type
  - Email: daily digest on/off
  - In-app: always enabled (non-configurable)
  - SMS: opt-in only for critical

Timing Preferences:
  - Quiet hours: 10 PM - 8 AM local time
  - Weekend notifications: enabled/disabled
  - Frequency caps: max 10 push notifications per day

Content Preferences:
  - Social interactions: likes, comments, follows
  - Content discovery: trending, recommendations
  - System notifications: security, updates
```

### Implementation
```sql
-- User preferences table schema
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_digest_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    max_daily_push INTEGER DEFAULT 10,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Notification type preferences
CREATE TABLE notification_type_preferences (
    user_id BIGINT,
    notification_type VARCHAR(50),
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, notification_type)
);
```

### Preference Processing Logic
```python
class PreferenceManager:
    def should_send_notification(self, user_id, notification_type, channel):
        # Check global preferences
        user_prefs = self.get_user_preferences(user_id)
        if not user_prefs.is_channel_enabled(channel):
            return False
            
        # Check quiet hours
        if self.is_quiet_hours(user_prefs.timezone):
            return notification_type == 'CRITICAL'
            
        # Check daily limits
        if self.daily_limit_reached(user_id, channel):
            return notification_type in ['CRITICAL', 'HIGH']
            
        # Check type-specific preferences
        return user_prefs.is_type_enabled(notification_type, channel)
```

## 5. Infrastructure Choices

### Deployment Architecture
```yaml
Production Environment:
  - AWS ECS Fargate for container orchestration
  - Application Load Balancer with health checks
  - RDS PostgreSQL Multi-AZ (db.r5.xlarge)
  - ElastiCache Redis cluster (cache.r5.large)
  - CloudWatch for monitoring and alerting

Development/Staging:
  - Smaller instance sizes (50% of production capacity)
  - Single AZ deployment for cost optimization
  - Shared Redis instance
```

### Scaling Strategy
```yaml
Horizontal Scaling:
  - Auto-scaling groups: 2-10 ECS tasks
  - Scale triggers: CPU > 70% or SQS queue depth > 1000
  - Database read replicas for preference lookups

Vertical Scaling:
  - Database: Start with db.r5.large, scale to db.r5.xlarge
  - Cache: Start with cache.r5.medium, scale to cache.r5.large
```

### Cost Optimization
```yaml
Monthly Infrastructure Costs (estimated):
  - ECS Fargate: $400-800
  - RDS PostgreSQL: $300-600
  - ElastiCache: $150-300
  - SQS: $50-100
  - SES: $10-50
  - Total: $910-1,850/month

Cost Controls:
  - Reserved instances for predictable workloads
  - Spot instances for batch processing
  - Automated resource scheduling (dev environments)
```

## 6. Failure Handling and Reliability

### Retry Mechanisms
```yaml
Push Notifications:
  - Retry attempts: 3
  - Backoff: exponential (1s, 4s, 16s)
  - Dead letter queue after final failure
  - Device token cleanup for invalid tokens

Email Notifications:
  - SES handles retries automatically
  - Bounce handling: disable email for hard bounces
  - Complaint handling: immediate unsubscribe

In-App Notifications:
  - WebSocket reconnection: automatic with exponential backoff
  - Message persistence: 30 days for offline users
  - Fallback to REST polling if WebSocket fails
```

### Circuit Breaker Implementation
```python
class NotificationCircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpenException()
        
        try:
            result = func(*args, **kwargs)
            self.reset()
            return result
        except Exception as e:
            self.record_failure()
            raise e
```

### Monitoring and Alerting
```yaml
Key Metrics:
  - Notification delivery rate by channel
  - Processing latency by priority level
  - Queue depth and processing rate
  - Error rates by notification type
  - User engagement rates

Alert Thresholds:
  - Delivery rate < 95%: Warning
  - Delivery rate < 90%: Critical
  - Queue depth > 10,000: Warning
  - Processing latency > 5 minutes: Critical
  - Error rate > 5%: Warning
```

## 7. Implementation Roadmap

### Phase 1 (Months 1-2): Core Infrastructure
- [ ] Basic notification service with PostgreSQL
- [ ] Push notification implementation (FCM/APNs)
- [ ] In-app notification system
- [ ] Basic user preference management
- [ ] SQS queue implementation

### Phase 2 (Months 3-4): Enhanced Features
- [ ] Email notification system
- [ ] Priority and batching logic
- [ ] Advanced user preferences
- [ ] Basic analytics and monitoring
- [ ] Retry mechanisms and error handling

### Phase 3 (Months 5-6): Production Readiness
- [ ] SMS notification implementation
- [ ] Circuit breaker patterns
- [ ] Comprehensive monitoring and alerting
- [ ] Performance optimization
- [ ] Load testing and capacity planning
- [ ] Documentation and runbooks

## 8. Key Tradeoffs and Rationale

### Managed Services vs. Self-Hosted
**Decision**: Use managed services (SQS, SES, RDS)
**Rationale**: 4-engineer team cannot maintain custom infrastructure
**Tradeoff**: Higher operational costs vs. reduced complexity

### Single Database vs. Microservices
**Decision**: Single PostgreSQL database with service separation
**Rationale**: Faster development with familiar technology
**Tradeoff**: Potential scaling bottleneck vs. development velocity

### Real-time vs. Near Real-time
**Decision**: Near real-time for most notifications (5-minute batches)
**Rationale**: Balances user experience with system efficiency
**Tradeoff**: Slight delay vs. resource optimization

### Feature Scope
**Decision**: Limited SMS implementation, no advanced ML personalization
**Rationale**: Focus on core functionality with small team
**Tradeoff**: Reduced feature set vs. reliable core system

## 9. Success Metrics

### Technical Metrics
- 99.9% uptime for notification service
- 95% delivery rate across all channels
- <5 minute processing latency for high-priority notifications
- <1% error rate for notification processing

### Business Metrics
- 40% push notification opt-in rate
- 15% email open rate for digests
- 25% click-through rate for actionable notifications
- <2% unsubscribe rate monthly

This design provides a solid foundation for a notification system that can scale to 10M MAU while being implementable by a 4-engineer team in 6 months. The focus on managed services and proven technologies ensures reliability while the modular design allows for future enhancements as the team and requirements grow.

---

## Proposal Y

# Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a scalable notification system supporting 10 million monthly active users with a 4-engineer team over 6 months. The design prioritizes **core functionality over feature breadth** while maintaining architectural scalability, focusing on push notifications as the primary channel with a clear path to expand additional channels post-MVP.

**Key Strategic Decisions:**
- **MVP Focus**: Push notifications only (addresses scope/team size mismatch from Version A)
- **Managed Infrastructure**: AWS managed services to reduce operational overhead
- **Scalable Foundation**: Architecture designed for future channel expansion without rework
- **Production-Ready**: Comprehensive monitoring, security, and reliability from day one

## 1. System Architecture Overview

### Core Components
- **Notification API Service**: REST API with JWT authentication for triggering notifications
- **Push Processor Service**: Handles FCM/APNs delivery with retry logic
- **User Preference Service**: Manages notification settings and device tokens
- **Queue System**: Amazon SQS FIFO queues with priority-based routing
- **Analytics Service**: Tracks delivery metrics and user engagement

**Rationale**: Maintains Version A's service separation while incorporating Version B's authentication and security improvements. Eliminates WebSocket complexity for MVP while preserving modular design for future expansion.

### Technology Stack Decisions

**Message Queue**: Amazon SQS FIFO Queues
- *Rationale*: FIFO queues provide ordering guarantees; separate queues per priority prevent head-of-line blocking
- *Implementation*: Message grouping by user_id ensures user-level ordering
- *Tradeoff*: Higher cost vs. complexity reduction for 4-engineer team

**Database**: Amazon RDS PostgreSQL with Read Replicas
- *Rationale*: Managed service with multi-AZ deployment; read replicas for device token lookups
- *Scaling Strategy*: Monthly partitioning for logs, proper indexing for performance
- *Tradeoff*: Managed service cost vs. operational simplicity

**Push Notifications**: Firebase Cloud Messaging + Apple Push Notification Service
- *Rationale*: Direct platform integration for better error handling and cost control
- *Authentication*: Service account keys with automated monthly rotation
- *Tradeoff*: Platform-specific handling vs. unified API for better control

## 2. Multi-Channel Architecture (Push-First Implementation)

### Phase 1: Push Notifications (MVP - Months 1-6)
```yaml
Implementation:
  - FCM for Android with exponential backoff retry
  - APNs for iOS with proper certificate management
  - Device token management with cleanup automation
  - User preferences for notification types

Capacity Planning:
  - Peak: 50K notifications/minute
  - Daily volume: 2M push notifications
  - Connection handling: Direct API calls (no WebSocket complexity)
```

### Phase 2: Additional Channels (Post-MVP)
```yaml
Email Notifications:
  - Amazon SES integration ready
  - Template system architecture defined
  - Daily digest batching prepared

In-App Notifications:
  - REST API polling architecture (not WebSocket)
  - Message persistence strategy defined
  - 30-day retention policy established

SMS Notifications:
  - Amazon SNS integration framework
  - Critical notifications only (security alerts)
  - US/Canada regulatory compliance ready
```

**Rationale**: Version B's focused approach for MVP with Version A's comprehensive channel planning. Eliminates WebSocket complexity while maintaining architectural flexibility for future expansion.

## 3. Priority and Batching Logic

### Priority Levels (Inherited from Version A - Proven Framework)
```yaml
CRITICAL (0-30 seconds):
  - Security alerts, account lockouts, payment failures
  - Processing: Individual messages, immediate delivery

HIGH (0-5 minutes):
  - Direct messages, mentions, live events
  - Processing: Small batches (100 messages)

MEDIUM (5-60 minutes):
  - Social interactions, group invitations
  - Processing: Medium batches (1000 messages)

LOW (1-24 hours):
  - Content recommendations, weekly digests
  - Processing: Large batches (5000 messages)
```

### Queue Architecture with Proper Ordering
```yaml
Queue Structure:
  critical-notifications.fifo: Immediate processing
  high-notifications.fifo: 5-minute batch processing
  medium-notifications.fifo: 1-hour batch processing
  low-notifications.fifo: Daily batch processing

Message Grouping:
  - Group ID: user_id for user-level ordering
  - Deduplication ID: notification_type + user_id + content_hash
  - Backpressure: Drop low-priority when queue depth exceeds limits
```

**Rationale**: Version A's proven priority framework with Version B's technical implementation improvements for FIFO queues and backpressure handling.

## 4. Database Design and User Preferences

### Simplified Schema (Version B Approach)
```sql
-- Device tokens with proper indexing and cleanup
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

CREATE INDEX idx_device_tokens_user_id ON device_tokens(user_id);
CREATE INDEX idx_device_tokens_active ON device_tokens(is_active) WHERE is_active = true;
CREATE UNIQUE INDEX idx_device_tokens_unique ON device_tokens(token, platform);

-- User preferences (simplified for MVP, extensible for future)
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    timezone VARCHAR(50) DEFAULT 'UTC',
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    max_daily_push INTEGER DEFAULT 10,
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

-- Partitioned logs for scale (Version B improvement)
CREATE TABLE notification_logs (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    platform VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);
```

**Rationale**: Version B's simplified approach eliminates JSONB complexity while preserving Version A's comprehensive preference categories. Adds proper constraints and partitioning for production scale.

### Preference Processing with Caching
```python
class PreferenceManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 hour
    
    def should_send_notification(self, user_id, notification_type, channel='push'):
        # Get cached or fetch preferences
        user_prefs = self.get_cached_preferences(user_id)
        
        # Check global channel preference
        if not user_prefs.get('push_enabled', True):
            return False
            
        # Check quiet hours (Version A logic)
        if self.is_quiet_hours(user_prefs.get('timezone', 'UTC')):
            return notification_type == 'CRITICAL'
            
        # Check daily limits
        if self.daily_limit_reached(user_id, channel):
            return notification_type in ['CRITICAL', 'HIGH']
            
        # Check type-specific preferences
        return self.is_type_enabled(user_id, notification_type)
    
    def get_cached_preferences(self, user_id):
        cache_key = f"user_prefs:{user_id}"
        cached = self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
            
        prefs = self.db.get_user_preferences(user_id)
        self.redis.setex(cache_key, self.cache_ttl, json.dumps(prefs))
        return prefs
```

**Rationale**: Combines Version A's comprehensive preference logic with Version B's caching strategy and clear cache invalidation.

## 5. API Security and Authentication

### Service-to-Service Authentication
```python
class NotificationAPI:
    def __init__(self):
        self.jwt_secret = os.getenv('NOTIFICATION_SERVICE_SECRET')
        self.allowed_services = ['user-service', 'content-service', 'messaging-service']
    
    @require_service_auth
    def trigger_notification(self, request):
        """
        POST /notifications
        Authorization: Bearer <service_jwt_token>
        Content-Type: application/json
        
        Body:
        {
            "user_id": 12345,
            "notification_type": "MENTION",
            "title": "You were mentioned",
            "body": "John mentioned you in a post",
            "data": {"post_id": 67890},
            "priority": "HIGH"
        }
        """
        service_name = self.verify_service_token(request.headers['Authorization'])
        
        notification = NotificationRequest(
            user_id=request.json['user_id'],
            type=request.json['notification_type'],
            title=request.json['title'],
            body=request.json['body'],
            data=request.json.get('data', {}),
            priority=request.json.get('priority', 'MEDIUM'),
            requesting_service=service_name
        )
        
        return self.queue_notification(notification)
    
    def verify_service_token(self, auth_header):
        try:
            token = auth_header.replace('Bearer ', '')
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            
            if payload['service'] not in self.allowed_services:
                raise UnauthorizedError("Service not allowed")
                
            return payload['service']
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Invalid token")
```

**Rationale**: Version B's authentication approach addresses the missing security model from Version A, essential for production deployment.

## 6. Failure Handling and Monitoring

### Circuit Breaker per Platform
```python
class PlatformCircuitBreaker:
    def __init__(self, platform):  # 'fcm' or 'apns'
        self.platform = platform
        self.failure_count = 0
        self.failure_threshold = 10
        self.timeout = 300  # 5 minutes
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = None
        
    def send_notification(self, notification):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                # Route to DLQ instead of dropping
                self.route_to_dlq(notification, f"{self.platform}_circuit_open")
                return False
                
        try:
            result = self.platform_send(notification)
            if self.state == 'HALF_OPEN':
                self.reset()
            return result
        except PlatformException as e:
            self.record_failure()
            self.route_to_dlq(notification, str(e))
            return False
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            
    def reset(self):
        self.failure_count = 0
        self.state = 'CLOSED'
        self.last_failure_time = None
```

### Comprehensive Monitoring
```yaml
Technical Metrics:
  notification_delivery_rate:
    description: "FCM/APNs delivery confirmations received"
    calculation: "delivered_count / sent_count * 100"
    alert_threshold: "< 95% for 5 minutes"
    
  queue_processing_latency:
    description: "Time from queue message to platform API call"
    alert_threshold: "> 30s critical, > 5min high, > 60min medium"
    
  device_token_error_rate:
    description: "Invalid/expired token errors"
    alert_threshold: "> 5% of sends per hour"
    
  circuit_breaker_state:
    description: "FCM/APNs circuit breaker status"
    alert_threshold: "OPEN state for > 1 minute"

Business Metrics:
  daily_active_push_users:
    description: "Users receiving push notifications daily"
    target: "40% of DAU"
    
  notification_engagement_rate:
    description: "Push notifications clicked/opened"
    target: "25% click-through rate"
    
  opt_out_rate:
    description: "Users disabling push notifications"
    alert_threshold: "> 2% monthly increase"
```

**Rationale**: Combines Version A's comprehensive monitoring approach with Version B's specific technical implementations and clear alert thresholds.

## 7. Infrastructure and Scaling

### Deployment Architecture
```yaml
Production Environment:
  Compute: 
    - ECS Fargate with auto-scaling (2-8 tasks per service)
    - Application Load Balancer with health checks
  
  Database:
    - RDS PostgreSQL Multi-AZ (db.r5.large)
    - Read replica for device token lookups
    - ElastiCache Redis cluster (cache.r5.medium)
  
  Monitoring:
    - CloudWatch with custom dashboards
    - SNS alerts for critical thresholds
    - X-Ray tracing for request debugging

Scaling Triggers:
  - CPU > 70% for 5 minutes: Add ECS tasks
  - Queue depth > 1000 messages: Scale processing
  - Database read latency > 100ms: Add read replica
```

### Monthly Cost Analysis
```yaml
AWS Infrastructure:
  ECS Fargate (4 services, 2-6 tasks): $300-600
  RDS PostgreSQL + Read Replica: $400-600
  ElastiCache Redis: $150-250
  SQS FIFO Queues (2M messages): $100-150
  CloudWatch + X-Ray: $75-125
  Data Transfer: $50-100
  
Push Services:
  FCM: Free
  APNs: Free (Apple Developer Program)
  
Total Monthly: $1,075-1,825

Cost Controls:
  - Reserved instances for predictable workloads
  - Auto-scaling to match demand
  - Queue depth monitoring to prevent overages
```

**Rationale**: Version A's comprehensive infrastructure planning with Version B's realistic cost estimates and specific scaling triggers.

## 8. Implementation Roadmap

### Phase 1: Foundation (Months 1-2)
**Team**: 2 Backend Engineers, 1 Mobile Engineer, 1 DevOps Engineer

**Weeks 1-2: Core Infrastructure**
- Database schema implementation (Backend)
- Basic notification API with authentication (Backend)
- AWS infrastructure setup (DevOps)

**Weeks 3-4: Platform Integration**
- FCM integration and testing (Backend + Mobile)
- APNs integration and testing (Backend + Mobile)
- Device token registration flow (Mobile)

**Weeks 5-6: Queue Processing**
- SQS FIFO queue setup (Backend + DevOps)
- Basic message processing (Backend)
- Retry logic implementation (Backend)

**Weeks 7-8: User Preferences**
- Preference API implementation (Backend)
- Basic mobile preference UI (Mobile)
- Integration testing (All)

**Deliverable**: Send basic push notifications with user controls

### Phase 2: Production Features (Months 3-4)

**Weeks 9-10: Priority and Batching**
- Priority queue implementation
- Batching logic for different priority levels
- Device token cleanup automation

**Weeks 11-12: Advanced Preferences**
- Quiet hours and timezone handling
- Daily limit enforcement
- Notification type granular controls

**Weeks 13-14: Reliability**
- Circuit breaker implementation
-
