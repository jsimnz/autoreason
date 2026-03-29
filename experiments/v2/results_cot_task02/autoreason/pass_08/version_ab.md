# Notification System Design for Social App (10M MAU) - Strategic Synthesis

## Executive Summary

Building notification infrastructure for 10M users with 4 backend engineers requires a **pragmatic hybrid approach** that prioritizes reliability and maintainability over feature completeness. This synthesis combines the most robust technical architecture with realistic project constraints.

**Key Strategic Decision**: Hybrid architecture using proven third-party services (OneSignal, SendGrid) with custom orchestration layer, delivering enterprise-grade reliability at manageable cost and complexity.

**Bottom Line**: $415K development cost and $7,950/month operational cost for a production-ready system that reliably handles 10M users with room for 5x growth.

---

## Strategic Architecture: Hybrid Approach

### High-Level System Design

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │  Notification   │    │   Message       │
│   (Kong)        │────│  Orchestrator   │────│   Queue         │
│   Rate Limiting │    │   (Go Service)  │    │   (Redis Cluster)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Prefs    │    │   Analytics     │    │   Channel       │
│   Database      │────│   Pipeline      │────│   Workers       │
│   (PostgreSQL)  │    │   (ClickHouse)  │    │   (Kubernetes)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                              ┌─────────────────┐
                                              │  Third-Party    │
                                              │  Services       │
                                              │  • OneSignal    │
                                              │  • SendGrid     │
                                              │  • Twilio       │
                                              └─────────────────┘
```

### Delivery Channel Strategy

**Push Notifications (OneSignal + Firebase FCM Backup):**
- **Primary**: OneSignal ($2,000/month for 10M users)
- **Backup**: Firebase FCM (free tier as failover)
- **Rationale**: OneSignal provides 95%+ delivery rates with simpler integration than FCM enterprise
- **Features**: Advanced segmentation, A/B testing, delivery analytics

**Email (SendGrid):**
- **Cost**: $500/month for 5M emails with dedicated IP
- **Features**: Template management, reputation monitoring, compliance tools
- **Integration**: SMTP relay with comprehensive webhook callbacks

**SMS (Twilio):**
- **Cost**: $2,000/month (2FA + critical alerts only)
- **Usage**: Emergency notifications, verification codes, high-value user retention
- **Compliance**: TCPA-compliant opt-in tracking with global short codes

**In-App (Custom WebSocket + Redis):**
- **Cost**: $800/month for infrastructure
- **Implementation**: Horizontally scalable WebSocket service with Redis pub/sub
- **Fallback**: Server-sent events for connection issues, polling API as last resort

---

## Database Architecture: Performance-Optimized

### User Preferences Schema (Production-Ready)

```sql
-- Hash partitioned for optimal distribution and query performance
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    quiet_hours JSONB DEFAULT '{"start": "22:00", "end": "08:00", "timezone": "UTC"}',
    email_frequency VARCHAR(20) DEFAULT 'immediate', -- immediate, hourly, daily
    push_frequency VARCHAR(20) DEFAULT 'immediate',
    category_preferences JSONB DEFAULT '{}', -- {"likes": true, "comments": true, "follows": false}
    frequency_limits JSONB DEFAULT '{"email_daily_max": 5, "push_hourly_max": 10}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
) PARTITION BY HASH (user_id);

-- Create 8 partitions for balanced load distribution
CREATE TABLE user_preferences_0 PARTITION OF user_notification_preferences
    FOR VALUES WITH (modulus 8, remainder 0);
-- Repeat for remainder 1-7

-- Optimized indexes for common query patterns
CREATE INDEX idx_user_prefs_push_enabled ON user_notification_preferences (push_enabled) 
    WHERE push_enabled = true;
CREATE INDEX idx_user_prefs_email_enabled ON user_notification_preferences (email_enabled) 
    WHERE email_enabled = true;
CREATE INDEX idx_user_prefs_updated ON user_notification_preferences (updated_at);

-- GIN index for efficient JSON queries
CREATE INDEX idx_user_prefs_categories ON user_notification_preferences 
    USING GIN (category_preferences);
```

### Device Token Management (Security-First)

```sql
CREATE TABLE device_tokens (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    platform VARCHAR(10) CHECK (platform IN ('ios', 'android', 'web')),
    token_fingerprint CHAR(64) UNIQUE NOT NULL, -- SHA-256 of token for deduplication
    encrypted_token BYTEA NOT NULL, -- AES-256-GCM encrypted actual token
    encryption_key_id VARCHAR(50) NOT NULL, -- References key management service
    is_active BOOLEAN DEFAULT true,
    last_used TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    PRIMARY KEY (user_id, platform, id)
) PARTITION BY HASH (user_id);

-- Create 8 partitions for distribution
CREATE TABLE device_tokens_0 PARTITION OF device_tokens 
    FOR VALUES WITH (modulus 8, remainder 0);
-- Repeat for remainder 1-7

-- Performance indexes
CREATE INDEX idx_device_tokens_user_active ON device_tokens (user_id) 
    WHERE is_active = true;
CREATE INDEX idx_device_tokens_fingerprint ON device_tokens (token_fingerprint) 
    WHERE is_active = true;
CREATE INDEX idx_device_tokens_expires ON device_tokens (expires_at) 
    WHERE expires_at IS NOT NULL;
```

### Message Tracking (Time-Partitioned for Analytics)

```sql
CREATE TABLE notification_logs (
    message_id UUID,
    user_id BIGINT NOT NULL,
    notification_type VARCHAR(50),
    channels TEXT[],
    priority VARCHAR(10) CHECK (priority IN ('critical', 'high', 'normal', 'low')),
    status VARCHAR(20) DEFAULT 'queued',
    batch_id UUID,
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    error_code VARCHAR(50),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (created_at, message_id)
) PARTITION BY RANGE (created_at);

-- Monthly partitions with automatic creation
CREATE TABLE notification_logs_2024_01 PARTITION OF notification_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Indexes optimized for analytics queries
CREATE INDEX idx_notif_logs_2024_01_user_id ON notification_logs_2024_01 (user_id, created_at);
CREATE INDEX idx_notif_logs_2024_01_status ON notification_logs_2024_01 (status, created_at);
CREATE INDEX idx_notif_logs_2024_01_type ON notification_logs_2024_01 (notification_type, created_at);
```

---

## Message Processing Engine (Production-Grade)

### Priority-Based Processing with Smart Batching

```go
type NotificationPriority int
const (
    PriorityCritical NotificationPriority = 1 // Security alerts, system outages
    PriorityHigh     NotificationPriority = 2 // Direct messages, mentions
    PriorityNormal   NotificationPriority = 3 // Likes, comments, follows
    PriorityLow      NotificationPriority = 4 // Marketing, recommendations
)

type NotificationRequest struct {
    MessageID       string                `json:"message_id"`
    UserIDs         []int64              `json:"user_ids"`
    Type            string               `json:"type"`
    Priority        NotificationPriority `json:"priority"`
    Channels        []Channel            `json:"channels"`
    Content         NotificationContent  `json:"content"`
    DeduplicationID string               `json:"deduplication_id,omitempty"`
    ExpiresAt       *time.Time           `json:"expires_at,omitempty"`
    Scheduling      *ScheduleConfig      `json:"scheduling,omitempty"`
}

type MessageOrchestrator struct {
    redisClient     *redis.ClusterClient
    dbPool          *pgxpool.Pool
    channelWorkers  map[Channel]*ChannelWorker
    circuitBreakers map[string]*CircuitBreaker
    deduplicator    *MessageDeduplicator
    keyManager      *EncryptionKeyManager
    metrics         *prometheus.Registry
}

func (m *MessageOrchestrator) ProcessNotification(ctx context.Context, req NotificationRequest) error {
    // 1. Validate and deduplicate
    if err := m.validateRequest(req); err != nil {
        return fmt.Errorf("validation failed: %w", err)
    }
    
    if m.deduplicator.IsDuplicate(req.DeduplicationID, req.Type) {
        m.metrics.Counter("duplicate_messages_filtered").Inc()
        return nil // Silent success for duplicates
    }
    
    // 2. Apply user preferences with comprehensive filtering
    filteredUsers, err := m.applyUserPreferencesWithFallback(ctx, req)
    if err != nil {
        return fmt.Errorf("preference filtering failed: %w", err)
    }
    
    if len(filteredUsers) == 0 {
        m.metrics.Counter("notifications_filtered_out_completely").Inc()
        return nil
    }
    
    // 3. Critical messages bypass batching and rate limiting
    if req.Priority == PriorityCritical {
        return m.processImmediately(ctx, req, filteredUsers)
    }
    
    // 4. Intelligent batching for normal priority messages
    return m.processBatched(ctx, req, filteredUsers)
}
```

### Advanced Batching with Timezone Optimization

```go
type BatchConfig struct {
    MaxBatchSize     int           `json:"max_batch_size"`     // 1000 for push, 100 for email
    MaxWaitTime      time.Duration `json:"max_wait_time"`      // 30s for normal, 5s for high
    RateLimitPerSec  int           `json:"rate_limit_per_sec"` // API rate limits
    TimezoneOptimize bool          `json:"timezone_optimize"`  // Optimize delivery timing
}

func (m *MessageOrchestrator) processBatched(ctx context.Context, req NotificationRequest, users []UserTarget) error {
    channelBatches := make(map[Channel][]Batch)
    
    for _, channel := range req.Channels {
        channelUsers := m.filterUsersByChannelCapability(users, channel)
        config := m.getBatchConfig(channel, req.Priority)
        
        // For non-urgent messages, optimize by timezone for better engagement
        if req.Priority > PriorityHigh && config.TimezoneOptimize {
            timezoneGroups := m.groupByOptimalDeliveryTime(channelUsers)
            for timezone, tzUsers := range timezoneGroups {
                batches := m.createBatchesForTimezone(channel, tzUsers, req, timezone, config)
                channelBatches[channel] = append(channelBatches[channel], batches...)
            }
        } else {
            // High priority: process immediately regardless of timezone
            batches := m.createImmediateBatches(channel, channelUsers, req, config)
            channelBatches[channel] = batches
        }
    }
    
    // Queue batches with appropriate priority and delays
    for channel, batches := range channelBatches {
        for _, batch := range batches {
            if err := m.queueBatchWithPriority(ctx, channel, batch, req.Priority); err != nil {
                m.metrics.Counter("batch_queue_errors").WithLabelValues(string(channel)).Inc()
                return fmt.Errorf("failed to queue batch for channel %s: %w", channel, err)
            }
        }
    }
    
    return nil
}

func (m *MessageOrchestrator) groupByOptimalDeliveryTime(users []UserTarget) map[string][]UserTarget {
    timezoneGroups := make(map[string][]UserTarget)
    
    for _, user := range users {
        // Calculate optimal delivery time based on user's timezone and quiet hours
        timezone := user.Preferences.Timezone
        if timezone == "" {
            timezone = "UTC" // Default fallback
        }
        
        // Group users by timezone for batch processing
        timezoneGroups[timezone] = append(timezoneGroups[timezone], user)
    }
    
    return timezoneGroups
}
```

---

## Failure Handling and Resilience (Production-Ready)

### Thread-Safe Circuit Breaker

```go
type CircuitBreaker struct {
    maxFailures     int32
    timeout         time.Duration
    resetTimeout    time.Duration
    
    // Atomic operations for thread safety
    state           int32 // 0=closed, 1=open, 2=half-open
    failureCount    int32
    successCount    int32
    lastFailureTime int64
    
    // Half-open state management
    halfOpenLock    sync.Mutex
    halfOpenAllowed int32
    
    metrics         *prometheus.Registry
}

const (
    StateClosed   = 0
    StateOpen     = 1
    StateHalfOpen = 2
)

func (cb *CircuitBreaker) Execute(ctx context.Context, operation func() error) error {
    state := atomic.LoadInt32(&cb.state)
    
    switch state {
    case StateOpen:
        if time.Since(time.Unix(0, atomic.LoadInt64(&cb.lastFailureTime))) > cb.resetTimeout {
            cb.attemptReset()
        } else {
            cb.metrics.Counter("circuit_breaker_rejected").Inc()
            return ErrCircuitBreakerOpen
        }
    case StateHalfOpen:
        if !cb.tryHalfOpenExecution() {
            return ErrCircuitBreakerOpen
        }
    }
    
    err := operation()
    cb.recordResult(err)
    return err
}

func (cb *CircuitBreaker) attemptReset() {
    cb.halfOpenLock.Lock()
    defer cb.halfOpenLock.Unlock()
    
    if atomic.CompareAndSwapInt32(&cb.state, StateOpen, StateHalfOpen) {
        atomic.StoreInt32(&cb.failureCount, 0)
        atomic.StoreInt32(&cb.successCount, 0)
        atomic.StoreInt32(&cb.halfOpenAllowed, 5) // Allow 5 test requests
        cb.metrics.Counter("circuit_breaker_half_open").Inc()
    }
}

func (cb *CircuitBreaker) recordResult(err error) {
    if err != nil {
        failures := atomic.AddInt32(&cb.failureCount, 1)
        atomic.StoreInt64(&cb.lastFailureTime, time.Now().UnixNano())
        
        if failures >= cb.maxFailures {
            atomic.StoreInt32(&cb.state, StateOpen)
            cb.metrics.Counter("circuit_breaker_opened").Inc()
        }
    } else {
        if atomic.LoadInt32(&cb.state) == StateHalfOpen {
            successes := atomic.AddInt32(&cb.successCount, 1)