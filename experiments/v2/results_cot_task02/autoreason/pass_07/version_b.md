# Notification System Design for Social App (10M MAU) - Revised Proposal

## Executive Summary

After addressing critical architectural and operational concerns, this revised proposal presents a production-ready notification system that can genuinely handle 10M MAU with proper scalability, compliance, and disaster recovery. The **realistic cost is $1.2M development over 9 months with $28,500/month operational costs** - significantly higher than initially estimated but necessary for a system of this scale.

**Key Changes**: Proper message queue infrastructure, realistic third-party pricing, comprehensive disaster recovery, GDPR compliance, and production-grade monitoring.

---

## Corrected Architecture: Production-Ready Design

### High-Level System Architecture

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

---

## Database Architecture: Production-Grade Schema

### Corrected Partitioning Strategy

```sql
-- Range partitioning by created_at for operational efficiency
CREATE TABLE user_notification_preferences (
    user_id BIGINT NOT NULL,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    quiet_hours JSONB DEFAULT '{"enabled": false}',
    category_preferences JSONB DEFAULT '{}',
    frequency_limits JSONB DEFAULT '{"email_daily_max": 5, "push_hourly_max": 10}',
    gdpr_consent BOOLEAN DEFAULT false,
    gdpr_consent_date TIMESTAMP,
    data_residency VARCHAR(10) DEFAULT 'US', -- EU, US, APAC
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, created_at)
) PARTITION BY RANGE (created_at);

-- Monthly partitions with automated management
CREATE TABLE user_preferences_2024_01 PARTITION OF user_notification_preferences
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Index for fast user lookups
CREATE INDEX idx_user_prefs_user_id ON user_notification_preferences (user_id);
CREATE INDEX idx_user_prefs_gdpr ON user_notification_preferences (gdpr_consent, data_residency);
```

### Critical Missing Tables Added

```sql
-- Notification templates for A/B testing and localization
CREATE TABLE notification_templates (
    template_id UUID PRIMARY KEY,
    template_name VARCHAR(255) NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    language_code VARCHAR(5) DEFAULT 'en',
    title_template TEXT,
    body_template TEXT,
    action_url_template TEXT,
    variables JSONB, -- Dynamic content variables
    is_active BOOLEAN DEFAULT true,
    version INTEGER DEFAULT 1,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(template_name, version)
);

-- Campaign management
CREATE TABLE notification_campaigns (
    campaign_id UUID PRIMARY KEY,
    campaign_name VARCHAR(255) NOT NULL,
    template_id UUID REFERENCES notification_templates(template_id),
    target_criteria JSONB, -- User segmentation rules
    scheduling_config JSONB, -- Timezone-aware scheduling
    ab_test_config JSONB, -- A/B test parameters
    status VARCHAR(20) DEFAULT 'draft',
    created_by INTEGER REFERENCES users(id),
    scheduled_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User engagement history for ML optimization
CREATE TABLE user_engagement_history (
    user_id BIGINT NOT NULL,
    notification_type VARCHAR(50),
    channel VARCHAR(20),
    action VARCHAR(20), -- sent, delivered, opened, clicked, dismissed
    campaign_id UUID,
    template_id UUID,
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB -- Device info, location, etc.
) PARTITION BY RANGE (timestamp);

-- Monthly partitions with 90-day retention policy
CREATE TABLE engagement_2024_01 PARTITION OF user_engagement_history
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### Secure Device Token Management

```sql
-- Separate encryption keys per data residency region
CREATE TABLE device_tokens (
    token_id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL,
    platform VARCHAR(10) CHECK (platform IN ('ios', 'android', 'web')),
    token_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA-256 hash for deduplication
    encrypted_token BYTEA NOT NULL, -- AES-256-GCM encrypted
    key_version INTEGER NOT NULL, -- For key rotation
    data_residency VARCHAR(10) NOT NULL,
    app_version VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    last_used TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP, -- For token lifecycle management
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, platform, token_hash)
);

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

### GDPR Compliance Tables

```sql
-- Audit log for compliance
CREATE TABLE gdpr_audit_log (
    audit_id UUID PRIMARY KEY,
    user_id BIGINT,
    action VARCHAR(50), -- consent_given, data_exported, data_deleted
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

-- Data deletion requests
CREATE TABLE data_deletion_requests (
    request_id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL,
    requested_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    deletion_metadata JSONB -- What was deleted and when
);
```

---

## Message Processing: Apache Kafka Architecture

### Why Kafka Over Redis

**Durability**: Kafka persists messages to disk with configurable replication, ensuring zero message loss even during broker failures.

**Scalability**: Kafka can handle millions of messages per second across multiple partitions, far exceeding Redis memory limitations.

**Ordering Guarantees**: Per-partition ordering ensures notification sequences are maintained for each user.

### Kafka Topic Strategy

```go
// Topic configuration for 10M users
type KafkaTopics struct {
    HighPriorityNotifications string // 6 partitions, 1-second retention
    NormalNotifications       string // 12 partitions, 24-hour retention  
    LowPriorityNotifications  string // 6 partitions, 7-day retention
    DeliveryStatus           string // 3 partitions, 30-day retention
    UserEngagement           string // 12 partitions, 90-day retention
}

type NotificationMessage struct {
    MessageID     string                 `json:"message_id"`
    UserID        int64                  `json:"user_id"`
    CampaignID    string                 `json:"campaign_id,omitempty"`
    TemplateID    string                 `json:"template_id"`
    Priority      NotificationPriority   `json:"priority"`
    Channels      []DeliveryChannel      `json:"channels"`
    Content       NotificationContent    `json:"content"`
    Targeting     TargetingConfig        `json:"targeting"`
    Scheduling    SchedulingConfig       `json:"scheduling"`
    Compliance    ComplianceConfig       `json:"compliance"`
    Timestamp     time.Time              `json:"timestamp"`
}

type ComplianceConfig struct {
    RequiresGDPRConsent bool   `json:"requires_gdpr_consent"`
    DataResidency       string `json:"data_residency"`
    RetentionDays       int    `json:"retention_days"`
}
```

### Intelligent Message Processing

```go
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
        hasConsent, err := mp.checkGDPRConsent(msg.UserID, msg.Compliance.DataResidency)
        if err != nil || !hasConsent {
            return mp.logComplianceViolation(msg, "missing_gdpr_consent")
        }
    }
    
    // 2. Load user preferences with caching
    prefs, err := mp.getUserPreferences(ctx, msg.UserID)
    if err != nil {
        return fmt.Errorf("failed to load user preferences: %w", err)
    }
    
    // 3. Apply frequency capping
    if mp.exceedsFrequencyLimits(msg.UserID, msg.Priority, prefs.FrequencyLimits) {
        return mp.logSkippedMessage(msg, "frequency_limit_exceeded")
    }
    
    // 4. Timezone-aware scheduling
    if msg.Scheduling.RespectQuietHours {
        if mp.inQuietHours(msg.UserID, prefs.QuietHours) {
            return mp.scheduleForLater(msg, mp.calculateNextDeliveryTime(prefs.QuietHours))
        }
    }
    
    // 5. Channel filtering and batching
    enabledChannels := mp.filterEnabledChannels(msg.Channels, prefs)
    for _, channel := range enabledChannels {
        batch := mp.createChannelBatch(msg, channel)
        if err := mp.queueChannelBatch(ctx, batch); err != nil {
            log.Printf("Failed to queue batch for channel %s: %v", channel, err)
        }
    }
    
    return nil
}

func (mp *MessageProcessor) createChannelBatch(msg NotificationMessage, channel DeliveryChannel) ChannelBatch {
    return ChannelBatch{
        BatchID:     generateBatchID(),
        Channel:     channel,
        Messages:    []NotificationMessage{msg},
        Priority:    msg.Priority,
        CreatedAt:   time.Now(),
        Metadata: BatchMetadata{
            EstimatedSize:    mp.estimateBatchSize(msg, channel),
            ProcessingHints:  mp.getProcessingHints(channel),
            RetryConfig:     mp.getRetryConfig(channel),
        },
    }
}
```

---

## Disaster Recovery and Fallback Systems

### Multi-Provider Fallback Strategy

```go
type ChannelProvider interface {
    Send(ctx context.Context, batch ChannelBatch) (*DeliveryResult, error)
    GetHealthStatus() ProviderHealth
    GetRateLimits() RateLimitInfo
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

// Email providers with geographic distribution
type EmailProviders struct {
    Primary: *SendGridProvider,
    Fallback: []ChannelProvider{
        &AmazonSESProvider{Region: "us-east-1"},
        &AmazonSESProvider{Region: "eu-west-1"},
        &PostmarkProvider{},
    }
}

func (ns *NotificationSender) SendWithFallback(ctx context.Context, batch ChannelBatch) error {
    primary := ns.primaryProviders[batch.Channel]
    
    // Try primary provider first
    if ns.circuitBreakers[primary.Name()].IsHealthy() {
        result, err := primary.Send(ctx, batch)
        if err == nil {
            return ns.recordSuccess(batch, primary, result)
        }
        
        // Log failure and try fallbacks
        ns.recordFailure(batch, primary, err)
    }
    
    // Try fallback providers
    for _, fallback := range ns.fallbackProviders[batch.Channel] {
        if !ns.circuitBreakers[fallback.Name()].IsHealthy() {
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

### Sophisticated Circuit Breaker

```go
type CircuitBreaker struct {
    name            string
    maxFailures     int
    timeout         time.Duration
    resetTimeout    time.Duration
    state           CircuitState
    failures        []FailureRecord
    mutex           sync.RWMutex
    healthThreshold float64 // Success rate threshold
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

func (cb *CircuitBreaker) recordResult(err error) {
    cb.mutex.Lock()
    defer cb.mutex.Unlock()
    
    if err != nil {
        failure := FailureRecord{
            Timestamp:   time.Now(),
            ErrorType:   cb.classifyError(err),
            Severity:    cb.getSeverity(err),
            Recoverable: cb.isRecoverable