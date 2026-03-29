# Notification System Design for Social App (10M MAU) - Strategic Architecture

## Executive Summary

Building notification infrastructure for 10M users with 4 backend engineers and 6 months requires a **production-ready hybrid approach**. This synthesis combines enterprise-grade reliability with pragmatic resource constraints, delivering a system capable of handling 10M MAU for **$460K development cost and $8,200/month operational cost**.

**Key Decision**: Hybrid architecture using third-party services (OneSignal, SendGrid) with custom orchestration layer provides enterprise reliability at startup velocity.

---

## Strategic Architecture

### High-Level System Design

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │  Notification   │    │   Apache Kafka  │
│   (Kong + WAF)  │────│  Orchestrator   │────│   Message Bus   │
│   Rate Limiting │    │   (Go Service)  │    │   (3 brokers)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Prefs    │    │   Compliance    │    │   Channel       │
│   Database      │────│   Audit Log     │    │   Workers       │
│   (PostgreSQL)  │    │   (PostgreSQL)  │    │   (Kubernetes)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                              ┌─────────────────────────────────┐
                              │        Third-Party Services     │
                              │  Primary: OneSignal Enterprise  │
                              │  Fallback: FCM Direct + APNS    │
                              │  Email: SendGrid + Amazon SES   │
                              │  SMS: Twilio + MessageBird      │
                              └─────────────────────────────────┘
```

**Architecture Rationale:**
- **Kafka** for message durability and ordering guarantees at scale
- **Hybrid approach** balances development velocity with production reliability
- **Multi-provider fallback** ensures 99.9% uptime despite third-party failures

---

## Database Architecture: Production-Grade Schema

### User Preferences with GDPR Compliance

```sql
-- Partitioned for horizontal scaling
CREATE TABLE user_notification_preferences (
    user_id BIGINT NOT NULL,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    quiet_hours JSONB DEFAULT '{"enabled": false, "start": "22:00", "end": "08:00", "timezone": "UTC"}',
    category_preferences JSONB DEFAULT '{"likes": true, "comments": true, "follows": false}',
    frequency_limits JSONB DEFAULT '{"email_daily_max": 5, "push_hourly_max": 10}',
    gdpr_consent BOOLEAN DEFAULT false,
    gdpr_consent_date TIMESTAMP,
    data_residency VARCHAR(10) DEFAULT 'US', -- EU, US, APAC
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id)
) PARTITION BY HASH (user_id);

-- Create 4 partitions for initial deployment
CREATE TABLE user_preferences_0 PARTITION OF user_notification_preferences
    FOR VALUES WITH (modulus 4, remainder 0);
-- Repeat for remainder 1-3

-- Indexes for fast lookups
CREATE INDEX idx_user_prefs_gdpr ON user_notification_preferences (gdpr_consent, data_residency);
```

### Secure Device Token Management

```sql
CREATE TABLE device_tokens (
    token_id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL,
    platform VARCHAR(10) CHECK (platform IN ('ios', 'android', 'web')),
    token_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA-256 hash for deduplication
    encrypted_token BYTEA NOT NULL, -- AES-256-GCM encrypted
    key_version INTEGER NOT NULL, -- For key rotation
    data_residency VARCHAR(10) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_used TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, platform, token_hash)
) PARTITION BY HASH (user_id);

-- Automated key rotation tracking
CREATE TABLE encryption_keys (
    key_version INTEGER PRIMARY KEY,
    data_residency VARCHAR(10) NOT NULL,
    encrypted_key BYTEA NOT NULL, -- Encrypted with master key from HSM
    created_at TIMESTAMP DEFAULT NOW(),
    retired_at TIMESTAMP,
    UNIQUE(key_version, data_residency)
);
```

### Message Tracking and Analytics

```sql
-- Partitioned by time for efficient queries and cleanup
CREATE TABLE notification_logs (
    message_id UUID NOT NULL,
    user_id BIGINT NOT NULL,
    campaign_id UUID,
    notification_type VARCHAR(50),
    channels TEXT[], -- ['push', 'email']
    priority VARCHAR(10) CHECK (priority IN ('high', 'normal', 'low')),
    status VARCHAR(20) DEFAULT 'queued',
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    error_message TEXT,
    provider_response JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (message_id, created_at)
) PARTITION BY RANGE (created_at);

-- Monthly partitions with automated cleanup
CREATE TABLE notification_logs_2024_01 PARTITION OF notification_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- User engagement history for ML optimization
CREATE TABLE user_engagement_history (
    user_id BIGINT NOT NULL,
    notification_type VARCHAR(50),
    channel VARCHAR(20),
    action VARCHAR(20), -- sent, delivered, opened, clicked, dismissed
    campaign_id UUID,
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB -- Device info, location, etc.
) PARTITION BY RANGE (timestamp);
```

---

## Message Processing: Kafka-Powered Architecture

### Why Kafka Over Redis

**Durability**: Kafka persists messages to disk with configurable replication, ensuring zero message loss during broker failures.

**Scalability**: Handles millions of messages per second across partitions, far exceeding Redis memory limitations.

**Ordering**: Per-partition ordering ensures notification sequences are maintained for each user.

### Intelligent Message Processing

```go
type NotificationMessage struct {
    MessageID     string                 `json:"message_id"`
    UserIDs       []int64               `json:"user_ids"`
    CampaignID    string                `json:"campaign_id,omitempty"`
    Type          string                `json:"type"`
    Priority      NotificationPriority   `json:"priority"`
    Channels      []DeliveryChannel      `json:"channels"`
    Content       NotificationContent    `json:"content"`
    Targeting     TargetingConfig        `json:"targeting"`
    Scheduling    SchedulingConfig       `json:"scheduling"`
    Compliance    ComplianceConfig       `json:"compliance"`
    Timestamp     time.Time              `json:"timestamp"`
}

type NotificationPriority int
const (
    PriorityHigh   NotificationPriority = 1 // Security alerts, direct messages
    PriorityNormal NotificationPriority = 2 // Likes, comments, follows  
    PriorityLow    NotificationPriority = 3 // Marketing, recommendations
)

type MessageProcessor struct {
    kafkaProducer    *kafka.Producer
    kafkaConsumer    *kafka.Consumer
    dbPool          *sql.DB
    redisClient     *redis.Client
    circuitBreakers map[string]*CircuitBreaker
    rateLimiters    map[string]*TokenBucket
}

func (mp *MessageProcessor) ProcessNotification(ctx context.Context, msg NotificationMessage) error {
    // 1. GDPR compliance check
    if msg.Compliance.RequiresGDPRConsent {
        hasConsent, err := mp.checkGDPRConsent(msg.UserIDs, msg.Compliance.DataResidency)
        if err != nil || !hasConsent {
            return mp.logComplianceViolation(msg, "missing_gdpr_consent")
        }
    }
    
    // 2. Load user preferences with caching
    userPrefs, err := mp.batchLoadUserPreferences(ctx, msg.UserIDs)
    if err != nil {
        return fmt.Errorf("failed to load user preferences: %w", err)
    }
    
    // 3. Apply frequency capping and filtering
    filteredUsers := mp.applyFiltersAndLimits(msg, userPrefs)
    if len(filteredUsers) == 0 {
        return mp.logSkippedMessage(msg, "all_users_filtered")
    }
    
    // 4. Create channel-specific batches with timezone awareness
    channelBatches := mp.createIntelligentBatches(filteredUsers, msg)
    
    // 5. Queue batches with priority-based routing
    for channel, batches := range channelBatches {
        topicName := mp.getTopicForPriority(msg.Priority)
        for _, batch := range batches {
            if err := mp.queueChannelBatch(ctx, topicName, batch); err != nil {
                log.Printf("Failed to queue batch for channel %s: %v", channel, err)
            }
        }
    }
    
    return nil
}

func (mp *MessageProcessor) createIntelligentBatches(users []UserTarget, msg NotificationMessage) map[DeliveryChannel][]ChannelBatch {
    batches := make(map[DeliveryChannel][]ChannelBatch)
    
    for _, channel := range msg.Channels {
        config := mp.getBatchConfig(channel)
        channelUsers := mp.filterUsersByChannel(users, channel)
        
        // Group by timezone for optimal delivery timing
        timezoneGroups := mp.groupByTimezone(channelUsers)
        
        for timezone, tzUsers := range timezoneGroups {
            // Create optimally-sized batches
            for i := 0; i < len(tzUsers); i += config.MaxBatchSize {
                end := i + config.MaxBatchSize
                if end > len(tzUsers) {
                    end = len(tzUsers)
                }
                
                batch := ChannelBatch{
                    BatchID:     generateBatchID(),
                    Channel:     channel,
                    Users:       tzUsers[i:end],
                    Content:     msg.Content,
                    Priority:    msg.Priority,
                    Timezone:    timezone,
                    CreatedAt:   time.Now(),
                    Metadata: BatchMetadata{
                        EstimatedSize:   mp.estimateBatchSize(msg, channel),
                        ProcessingHints: mp.getProcessingHints(channel),
                        RetryConfig:    mp.getRetryConfig(channel),
                    },
                }
                
                batches[channel] = append(batches[channel], batch)
            }
        }
    }
    
    return batches
}
```

---

## Multi-Provider Fallback System

### Channel Provider Interface

```go
type ChannelProvider interface {
    Send(ctx context.Context, batch ChannelBatch) (*DeliveryResult, error)
    GetHealthStatus() ProviderHealth
    GetRateLimits() RateLimitInfo
    GetName() string
}

type NotificationSender struct {
    primaryProviders   map[DeliveryChannel]ChannelProvider
    fallbackProviders  map[DeliveryChannel][]ChannelProvider
    circuitBreakers    map[string]*CircuitBreaker
    healthChecker      *ProviderHealthChecker
}

// Push notification providers with intelligent fallback
type PushProviders struct {
    Primary:  *OneSignalProvider  // Enterprise tier with SLA
    Fallback: []ChannelProvider{
        &FCMDirectProvider{},     // Direct FCM integration
        &APNSDirectProvider{},    // Direct APNS integration
    }
}

func (ns *NotificationSender) SendWithFallback(ctx context.Context, batch ChannelBatch) error {
    primary := ns.primaryProviders[batch.Channel]
    
    // Try primary provider first
    if ns.circuitBreakers[primary.GetName()].IsHealthy() {
        result, err := primary.Send(ctx, batch)
        if err == nil {
            return ns.recordSuccess(batch, primary, result)
        }
        ns.recordFailure(batch, primary, err)
    }
    
    // Try fallback providers
    for _, fallback := range ns.fallbackProviders[batch.Channel] {
        if !ns.circuitBreakers[fallback.GetName()].IsHealthy() {
            continue
        }
        
        result, err := fallback.Send(ctx, batch)
        if err == nil {
            return ns.recordFallbackSuccess(batch, fallback, result)
        }
        ns.recordFailure(batch, fallback, err)
    }
    
    return fmt.Errorf("all providers failed for batch %s", batch.BatchID)
}
```

### Advanced Circuit Breaker

```go
type CircuitBreaker struct {
    name            string
    maxFailures     int
    timeout         time.Duration
    resetTimeout    time.Duration
    state           CircuitState
    failures        []FailureRecord
    mutex           sync.RWMutex
    healthThreshold float64 // Success rate threshold (e.g., 0.95)
}

type FailureRecord struct {
    Timestamp   time.Time
    ErrorType   ErrorType
    Severity    ErrorSeverity
    Recoverable bool
}

type ErrorType int
const (
    ErrorTypeRateLimit   ErrorType = iota // 429 errors - recoverable
    ErrorTypeTimeout                      // Network timeouts - recoverable  
    ErrorTypeAuth                         // 401/403 - requires manual intervention
    ErrorTypeServerError                  // 5xx errors - potentially recoverable
    ErrorTypeClientError                  // 4xx errors - not recoverable
)

func (cb *CircuitBreaker) Execute(operation func() error) error {
    if cb.shouldOpenCircuit() {
        return ErrCircuitBreakerOpen
    }
    
    err := operation()
    cb.recordResult(err)
    
    return err
}

func (cb *CircuitBreaker) shouldOpenCircuit() bool {
    cb.mutex.RLock()
    defer cb.mutex.RUnlock()
    
    if cb.state == CircuitStateOpen {
        if time.Since(cb.getLastFailureTime()) > cb.resetTimeout {
            cb.state = CircuitStateHalfOpen
            return false
        }
        return true
    }
    
    // Calculate recent success rate
    recentFailures := cb.getRecentFailures(time.Minute * 5)
    if len(recentFailures) >= cb.maxFailures {
        successRate := cb.calculateSuccessRate(time.Minute * 5)
        return successRate < cb.healthThreshold
    }
    
    return false
}
```

---

## Cost Analysis and Resource Planning

### Development Costs (6 Months)

**Team Composition:**
- 4 Senior Backend Engineers ($90K each): $360,000
- DevOps setup and security review: $40,000
- Third-party service integration: $15,000
- Testing and compliance: $25,000
- **Total Development: $440,000**

### Monthly Operational Costs

**Third-Party Services:**
- OneSignal Enterprise (10M push users): $2,000/month
- SendGrid Pro (5M emails): $500/month
- Twilio SMS (emergency notifications): $2,000/month
- **Subtotal: $4,500/month**

**Infrastructure (AWS):**
- Kafka cluster (3 x m5.large): $450/month
- Application servers (4 x c