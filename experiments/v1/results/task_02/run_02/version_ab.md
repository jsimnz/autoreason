# Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a scalable notification system capable of handling 10M monthly active users with a team of 4 backend engineers over 6 months. The design balances architectural sophistication with operational pragmatism, leveraging managed services strategically while maintaining control over core business logic and scaling characteristics.

## System Architecture Overview

### Core Components
1. **Notification Service** - Central orchestration layer with REST API
2. **Channel Adapters** - Push, Email, In-app, SMS delivery services
3. **User Preference Engine** - Integrated with existing user database
4. **Queue System** - Redis-based priority queues with Kafka upgrade path
5. **Analytics & Monitoring** - CloudWatch with custom metrics

**Rationale**: Maintains Version A's comprehensive architecture while adopting Version B's pragmatic service boundaries and managed service approach.

## 1. Delivery Channels Strategy

### Channel Selection & Implementation

**Push Notifications (Primary Channel)**
- **Implementation**: Firebase Admin SDK for unified iOS/Android management
- **Device Token Management**: PostgreSQL storage with user_id mapping, daily validation jobs to remove stale tokens
- **Rate Limits**: FCM supports 600K messages/minute; our peak 2,000/second (120K/minute) provides comfortable headroom
- **Capacity**: Handle 250K notifications/minute with auto-scaling
- **Fallback**: In-app notification storage for offline users

**In-App Notifications (Polling-Based)**
- **Implementation**: REST API polling every 30 seconds during active sessions
- **Mobile Strategy**: iOS/Android background refresh, leveraging platform-native background processing
- **Storage**: PostgreSQL notifications table with 7-day retention
- **Capacity**: Standard database queries with user_id indexing

**Rationale**: Version B correctly identifies WebSocket complexity as unnecessary. Mobile apps naturally poll for notifications, and persistent connections don't align with mobile battery optimization patterns.

**Email (Batch Channel)**
- **Implementation**: SendGrid paid plan (Essential: $19.95/month for 100K emails)
- **Deliverability Setup**: SPF/DKIM authentication, dedicated IP warming over 2-week period
- **Capacity**: 100K emails/month for transactional, additional volume pricing for marketing
- **Templates**: SendGrid dynamic templates with merge tag personalization
- **Unsubscribe Handling**: Automated webhook processing for bounces and unsubscribes

**SMS (Critical Use Only)**
- **Implementation**: Twilio API with geographic restrictions
- **Usage**: Security alerts (suspicious logins, password resets) only - estimated 1% of users monthly
- **Budget**: $500/month (66K messages at $0.0075 each)
- **Geographic Scope**: US/Canada initially (lower costs, regulatory simplicity)

**Rationale**: Version B's realistic cost assessment and use case limitation is correct. Version A's $5,000 SMS budget would represent 20% of infrastructure costs for minimal business value.

### Channel Priority Matrix
```
Critical (Security): SMS → Push → Email
High (Social): Push → In-App  
Medium (Engagement): Push OR Email (user preference)
Low (Marketing): Email only
```

## 2. Priority and Batching Logic

### Priority Classification

**Critical (P0)** - Security and payments only
- Password resets, suspicious logins, payment failures
- Immediate delivery, no batching, all available channels
- Volume: <1,000/day
- SLA: <30 seconds

**High (P1)** - Real-time social interactions
- Direct messages, mentions, friend requests, live event updates
- Process within 1 minute, micro-batching for efficiency
- Push + In-app channels
- Volume: ~50,000/day
- SLA: <2 minutes

**Medium (P2)** - Standard engagement
- Likes, comments, follows, content recommendations
- Batching windows: 15 minutes, user-level deduplication
- Push OR Email (user preference)
- Volume: ~8,000,000/day
- SLA: <15 minutes

**Low (P3)** - Digest and marketing
- Weekly summaries, trending content, promotional content
- Daily/weekly batch processing
- Email only
- Volume: ~100,000/week
- SLA: Within scheduled window

### Batching Strategy

**Redis Priority Queue Implementation**:
```python
# Priority-based queue processing
QUEUES = {
    'CRITICAL': 'notifications:critical',
    'HIGH': 'notifications:high', 
    'MEDIUM': 'notifications:medium',
    'LOW': 'notifications:low'
}

class NotificationProcessor:
    def process_with_batching(self):
        while True:
            # Process critical immediately
            if notification := redis.brpop([QUEUES['CRITICAL']], timeout=1):
                self.send_immediately(notification)
                continue
                
            # Batch medium/low priority by user
            batch = self.collect_batch(timeout=15)  # 15-second windows for medium
            if batch:
                self.send_batch(batch)
```

**Batching Rules**:
- Critical: No batching, immediate delivery
- High: Micro-batching (5-second windows) for delivery efficiency
- Medium: 15-minute windows with user-level deduplication
- Low: Daily digest compilation

**User-Level Frequency Capping**:
- Maximum 50 push notifications per user per day
- Medium priority: Maximum 5 per user per hour
- Exponential backoff for users who don't engage

**Rationale**: Combines Version A's sophisticated batching logic with Version B's realistic implementation approach. Maintains micro-batching for efficiency while avoiding over-complexity.

## 3. User Preference Management

### Preference Schema
```sql
-- Extend existing users table with JSONB preferences
ALTER TABLE users ADD COLUMN notification_preferences JSONB DEFAULT '{
  "push_enabled": true,
  "email_enabled": true,
  "sms_enabled": false,
  "quiet_hours": {
    "start": "22:00",
    "end": "08:00", 
    "timezone": "UTC"
  },
  "notification_types": {
    "direct_messages": ["push", "email"],
    "mentions": ["push"],
    "likes": ["push"],
    "follows": ["email"],
    "marketing": []
  },
  "frequency_caps": {
    "push_daily_limit": 50,
    "email_weekly_limit": 10
  }
}';

-- Performance indexes
CREATE INDEX idx_users_notification_prefs ON users USING GIN (notification_preferences);
CREATE INDEX idx_users_push_enabled ON users ((notification_preferences->>'push_enabled')) WHERE notification_preferences->>'push_enabled' = 'true';
```

### Preference Engine Features

**Smart Defaults**:
- New users: Push enabled for direct messages and mentions only
- EU users: All channels disabled by default (GDPR compliance)
- Auto-disable push after 30 days of app inactivity
- Gradual opt-in based on engagement patterns

**Geographic Compliance**:
- GDPR: Explicit opt-in required for EU users
- CAN-SPAM: Easy unsubscribe for all email communications
- TCPA: SMS only with explicit consent and security justification

**Preference API**:
```
GET /api/v1/users/{user_id}/notification-preferences
PUT /api/v1/users/{user_id}/notification-preferences
POST /api/v1/users/{user_id}/notification-preferences/bulk-update
```

**Rationale**: Version B's database integration approach is more pragmatic than Version A's separate service. JSONB provides flexibility while maintaining ACID properties and query performance.

## 4. Infrastructure Choices

### Technology Stack Rationale

**Message Queue: Redis with Kafka Migration Path**
- **Phase 1**: Redis with AOF persistence and clustering
- **Why Redis First**: Team expertise, simpler operations, sufficient for initial scale
- **Migration Trigger**: >100K messages/hour sustained or durability requirements
- **Kafka Preparation**: Design queue interfaces to abstract underlying technology
- **Cost**: Redis Cluster on AWS ElastiCache: $800/month

**Database: PostgreSQL with Read Replicas**
- **Primary**: User preferences (JSONB), notification templates, audit logs
- **Read Replicas**: Analytics queries, reporting dashboard
- **Scaling Strategy**: Horizontal read scaling, vertical write scaling
- **Configuration**: 4 vCPUs, 32GB RAM, 1TB SSD primary + 2 read replicas
- **Cost**: $1,200/month

**Compute: ECS with Auto Scaling**
- **Why ECS over Kubernetes**: Simpler operations for 4-person team, AWS-native integration
- **Services**:
  - Notification API: 2-6 tasks (auto-scale based on CPU/queue depth)
  - Background Workers: 4-8 tasks (scale based on queue size)
  - Channel Services: 2 tasks each (push, email, SMS)
- **Cost**: $1,500/month

**Monitoring: CloudWatch + Custom Metrics + PagerDuty**
- **Application Metrics**: Custom CloudWatch metrics for delivery rates, latency
- **Infrastructure**: Standard CloudWatch monitoring for all AWS services
- **Alerting**: PagerDuty integration for SLA violations and service health
- **Logging**: CloudWatch Logs with structured JSON logging
- **Cost**: $400/month

**Rationale**: Adopts Version B's managed service approach while maintaining Version A's performance requirements. ECS provides container benefits without Kubernetes complexity.

### Capacity Planning

**Load Calculations**:
- 10M MAU with 5% daily activity = 500K DAU (Version A's assumption is more appropriate for social apps)
- Average 15 notifications/active user/day = 7.5M notifications/day
- Peak hours: 3x average = 625 notifications/second
- Growth buffer: 2x capacity = 1,250 notifications/second

**Infrastructure Sizing**:
- Redis Cluster: 3 shards, 16GB total memory
- PostgreSQL: Primary + 2 read replicas, connection pooling
- ECS Tasks: Auto-scaling based on queue depth and CPU utilization

**Rationale**: Version A's user engagement assumptions are more realistic for social applications than Version B's conservative estimates.

## 5. Failure Handling Strategy

### Retry Mechanisms

**Channel-Specific Retry Strategy**:
```python
RETRY_CONFIGS = {
    'push': {
        'max_attempts': 3,
        'delays': [60, 300, 900],  # 1min, 5min, 15min
        'backoff': 'exponential'
    },
    'email': {
        'max_attempts': 5, 
        'delays': [300, 1800, 7200, 21600, 86400],  # 5min to 24hr
        'backoff': 'exponential'
    },
    'sms': {
        'max_attempts': 2,
        'delays': [60, 300],  # Cost-conscious retry
        'backoff': 'linear'
    }
}
```

**Circuit Breaker Implementation**:
- **Failure Threshold**: 50% error rate over 5-minute window
- **Circuit States**: Closed → Open (30s) → Half-Open (10 test requests)
- **Per-Channel**: Independent circuit breakers for each delivery channel
- **Fallback**: Automatic channel failover based on user preferences

### Dead Letter Queue Strategy

**DLQ Processing**:
- Failed notifications after max retries → PostgreSQL `failed_notifications` table
- Daily automated report generation for manual review
- Replay capability for resolved infrastructure issues
- 30-day retention with automated cleanup

### Graceful Degradation

**Degradation Hierarchy**:
1. **Channel Failure**: Automatic failover to user's secondary preference
2. **Queue Overload**: Priority-based dropping (low priority first)
3. **Database Issues**: Read-only mode with cached preferences
4. **Redis Failure**: Synchronous processing with reduced throughput

**Rationale**: Maintains Version A's comprehensive failure handling while adopting Version B's realistic complexity assessment.

## 6. Implementation Timeline (6 Months)

### Phase 1: Foundation (Months 1-2)
**Team Allocation**: 
- **Senior Engineer 1**: Infrastructure setup (ECS, Redis, RDS)
- **Senior Engineer 2**: Core notification service and push integration
- **Engineer 3**: User preference integration and API
- **Engineer 4**: Monitoring, logging, and basic admin tools

**Deliverables**:
- Push notifications operational for 100K+ users
- User preference management with database integration
- Redis queue system with priority handling
- Basic monitoring and alerting infrastructure

**Success Criteria**: 10K push notifications/day with >90% delivery rate

### Phase 2: Multi-Channel & Scale (Months 3-4)
**Team Allocation**:
- **Engineers 1-2**: Email integration with SendGrid, template system
- **Engineer 3**: In-app notification API and mobile integration
- **Engineer 4**: Performance optimization, auto-scaling, load testing

**Deliverables**:
- Email notifications with proper deliverability setup
- In-app notification polling API
- Batching and priority processing logic
- Auto-scaling based on queue depth and system load

**Success Criteria**: 500K notifications/day across all channels with <5 minute P2 latency

### Phase 3: Polish & SMS (Months 5-6)
**Team Allocation**:
- **Engineer 1**: SMS integration for security notifications
- **Engineer 2**: Advanced analytics and business metrics dashboard
- **Engineers 3-4**: Performance tuning, reliability improvements, documentation

**Deliverables**:
- SMS for critical security notifications
- Comprehensive analytics dashboard
- Load testing validation for 10M MAU scale
- Complete system documentation and runbooks

**Success Criteria**: Full 10M MAU support with all SLAs met

**Rationale**: Maintains Version A's comprehensive feature development while adopting Version B's realistic team allocation and skill-appropriate task distribution.

## 7. Key Tradeoffs and Decisions

### Technology Complexity vs. Team Capability
**Decision**: Managed services with upgrade paths
- Start with Redis, design for Kafka migration
- ECS instead of Kubernetes for operational simplicity  
- Leverage AWS managed services to reduce operational burden
- **Rationale**: 4-person team must focus on business logic, not infrastructure operations

### Performance vs. Cost Optimization
**Decision**: Cost-conscious scaling with performance headroom
- SMS limited to security use cases only
- Email volume capped at sustainable levels
- Infrastructure sized for 2x current requirements
- **Rationale**: Sustainable growth model that can expand with business success

### Feature Completeness vs. Time to Market
**Decision**: Phased delivery with solid foundations
- MVP push notifications first, then expand channels
- Core reliability features (retries, monitoring) from day one
- Advanced features (complex batching, ML personalization) deferred
- **Rationale**: Early user value while building scalable foundations

## 8. Success Metrics & Monitoring

### Technical KPIs
- **Delivery Rate**: >95% for push, >90% for email (Version A's targets with Version B's realism)
- **Latency**: <2 minutes end-to-end for P1 notifications
- **Uptime**: 99.9% system availability
- **Throughput**: Support 1,250 notifications/second sustained

### Business KPIs
- **Engagement**: 12% click-through rate on push notifications (between industry average and optimistic)
- **Opt-out Rate**: <7% monthly churn from notifications
- **Cost per Notification**: <$0.0015 average across all channels
- **User Satisfaction**: >4.0/5.0 rating for notification relevance

### Monitoring Implementation
```python
# Custom CloudWatch metrics
class NotificationMetrics:
    def record_delivery(self, channel, success, latency_ms):
        cloudwatch.put_metric_data(
            Namespace='NotificationSystem',
            MetricData=[
                {
                    'MetricName': f'{channel}_delivery_rate',
                    'Value': 1 if success else 0,
                    'Unit': 'Count',
                    'Dimensions': [{'Name': 'Channel', 'Value': channel}]
                },
                {
                    'MetricName': f'{channel}_latency',
                    'Value': latency_ms,
                    'Unit': 'Milliseconds'
                }
            ]
        )
```

## 9. Security & Compliance

### Data Protection & Privacy
- **GDPR Compliance**: EU users opt-out by default, right to be forgotten implementation
- **Data Encryption**: TLS 1.3 in transit, AES-256 at rest for all user data
- **API Security**: JWT authentication for internal services, rate limiting on public APIs
- **Audit Trail**: Structured logging of all notification events with user consent tracking