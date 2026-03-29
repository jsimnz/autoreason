# Notification System Design for Social App (10M MAU) - Strategic Synthesis

## Executive Summary

Building notification infrastructure for 10M users requires honest assessment of constraints. With 4 backend engineers and 6 months, **a hybrid approach using third-party services with custom orchestration is the only viable path**. This synthesis presents a production-ready solution that balances cost, reliability, and development velocity.

**Bottom Line**: The hybrid approach delivers enterprise-grade notifications for $460K development cost and $7,450/month operational cost, versus $1.86M and 18 months for full in-house development.

---

## Strategic Architecture: Hybrid Approach

### High-Level System Design

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │  Notification   │    │   Message       │
│   (Kong/Istio)  │────│  Orchestrator   │────│   Queue         │
│   Rate Limiting │    │   (Go Service)  │    │   (Redis)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Prefs    │    │   Analytics     │    │   Channel       │
│   Database      │────│   Pipeline      │    │   Workers       │
│   (PostgreSQL)  │    │   (Kafka)       │    │   (Kubernetes)  │
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

**Push Notifications (OneSignal):**
- **Cost**: $2,000/month for 10M users
- **Rationale**: Proven 95%+ delivery rates, handles iOS/Android complexity
- **Integration**: RESTful API with webhook callbacks for delivery status

**Email (SendGrid):**
- **Cost**: $500/month for 5M emails
- **Features**: Template management, deliverability optimization, compliance
- **Integration**: SMTP relay with event webhooks

**SMS (Twilio):**
- **Cost**: $2,000/month (emergency notifications only)
- **Usage**: 2FA, critical alerts, opt-in marketing
- **Global**: Short codes in major markets

**In-App (WebSocket + Redis):**
- **Cost**: $800/month for real-time service
- **Implementation**: Custom WebSocket service with Redis pub/sub
- **Fallback**: Polling API for connection issues

---

## Database Architecture: Optimized for Scale

### User Preferences Schema

```sql
-- Partitioned by user_id for horizontal scaling
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    quiet_hours JSONB, -- {"start": "22:00", "end": "08:00", "timezone": "UTC"}
    category_preferences JSONB, -- {"likes": true, "comments": true, "follows": false}
    frequency_limits JSONB, -- {"email_daily_max": 3, "push_hourly_max": 5}
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
) PARTITION BY HASH (user_id);

-- Create 4 partitions for initial deployment
CREATE TABLE user_preferences_0 PARTITION OF user_notification_preferences
    FOR VALUES WITH (modulus 4, remainder 0);
-- Repeat for remainder 1-3
```

### Device Token Management

```sql
CREATE TABLE device_tokens (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    platform VARCHAR(10) CHECK (platform IN ('ios', 'android', 'web')),
    token_hash VARCHAR(64) UNIQUE, -- SHA-256 of actual token
    encrypted_token BYTEA, -- AES-256 encrypted
    is_active BOOLEAN DEFAULT true,
    last_used TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, platform, id)
) PARTITION BY HASH (user_id);

-- Index for token lookups
CREATE INDEX idx_device_tokens_hash ON device_tokens (token_hash) WHERE is_active = true;
```

### Message Tracking Schema

```sql
CREATE TABLE notification_logs (
    message_id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL,
    notification_type VARCHAR(50),
    channels TEXT[], -- ['push', 'email']
    priority VARCHAR(10) CHECK (priority IN ('high', 'normal', 'low')),
    status VARCHAR(20) DEFAULT 'queued',
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    opened_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Monthly partitions for performance
CREATE TABLE notification_logs_2024_01 PARTITION OF notification_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

---

## Message Processing Engine

### Priority and Batching Logic

```go
type NotificationRequest struct {
    MessageID    string            `json:"message_id"`
    UserIDs      []int64          `json:"user_ids"`
    Type         string           `json:"type"`
    Priority     Priority         `json:"priority"`
    Channels     []Channel        `json:"channels"`
    Content      NotificationContent `json:"content"`
    Scheduling   ScheduleConfig   `json:"scheduling,omitempty"`
    Targeting    TargetingConfig  `json:"targeting,omitempty"`
}

type Priority int
const (
    PriorityHigh   Priority = 1 // Security alerts, direct messages
    PriorityNormal Priority = 2 // Likes, comments, follows
    PriorityLow    Priority = 3 // Marketing, recommendations
)

// Message orchestrator with intelligent batching
type MessageOrchestrator struct {
    redisClient   *redis.Client
    dbPool        *sql.DB
    channelWorkers map[Channel]*ChannelWorker
    batchConfig   BatchConfig
}

type BatchConfig struct {
    MaxBatchSize     int           `json:"max_batch_size"`     // 1000 for push, 100 for email
    MaxWaitTime      time.Duration `json:"max_wait_time"`      // 30s for normal, 5s for high
    RateLimitPerSec  int           `json:"rate_limit_per_sec"` // API rate limits
}

func (m *MessageOrchestrator) ProcessNotification(req NotificationRequest) error {
    // 1. Validate and enrich request
    enrichedReq, err := m.enrichRequest(req)
    if err != nil {
        return fmt.Errorf("enrichment failed: %w", err)
    }
    
    // 2. Apply user preferences filtering
    filteredUsers, err := m.applyUserPreferences(enrichedReq)
    if err != nil {
        return fmt.Errorf("preference filtering failed: %w", err)
    }
    
    // 3. Segment by channel and priority
    channelBatches := m.createChannelBatches(filteredUsers, enrichedReq)
    
    // 4. Queue batches with appropriate delays
    for channel, batches := range channelBatches {
        for _, batch := range batches {
            queueKey := fmt.Sprintf("notifications:%s:%s", channel, req.Priority)
            if err := m.queueBatch(queueKey, batch); err != nil {
                log.Printf("Failed to queue batch: %v", err)
            }
        }
    }
    
    return nil
}
```

### Smart Batching Algorithm

```go
func (m *MessageOrchestrator) createChannelBatches(users []UserTarget, req NotificationRequest) map[Channel][]Batch {
    batches := make(map[Channel][]Batch)
    
    for _, channel := range req.Channels {
        config := m.batchConfig.GetChannelConfig(channel)
        channelUsers := m.filterUsersByChannel(users, channel)
        
        // Group by timezone for optimal delivery timing
        timezoneGroups := m.groupByTimezone(channelUsers)
        
        for timezone, tzUsers := range timezoneGroups {
            // Create batches within timezone group
            for i := 0; i < len(tzUsers); i += config.MaxBatchSize {
                end := i + config.MaxBatchSize
                if end > len(tzUsers) {
                    end = len(tzUsers)
                }
                
                batch := Batch{
                    ID:          generateBatchID(),
                    Channel:     channel,
                    Users:       tzUsers[i:end],
                    Content:     req.Content,
                    Priority:    req.Priority,
                    Timezone:    timezone,
                    CreatedAt:   time.Now(),
                }
                
                batches[channel] = append(batches[channel], batch)
            }
        }
    }
    
    return batches
}
```

---

## Failure Handling and Resilience

### Circuit Breaker Implementation

```go
type CircuitBreaker struct {
    maxFailures     int
    timeout         time.Duration
    resetTimeout    time.Duration
    state           CircuitState
    failureCount    int
    lastFailureTime time.Time
    mutex           sync.RWMutex
}

type CircuitState int
const (
    StateClosed CircuitState = iota
    StateOpen
    StateHalfOpen
)

func (cb *CircuitBreaker) Execute(operation func() error) error {
    cb.mutex.RLock()
    state := cb.state
    cb.mutex.RUnlock()
    
    if state == StateOpen {
        if time.Since(cb.lastFailureTime) > cb.resetTimeout {
            cb.setState(StateHalfOpen)
        } else {
            return ErrCircuitBreakerOpen
        }
    }
    
    err := operation()
    cb.recordResult(err)
    return err
}

func (cb *CircuitBreaker) recordResult(err error) {
    cb.mutex.Lock()
    defer cb.mutex.Unlock()
    
    if err != nil {
        cb.failureCount++
        cb.lastFailureTime = time.Now()
        
        if cb.failureCount >= cb.maxFailures {
            cb.state = StateOpen
        }
    } else {
        cb.failureCount = 0
        cb.state = StateClosed
    }
}
```

### Retry Logic with Exponential Backoff

```go
type RetryConfig struct {
    MaxRetries    int
    InitialDelay  time.Duration
    MaxDelay      time.Duration
    Multiplier    float64
    Jitter        bool
}

func (r *RetryConfig) Execute(ctx context.Context, operation func() error) error {
    var lastErr error
    delay := r.InitialDelay
    
    for attempt := 0; attempt <= r.MaxRetries; attempt++ {
        if attempt > 0 {
            select {
            case <-time.After(r.calculateDelay(delay, attempt)):
            case <-ctx.Done():
                return ctx.Err()
            }
        }
        
        lastErr = operation()
        if lastErr == nil {
            return nil
        }
        
        if !r.isRetryableError(lastErr) {
            return lastErr
        }
        
        delay = time.Duration(float64(delay) * r.Multiplier)
        if delay > r.MaxDelay {
            delay = r.MaxDelay
        }
    }
    
    return fmt.Errorf("operation failed after %d attempts: %w", r.MaxRetries, lastErr)
}
```

---

## Complete Cost Analysis

### Development Costs (6 Months)

**Team Composition:**
- 4 Senior Backend Engineers: $360,000
- DevOps setup and security review: $40,000
- Third-party service setup and integration: $15,000
- **Total Development: $415,000**

### Monthly Operational Costs

**Third-Party Services:**
- OneSignal (10M push users): $2,000/month
- SendGrid (5M emails): $500/month
- Twilio SMS (emergency only): $2,000/month
- WebSocket service: $800/month
- **Subtotal: $5,300/month**

**Infrastructure (AWS):**
- Application servers (3 x c5.large): $400/month
- RDS PostgreSQL (db.r5.large with read replica): $600/month
- Redis cluster (elasticache): $300/month
- Load balancer + CloudFront CDN: $200/month
- Monitoring (DataDog): $800/month
- Security and backup services: $350/month
- **Subtotal: $2,650/month**

**Total Monthly: $7,950/month**
**Annual Operational Cost: $95,400**

---

## 6-Month Implementation Timeline

### Phase 1: Foundation (Months 1-2)
**Team Focus: 4 Engineers**

**Week 1-2: Infrastructure Setup**
- AWS environment and CI/CD pipeline
- PostgreSQL database with partitioning
- Redis cluster for caching and queues
- Basic monitoring and logging

**Week 3-6: Core Services**
- User preference API with full CRUD operations
- Device token management service
- Third-party service integration layer (OneSignal, SendGrid)
- Message orchestrator with basic batching

**Week 7-8: Testing and Security**
- Integration testing suite
- Security review and token encryption
- Basic admin dashboard for manual sends

**Deliverables:**
- ✅ Send basic notifications via OneSignal and SendGrid
- ✅ User preference management API
- ✅ Device token lifecycle management
- ✅ Basic delivery tracking

### Phase 2: Production Hardening (Months 3-4)
**Team Focus: 2 Engineers on reliability, 2 on features**

**Week 9-12: Reliability**
- Circuit breakers and retry logic
- Comprehensive error handling
- Rate limiting and abuse prevention
- Delivery status webhook processing

**Week 13-16: Analytics and Monitoring**
- Real-time delivery tracking dashboard
- A/B testing framework
- Performance metrics and alerting
- Capacity planning tools

**Deliverables:**
- ✅ 99%+ delivery reliability
- ✅ Real-time analytics dashboard
- ✅ A/B testing capability
- ✅ Production monitoring and alerting

### Phase 3: Advanced Features (Months 5-6)
**Team Focus: 1 Engineer on optimization, 3 on features**

**Week 17-20: Smart Features**
- Timezone-aware scheduling
- Template management system
- Advanced user segmentation
- Frequency capping and quiet hours

**Week 21-24: Business Features**
- Campaign management interface
- Bulk import and export tools
- Advanced reporting and analytics
- Performance optimization

**Deliverables:**
- ✅ Complete campaign management system
- ✅ Advanced segmentation and targeting
- ✅ Comprehensive analytics and reporting
- ✅ Optimized for 10M user scale

---

## Success Metrics and Monitoring

### Technical KPIs

**Reliability Metrics:**
- Delivery rate: >99% for email, >95% for push
- System uptime: >99.5%
- API response time: <200ms (95th percentile)
- End-to-end notification delivery: <30 seconds

**Performance Metrics:**
- Queue processing rate: >10,000 notifications/second
- Database query time: <50ms (95th percentile)
- Memory usage: <80% of allocated resources
- Error rate: <0.1% of total requests

### Business KPIs

**Engagement Metrics:**
- Click-through rate: 3-8% (varies by type)