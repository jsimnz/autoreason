# Notification System Design for Social App (10M MAU) - Revised Proposal

## Executive Summary

Building notification infrastructure for 10M users with 4 backend engineers requires a **pragmatic hybrid approach** that prioritizes reliability over feature completeness. This revised proposal addresses critical architectural flaws while maintaining realistic delivery expectations.

**Key Changes from Original:**
- Proper database partitioning strategy aligned with query patterns
- Realistic infrastructure sizing and cost estimates
- Comprehensive security and compliance framework
- Conservative timeline with adequate testing phases

**Bottom Line**: $680K development cost and $18,200/month operational cost for a production-ready system that can reliably handle 10M users.

---

## Strategic Architecture: Hybrid Approach (Revised)

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
                                              │  • Firebase FCM │
                                              │  • SendGrid     │
                                              │  • Twilio       │
                                              └─────────────────┘
```

### Delivery Channel Strategy (Revised)

**Push Notifications (Firebase FCM + OneSignal Backup):**
- **Primary**: Firebase FCM (Free up to 1B messages/month)
- **Backup**: OneSignal ($4,800/month for enterprise features)
- **Rationale**: FCM provides Google-grade reliability; OneSignal as failover
- **Delivery Rate Target**: 94-96% (industry realistic)

**Email (SendGrid + Amazon SES Backup):**
- **Primary**: SendGrid ($1,200/month for 10M emails with dedicated IP)
- **Backup**: Amazon SES ($1,000/month for overflow)
- **Features**: Template management, compliance, reputation monitoring

**SMS (Twilio):**
- **Cost**: $5,000/month (2FA + critical alerts only)
- **Usage**: Emergency notifications, verification codes
- **Compliance**: TCPA-compliant opt-in tracking

**In-App (Custom WebSocket Service):**
- **Implementation**: Horizontally scalable WebSocket service
- **Cost**: $2,400/month for infrastructure
- **Fallback**: Server-sent events for connection issues

---

## Database Architecture: Performance-Optimized

### User Preferences Schema (Corrected)

```sql
-- Time-based partitioning for better query performance
CREATE TABLE user_notification_preferences (
    user_id BIGINT,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    email_frequency VARCHAR(20) DEFAULT 'immediate', -- immediate, hourly, daily
    push_frequency VARCHAR(20) DEFAULT 'immediate',
    category_preferences JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id)
);

-- Proper indexes for common query patterns
CREATE INDEX idx_user_prefs_timezone ON user_notification_preferences (timezone);
CREATE INDEX idx_user_prefs_push_enabled ON user_notification_preferences (push_enabled) WHERE push_enabled = true;
CREATE INDEX idx_user_prefs_email_enabled ON user_notification_preferences (email_enabled) WHERE email_enabled = true;
CREATE INDEX idx_user_prefs_updated ON user_notification_preferences (updated_at);

-- GIN index for JSON queries
CREATE INDEX idx_user_prefs_categories ON user_notification_preferences USING GIN (category_preferences);
```

### Device Token Management (Secured)

```sql
CREATE TABLE device_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    platform VARCHAR(10) CHECK (platform IN ('ios', 'android', 'web')),
    token_fingerprint CHAR(64) UNIQUE NOT NULL, -- SHA-256 of token
    encrypted_token BYTEA NOT NULL, -- AES-256-GCM encrypted
    encryption_key_id VARCHAR(50) NOT NULL, -- References key management service
    is_active BOOLEAN DEFAULT true,
    last_used TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
) PARTITION BY HASH (user_id);

-- Create 16 partitions for better distribution
CREATE TABLE device_tokens_00 PARTITION OF device_tokens FOR VALUES WITH (modulus 16, remainder 0);
-- ... repeat for remainder 1-15

-- Proper indexes
CREATE INDEX idx_device_tokens_user_active ON device_tokens (user_id) WHERE is_active = true;
CREATE INDEX idx_device_tokens_platform ON device_tokens (user_id, platform) WHERE is_active = true;
CREATE INDEX idx_device_tokens_expires ON device_tokens (expires_at) WHERE expires_at IS NOT NULL;
```

### Message Tracking (Time-Partitioned)

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

-- Monthly partitions with proper indexes
CREATE TABLE notification_logs_2024_01 PARTITION OF notification_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Indexes for each partition
CREATE INDEX idx_notif_logs_2024_01_user_id ON notification_logs_2024_01 (user_id, created_at);
CREATE INDEX idx_notif_logs_2024_01_status ON notification_logs_2024_01 (status, created_at);
CREATE INDEX idx_notif_logs_2024_01_type ON notification_logs_2024_01 (notification_type, created_at);
```

---

## Message Processing Engine (Robust Implementation)

### Priority-Based Processing

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
        return ErrDuplicateMessage
    }
    
    // 2. Apply user preferences with proper error handling
    filteredUsers, err := m.applyUserPreferencesWithFallback(ctx, req)
    if err != nil {
        return fmt.Errorf("preference filtering failed: %w", err)
    }
    
    // 3. Route by priority - critical messages bypass batching
    if req.Priority == PriorityCritical {
        return m.processImmediately(ctx, req, filteredUsers)
    }
    
    // 4. Batch normal priority messages
    return m.processBatched(ctx, req, filteredUsers)
}
```

### Smart Batching with Deduplication

```go
type MessageDeduplicator struct {
    redis    *redis.ClusterClient
    ttl      time.Duration
}

func (d *MessageDeduplicator) IsDuplicate(dedupeID, msgType string) bool {
    if dedupeID == "" {
        return false
    }
    
    key := fmt.Sprintf("dedupe:%s:%s", msgType, dedupeID)
    result := d.redis.SetNX(context.Background(), key, "1", d.ttl)
    return result.Err() != nil || !result.Val()
}

func (m *MessageOrchestrator) processBatched(ctx context.Context, req NotificationRequest, users []UserTarget) error {
    // Group users by timezone and channel preferences
    channelBatches := make(map[Channel][]Batch)
    
    for _, channel := range req.Channels {
        channelUsers := m.filterUsersByChannelCapability(users, channel)
        
        // For non-critical messages, optimize by timezone
        if req.Priority > PriorityHigh {
            timezoneGroups := m.groupByOptimalDeliveryTime(channelUsers)
            for timezone, tzUsers := range timezoneGroups {
                batches := m.createBatchesForTimezone(channel, tzUsers, req, timezone)
                channelBatches[channel] = append(channelBatches[channel], batches...)
            }
        } else {
            // High priority: process immediately regardless of timezone
            batches := m.createImmediateBatches(channel, channelUsers, req)
            channelBatches[channel] = batches
        }
    }
    
    // Queue batches with appropriate priority
    for channel, batches := range channelBatches {
        for _, batch := range batches {
            if err := m.queueBatch(ctx, channel, batch); err != nil {
                m.metrics.Counter("batch_queue_errors").Inc()
                return fmt.Errorf("failed to queue batch: %w", err)
            }
        }
    }
    
    return nil
}
```

---

## Failure Handling and Resilience (Production-Ready)

### Circuit Breaker with Proper Concurrency

```go
type CircuitBreaker struct {
    maxFailures     int32
    timeout         time.Duration
    resetTimeout    time.Duration
    
    // Atomic counters for thread safety
    state           int32 // 0=closed, 1=open, 2=half-open
    failureCount    int32
    successCount    int32
    lastFailureTime int64
    
    // Half-open state management
    halfOpenLock    sync.Mutex
    halfOpenAllowed int32
}

func (cb *CircuitBreaker) Execute(ctx context.Context, operation func() error) error {
    state := atomic.LoadInt32(&cb.state)
    
    switch state {
    case StateOpen:
        if time.Since(time.Unix(0, atomic.LoadInt64(&cb.lastFailureTime))) > cb.resetTimeout {
            cb.attemptReset()
        } else {
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
    }
}

func (cb *CircuitBreaker) recordResult(err error) {
    if err != nil {
        failures := atomic.AddInt32(&cb.failureCount, 1)
        atomic.StoreInt64(&cb.lastFailureTime, time.Now().UnixNano())
        
        if failures >= cb.maxFailures {
            atomic.StoreInt32(&cb.state, StateOpen)
        }
    } else {
        if atomic.LoadInt32(&cb.state) == StateHalfOpen {
            successes := atomic.AddInt32(&cb.successCount, 1)
            if successes >= 3 { // Require 3 successes to close
                atomic.StoreInt32(&cb.state, StateClosed)
                atomic.StoreInt32(&cb.failureCount, 0)
            }
        } else {
            atomic.StoreInt32(&cb.failureCount, 0)
        }
    }
}
```

### Comprehensive Retry Strategy

```go
type RetryConfig struct {
    MaxRetries      int
    InitialDelay    time.Duration
    MaxDelay        time.Duration
    Multiplier      float64
    Jitter          bool
    RetryableErrors []string
}

func (r *RetryConfig) ExecuteWithContext(ctx context.Context, operation func() error) error {
    var lastErr error
    delay := r.InitialDelay
    
    for attempt := 0; attempt <= r.MaxRetries; attempt++ {
        if attempt > 0 {
            actualDelay := r.calculateDelay(delay, attempt)
            select {
            case <-time.After(actualDelay):
            case <-ctx.Done():
                return fmt.Errorf("context cancelled after %d attempts: %w", attempt, ctx.Err())
            }
        }
        
        lastErr = operation()
        if lastErr == nil {
            return nil
        }
        
        // Check if error is retryable
        if !r.isRetryableError(lastErr) {
            return fmt.Errorf("non-retryable error on attempt %d: %w", attempt+1, lastErr)
        }
        
        delay = time.Duration(float64(delay) * r.Multiplier)
        if delay > r.MaxDelay {
            delay = r.MaxDelay
        }
    }
    
    return fmt.Errorf("operation failed after %d attempts: %w", r.MaxRetries+1, lastErr)
}

func (r *