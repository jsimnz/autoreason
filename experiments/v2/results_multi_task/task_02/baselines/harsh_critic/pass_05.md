# NOTIFICATION SYSTEM FOR 10M MAU SOCIAL APP
**Complete Implementation Guide for 4 Backend Engineers, 6 Months**

## Executive Summary

This proposal delivers a **production-ready notification system** that handles 10M Monthly Active Users through a pragmatic, phased approach. We prioritize **operational simplicity** and **measurable reliability** over premature optimization.

**Key Principles:**
- Start with proven patterns that work at scale
- Build observability before complexity
- Scale infrastructure based on actual metrics, not projections
- Design for 99.9% uptime, not 99.99%

## 1. Reality-Based Scale Analysis

### 1.1 Actual Usage Patterns (Data-Driven Projections)
```
10M MAU Reality Check:
├── Daily Active Users: 1.2M (12% conversion typical for mature social apps)
├── Peak Concurrent Users: 120K (10% of DAU during regional prime time)
├── Geographic Distribution: 45% US, 25% Europe, 20% Asia-Pacific, 10% Other
├── Notification Engagement: 15-25% open rate, 60% of users disable some categories
└── Daily Notification Volume: 3-5M total across all channels

Peak Load Characteristics:
├── Push Notifications: 8K-12K/minute during breaking news/viral content
├── Email: 2K-3K/minute during digest sends
├── SMS: 200-500/minute (premium feature, low adoption)
└── In-App: 15K-20K/minute during peak concurrent hours
```

### 1.2 Infrastructure Scaling Timeline

**Phase 1 (Months 1-3): Foundation - Handle 2M DAU**
```yaml
AWS Infrastructure:
  Application Tier:
    - 3x c5.large instances behind Application Load Balancer
    - Auto Scaling Group (min: 3, max: 8, target: 70% CPU)
    - AWS Certificate Manager for TLS termination
  
  Database Tier:
    - Aurora PostgreSQL 14.x cluster (db.r5.large writer + 1 read replica)
    - Automated backups with 7-day retention
    - Enhanced monitoring enabled
  
  Caching & Queuing:
    - ElastiCache Redis 7.x (cache.r5.large, single node)
    - 4x SQS Standard queues (high/normal/low priority + DLQ)
    - CloudWatch alarms for queue depth
  
  External Services:
    - Firebase Cloud Messaging (FCM) for Android
    - Apple Push Notification Service (APNs) for iOS
    - AWS Simple Email Service (SES) - 200 emails/second limit
    - AWS Simple Notification Service (SNS) for SMS

Monthly Cost: ~$2,400
Capacity: 5M notifications/day, 50K concurrent users
```

**Phase 2 (Months 4-6): Production Scale - Handle 5M DAU**
```yaml
Scaled Infrastructure:
  Application Tier:
    - 6x c5.xlarge instances (based on actual CPU/memory metrics)
    - Auto Scaling Group (min: 6, max: 15)
    - Multiple AZ deployment for high availability
  
  Database Tier:
    - Aurora PostgreSQL (db.r5.xlarge writer + 2 read replicas)
    - Cross-region backup replication
    - Performance Insights enabled
  
  Caching & Queuing:
    - ElastiCache Redis cluster (3 nodes, cache.r5.large each)
    - SQS FIFO queues for ordered notifications
    - Dead Letter Queues with automated retry logic
  
  Monitoring & Observability:
    - DataDog APM for application performance monitoring
    - AWS X-Ray for distributed tracing
    - PagerDuty for incident management

Monthly Cost: ~$6,800
Capacity: 15M notifications/day, 150K concurrent users
```

## 2. Team Structure & Timeline

### 2.1 Engineer Allocation Strategy

**Backend Engineer 1 (Tech Lead)**
- Months 1-2: Core API framework, database schema, authentication
- Months 3-4: Performance optimization, caching layer implementation
- Months 5-6: Production monitoring, capacity planning, documentation

**Backend Engineer 2 (Push Notifications Specialist)**
- Months 1-2: FCM/APNs integration, device token management
- Months 3-4: Push notification batching, delivery tracking
- Months 5-6: Advanced push features (rich media, interactive notifications)

**Backend Engineer 3 (Multi-Channel Integration)**
- Months 1-2: Email service integration (SES), basic SMS setup
- Months 3-4: In-app notification system, notification history API
- Months 5-6: Advanced email templates, SMS optimization

**Backend Engineer 4 (Preferences & Infrastructure)**
- Months 1-2: User preference management, quiet hours logic
- Months 3-4: Admin dashboard, notification analytics
- Months 5-6: Infrastructure automation, disaster recovery procedures

### 2.2 Monthly Milestones

**Month 1: Foundation**
- ✅ Database schema deployed
- ✅ Basic push notification sending (FCM/APNs)
- ✅ User preference API (CRUD operations)
- ✅ Simple email notifications via SES

**Month 2: Core Features**
- ✅ In-app notification inbox
- ✅ Priority queue processing
- ✅ Basic batching logic (500 notifications/batch)
- ✅ Delivery status tracking

**Month 3: Production Readiness**
- ✅ Comprehensive monitoring and alerting
- ✅ Load testing (simulate 2x expected load)
- ✅ Error handling and retry mechanisms
- ✅ API rate limiting and authentication

**Month 4: Advanced Features**
- ✅ Quiet hours and timezone handling
- ✅ Notification templates and personalization
- ✅ SMS integration and fallback logic
- ✅ Admin dashboard for operations team

**Month 5: Scale Preparation**
- ✅ Performance optimization based on load test results
- ✅ Infrastructure scaling automation
- ✅ Disaster recovery procedures tested
- ✅ Documentation and runbooks completed

**Month 6: Production Launch**
- ✅ Gradual rollout (10% → 50% → 100% of users)
- ✅ Real-time monitoring and incident response
- ✅ Performance tuning based on actual usage
- ✅ Post-launch optimization and bug fixes

## 3. Database Design: Optimized for Performance

### 3.1 Core Schema (Production-Ready)

```sql
-- User notification preferences with intelligent indexing
CREATE TABLE user_preferences (
    user_id BIGINT PRIMARY KEY,
    
    -- Channel preferences (optimized for common queries)
    push_enabled BOOLEAN NOT NULL DEFAULT true,
    email_enabled BOOLEAN NOT NULL DEFAULT true,
    sms_enabled BOOLEAN NOT NULL DEFAULT false,
    in_app_enabled BOOLEAN NOT NULL DEFAULT true,
    
    -- Contact information with validation
    email VARCHAR(254), -- RFC 5321 maximum length
    phone VARCHAR(20),  -- E.164 format
    
    -- Timezone handling (store as IANA timezone identifier)
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    
    -- Category preferences (extensible but performant)
    enabled_categories TEXT[] NOT NULL DEFAULT ARRAY['social', 'system', 'marketing'],
    disabled_categories TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    
    -- Quiet hours (stored as minutes from midnight in user's timezone)
    quiet_start_minutes INTEGER, -- 0-1439 (22:00 = 1320 minutes)
    quiet_end_minutes INTEGER,   -- 0-1439 (08:00 = 480 minutes)
    
    -- Frequency controls
    max_push_per_hour INTEGER NOT NULL DEFAULT 10,
    max_email_per_day INTEGER NOT NULL DEFAULT 5,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE
);

-- Optimized indexes for common query patterns
CREATE INDEX idx_user_prefs_email_enabled ON user_preferences(email) 
    WHERE email_enabled = true AND email IS NOT NULL;
CREATE INDEX idx_user_prefs_push_enabled ON user_preferences(user_id) 
    WHERE push_enabled = true;
CREATE INDEX idx_user_prefs_updated ON user_preferences(updated_at DESC);

-- Device tokens with automatic cleanup
CREATE TABLE device_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    platform VARCHAR(10) NOT NULL CHECK (platform IN ('ios', 'android', 'web')),
    token_hash VARCHAR(64) NOT NULL, -- SHA-256 hash for security
    token_encrypted BYTEA NOT NULL,  -- Encrypted actual token
    app_version VARCHAR(20),
    device_model VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    -- Tracking for cleanup
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    failure_count INTEGER NOT NULL DEFAULT 0,
    
    -- Foreign key with cascade delete
    CONSTRAINT fk_device_tokens_user FOREIGN KEY (user_id) 
        REFERENCES user_preferences(user_id) ON DELETE CASCADE,
    
    -- Prevent duplicate tokens
    UNIQUE(user_id, platform, token_hash)
);

-- Indexes for device token management
CREATE INDEX idx_device_tokens_user_active ON device_tokens(user_id, platform) 
    WHERE is_active = true;
CREATE INDEX idx_device_tokens_cleanup ON device_tokens(last_used_at, failure_count) 
    WHERE is_active = true;
CREATE INDEX idx_device_tokens_hash ON device_tokens(token_hash);

-- Notification queue (for async processing)
CREATE TABLE notification_queue (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    
    -- Message content
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    
    -- Delivery configuration
    channels TEXT[] NOT NULL, -- ['push', 'email', 'sms', 'in_app']
    priority INTEGER NOT NULL CHECK (priority IN (1, 2, 3)), -- 1=high, 2=normal, 3=low
    
    -- Scheduling
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Rich content (optional)
    image_url VARCHAR(1000),
    action_url VARCHAR(1000),
    custom_data JSONB DEFAULT '{}',
    
    -- Processing status
    status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'expired')),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    
    -- Error tracking
    last_error TEXT,
    last_attempted_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for queue processing
CREATE INDEX idx_notification_queue_processing ON notification_queue(scheduled_at, priority, status) 
    WHERE status = 'pending';
CREATE INDEX idx_notification_queue_user ON notification_queue(user_id, created_at DESC);
CREATE INDEX idx_notification_queue_cleanup ON notification_queue(created_at) 
    WHERE status IN ('completed', 'failed', 'expired');

-- Delivery tracking (for analytics and debugging)
CREATE TABLE notification_deliveries (
    id BIGSERIAL PRIMARY KEY,
    queue_id BIGINT NOT NULL REFERENCES notification_queue(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    channel VARCHAR(20) NOT NULL,
    
    -- External service tracking
    external_id VARCHAR(255), -- FCM message ID, SES message ID, etc.
    provider_response JSONB,
    
    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'sent'
        CHECK (status IN ('sent', 'delivered', 'failed', 'bounced', 'opened', 'clicked')),
    error_code VARCHAR(50),
    error_message TEXT,
    
    -- Timing
    sent_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMP WITH TIME ZONE,
    opened_at TIMESTAMP WITH TIME ZONE,
    clicked_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for delivery analytics
CREATE INDEX idx_deliveries_queue ON notification_deliveries(queue_id);
CREATE INDEX idx_deliveries_user_channel ON notification_deliveries(user_id, channel, sent_at DESC);
CREATE INDEX idx_deliveries_status_time ON notification_deliveries(status, sent_at);

-- In-app notifications (user inbox)
CREATE TABLE user_notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    
    -- Content
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    
    -- Rich content
    image_url VARCHAR(1000),
    action_url VARCHAR(1000),
    custom_data JSONB DEFAULT '{}',
    
    -- User interaction
    is_read BOOLEAN NOT NULL DEFAULT false,
    is_archived BOOLEAN NOT NULL DEFAULT false,
    
    -- Lifecycle
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    read_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() + INTERVAL '30 days'),
    
    -- Reference to original notification
    source_queue_id BIGINT REFERENCES notification_queue(id) ON DELETE SET NULL
);

-- Indexes for inbox queries
CREATE INDEX idx_user_notifications_inbox ON user_notifications(user_id, created_at DESC) 
    WHERE is_archived = false AND expires_at > NOW();
CREATE INDEX idx_user_notifications_unread ON user_notifications(user_id, is_read, created_at DESC) 
    WHERE is_archived = false;
CREATE INDEX idx_user_notifications_cleanup ON user_notifications(expires_at) 
    WHERE expires_at < NOW();

-- Rate limiting tracking
CREATE TABLE rate_limits (
    user_id BIGINT NOT NULL,
    channel VARCHAR(20) NOT NULL,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    
    PRIMARY KEY (user_id, channel, window_start)
);

-- Index for rate limit checks
CREATE INDEX idx_rate_limits_check ON rate_limits(user_id, channel, window_start DESC);
```

### 3.2 Database Maintenance & Optimization

```sql
-- Automated cleanup procedures (run via scheduled jobs)

-- Clean up old notification queue entries (retain 30 days)
CREATE OR REPLACE FUNCTION cleanup_notification_queue()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM notification_queue 
    WHERE created_at < NOW() - INTERVAL '30 days'
    AND status IN ('completed', 'failed', 'expired');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Clean up old delivery records (retain 90 days)
CREATE OR REPLACE FUNCTION cleanup_delivery_records()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM notification_deliveries 
    WHERE sent_at < NOW() - INTERVAL '90 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Clean up expired in-app notifications
CREATE OR REPLACE FUNCTION cleanup_expired_notifications()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_notifications 
    WHERE expires_at < NOW() 
    OR (is_archived = true AND created_at < NOW() - INTERVAL '7 days');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Clean up inactive device tokens
CREATE OR REPLACE FUNCTION cleanup_device_tokens()
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER;