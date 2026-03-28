# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system for a social app with 10M MAU, designed for delivery within 6 months by 4 backend engineers. The system prioritizes reliability, user experience, and operational simplicity while managing infrastructure costs. Key design decisions favor proven technologies over cutting-edge solutions to ensure delivery within timeline and resource constraints.

## 1. System Architecture Overview

### Core Components
- **Notification Service API** - Event ingestion and routing
- **Channel Processors** - Delivery-specific logic for each channel
- **Preference Engine** - User settings and filtering
- **Queue System** - Batching and priority management
- **Analytics & Monitoring** - Delivery tracking and system health

### Technology Stack
- **Primary Database**: PostgreSQL (existing team expertise)
- **Queue System**: Redis + Bull Queue (Node.js compatible)
- **Caching**: Redis (shared with queue system)
- **External Services**: 
  - Push: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
  - Email: SendGrid
  - SMS: Twilio

**Rationale**: Leveraging existing team PostgreSQL expertise reduces learning curve. Redis handles both caching and queuing, minimizing operational complexity.

## 2. Delivery Channels Implementation

### 2.1 Push Notifications
**Technology**: FCM (Android) + APNs (iOS) via `node-pushnotifications` library

**Implementation**:
```javascript
// Push notification structure
{
  userId: string,
  deviceTokens: string[],
  payload: {
    title: string,
    body: string,
    data: object,
    badge?: number
  },
  priority: 'high' | 'normal',
  timeToLive: number // seconds
}
```

**Delivery Logic**:
- Batch size: 1000 notifications per API call
- Retry logic: 3 attempts with exponential backoff
- Token cleanup: Remove invalid tokens after 3 consecutive failures

### 2.2 Email Notifications
**Technology**: SendGrid with dynamic templates

**Implementation**:
- Template-based system for consistent branding
- Batch size: 1000 emails per API call (SendGrid limit)
- Unsubscribe handling via SendGrid webhooks
- Bounce/spam feedback processing

### 2.3 In-App Notifications
**Storage**: PostgreSQL table with 90-day retention

```sql
CREATE TABLE in_app_notifications (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  type VARCHAR(50) NOT NULL,
  title VARCHAR(255) NOT NULL,
  content TEXT,
  data JSONB,
  read_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  INDEX idx_user_created (user_id, created_at DESC)
);
```

**Delivery**: WebSocket connection with Redis pub/sub for real-time delivery

### 2.4 SMS Notifications
**Technology**: Twilio
**Usage**: High-priority notifications only (security, critical updates)
**Rate Limiting**: 5 SMS per user per day to control costs

## 3. Priority and Batching Logic

### 3.1 Priority Levels
1. **Critical** (0-30 seconds): Security alerts, account issues
2. **High** (0-5 minutes): Direct messages, mentions, friend requests  
3. **Medium** (5-30 minutes): Likes, comments, group activity
4. **Low** (30 minutes - 2 hours): Weekly digests, recommendations

### 3.2 Batching Strategy
**Queue Structure**: Separate Redis queues per priority level
- `notifications:critical`
- `notifications:high` 
- `notifications:medium`
- `notifications:low`

**Processing Rules**:
- Critical: Process immediately, no batching
- High: Batch every 30 seconds or 100 notifications
- Medium: Batch every 5 minutes or 500 notifications  
- Low: Batch every 30 minutes or 2000 notifications

**Implementation**:
```javascript
// Bull Queue configuration
const queues = {
  critical: new Bull('critical', { redis: redisConfig }),
  high: new Bull('high', { redis: redisConfig }),
  medium: new Bull('medium', { redis: redisConfig }),
  low: new Bull('low', { redis: redisConfig })
};

// Batch processing
queues.medium.process('batch', 10, async (job) => {
  const notifications = await getBatchedNotifications(job.data.batchId);
  return await processNotificationBatch(notifications);
});
```

## 4. User Preference Management

### 4.1 Database Schema
```sql
CREATE TABLE user_notification_preferences (
  user_id INTEGER PRIMARY KEY,
  channel_preferences JSONB NOT NULL DEFAULT '{}',
  category_preferences JSONB NOT NULL DEFAULT '{}',
  quiet_hours JSONB,
  frequency_settings JSONB,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Example data structure
{
  "channel_preferences": {
    "push": true,
    "email": true,
    "sms": false,
    "in_app": true
  },
  "category_preferences": {
    "social_interactions": {"push": true, "email": false},
    "security": {"push": true, "email": true, "sms": true},
    "marketing": {"push": false, "email": true}
  },
  "quiet_hours": {
    "enabled": true,
    "start": "22:00",
    "end": "08:00",
    "timezone": "America/New_York"
  }
}
```

### 4.2 Preference Engine
**Caching Strategy**: Redis cache with 1-hour TTL for active users
**Default Behavior**: Opt-in for critical notifications, opt-out for marketing

**Filtering Logic**:
1. Check global channel preferences
2. Apply category-specific overrides
3. Respect quiet hours for non-critical notifications
4. Apply frequency limits (max 20 push notifications per day)

## 5. Infrastructure Choices and Scaling

### 5.1 Compute Resources
**Initial Setup** (handles 2-3M MAU):
- 3x API servers (4 vCPU, 8GB RAM)
- 2x Queue processors (2 vCPU, 4GB RAM)  
- 1x PostgreSQL (8 vCPU, 32GB RAM)
- 1x Redis cluster (4 vCPU, 16GB RAM)

**Scaling Plan** (to 10M MAU):
- Horizontal scaling of API servers and queue processors
- Database read replicas for preference lookups
- Redis cluster for queue partitioning

### 5.2 Cost Optimization
**Push Notifications**: Free (FCM/APNs)
**Email**: ~$300/month (SendGrid Essentials)
**SMS**: ~$1000/month (Twilio, 50k messages)
**Infrastructure**: ~$2000/month (AWS/GCP)

**Total Estimated Cost**: $3,300/month at full scale

### 5.3 Performance Targets
- **Throughput**: 10,000 notifications/second peak
- **Latency**: 
  - Critical: <30 seconds
  - High: <5 minutes
  - Medium/Low: Best effort
- **Reliability**: 99.9% delivery success rate

## 6. Failure Handling and Reliability

### 6.1 Retry Logic
**Exponential Backoff Strategy**:
```javascript
const retryDelays = [1000, 5000, 25000]; // 1s, 5s, 25s

async function processWithRetry(notification, attempt = 0) {
  try {
    return await deliverNotification(notification);
  } catch (error) {
    if (attempt < retryDelays.length && isRetryableError(error)) {
      await delay(retryDelays[attempt]);
      return processWithRetry(notification, attempt + 1);
    }
    throw error;
  }
}
```

### 6.2 Dead Letter Queue
Failed notifications after all retries move to dead letter queue for investigation
- Store failed notification details
- Alert engineering team for manual review
- Attempt redelivery after fixes

### 6.3 Circuit Breaker Pattern
Implement circuit breakers for external services:
- Open circuit after 10 consecutive failures
- Half-open after 60 seconds
- Prevent cascade failures

### 6.4 Monitoring and Alerting
**Key Metrics**:
- Delivery success rate by channel
- Queue depth and processing time
- Error rates and types
- User engagement rates

**Alerting Thresholds**:
- Queue depth > 10,000 notifications
- Delivery success rate < 95%
- Processing time > 2x normal
- External service errors > 5%

## 7. Implementation Timeline (6 Months)

### Month 1-2: Foundation
- Database schema design and migration
- Basic notification service API
- Redis queue setup
- Push notification integration (FCM/APNs)

### Month 3-4: Core Features  
- Email integration (SendGrid)
- SMS integration (Twilio)
- In-app notification system
- User preference management

### Month 5: Advanced Features
- Batching and priority logic
- Quiet hours and frequency limiting  
- Analytics and monitoring
- Performance optimization

### Month 6: Production Readiness
- Load testing and performance tuning
- Security audit and hardening
- Documentation and runbooks
- Gradual rollout and monitoring

## 8. Team Allocation

**Engineer 1 (Senior)**: System architecture, infrastructure, deployment
**Engineer 2**: Push notifications, mobile integration, WebSocket handling  
**Engineer 3**: Email/SMS integration, external service management
**Engineer 4**: Preference engine, analytics, monitoring

## 9. Key Tradeoffs and Decisions

### 9.1 PostgreSQL vs. NoSQL
**Chosen**: PostgreSQL
**Rationale**: Team expertise, ACID compliance for preferences, good JSON support
**Tradeoff**: May require read replicas sooner than NoSQL solution

### 9.2 Self-hosted vs. Managed Queue
**Chosen**: Self-hosted Redis + Bull Queue
**Rationale**: Cost control, team Node.js expertise, simpler debugging
**Tradeoff**: More operational overhead vs. managed solutions (SQS, Pub/Sub)

### 9.3 Real-time vs. Batch Processing
**Chosen**: Hybrid approach with priority-based batching
**Rationale**: Balance between user experience and system efficiency
**Tradeoff**: Complexity vs. pure real-time or pure batch approaches

### 9.4 Multi-tenancy Strategy
**Chosen**: Single database with user-based partitioning
**Rationale**: Simpler operations, sufficient for current scale
**Tradeoff**: May need database sharding beyond 20M MAU

## 10. Success Metrics

### Technical Metrics
- 99.9% uptime
- <30 second delivery for critical notifications
- <5% failed delivery rate
- <200ms API response time

### Business Metrics  
- >25% push notification open rate
- >5% email click-through rate
- <2% unsubscribe rate
- >80% user preference completion

This notification system design balances scalability, reliability, and development velocity within the specified constraints. The phased implementation approach ensures delivery milestones while building toward a production-ready system that can scale with user growth.