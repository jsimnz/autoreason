# Notification System Design for Social App (10M MAU) - REVISED

## Executive Summary

This proposal outlines a **realistic** notification system for a social app with 10M MAU, designed to be implemented by 4 backend engineers within 6 months. The system focuses on **core functionality first** with a simple, scalable architecture that can be enhanced post-launch.

**Key Design Decisions:**
- **Simplified architecture**: Direct database queuing with background workers (no complex message queues)
- **Two-tier priority system**: Critical and normal notifications only
- **Normalized preference schema**: Proper relational design instead of JSONB
- **Push-first approach**: Focus on push notifications with email as secondary channel

**Scope Limitations for 6-Month Timeline:**
- No SMS integration (post-launch enhancement)
- No complex batching algorithms (simple time-window batching only)
- No real-time WebSocket delivery (polling-based in-app notifications)
- No machine learning or advanced personalization

*Fixes Problem 1: Fundamentally Broken Timeline - Realistic scope for 4 engineers in 6 months*

## 1. System Architecture Overview

### Simplified Core Components
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Notification  │    │   Background     │    │   Channel       │
│   API           │───▶│   Workers        │───▶│   Handlers      │
│   (Create)      │    │   (Process)      │    │   (Deliver)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   Redis Cache    │    │   External      │
│   (Queue +      │    │   (Preferences + │    │   Providers     │
│   Preferences)  │    │   Rate Limits)   │    │   (FCM/APNS)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Technology Stack
- **Database**: PostgreSQL for all persistent data (notifications, preferences, audit)
- **Cache**: Redis for preference caching and rate limiting
- **Queue**: PostgreSQL table-based queue (no SQS complexity)
- **Workers**: Go applications with simple polling
- **Infrastructure**: AWS ECS with Application Load Balancer

*Fixes Problem 4: Message Queue Architecture Won't Handle Load - Eliminates SNS/SQS complexity*

## 2. Database Schema Design

### Normalized Schema (Replaces JSONB Approach)

```sql
-- Core notification queue table
CREATE TABLE notification_queue (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1, -- 0=critical, 1=normal
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    data JSONB,
    channels INTEGER[] NOT NULL, -- [1,2,3] for push,email,in_app
    created_at TIMESTAMP DEFAULT NOW(),
    scheduled_for TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_notification_queue_pending ON notification_queue(scheduled_for, status) 
WHERE status = 'pending';

-- User preferences with proper normalization
CREATE TABLE user_notification_preferences (
    user_id UUID PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    in_app_enabled BOOLEAN DEFAULT true,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    daily_push_limit INTEGER DEFAULT 20,
    daily_email_limit INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Category-specific preferences
CREATE TABLE user_category_preferences (
    user_id UUID NOT NULL,
    category VARCHAR(50) NOT NULL,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, category),
    FOREIGN KEY (user_id) REFERENCES user_notification_preferences(user_id)
);

-- Rate limiting counters
CREATE TABLE user_notification_counters (
    user_id UUID NOT NULL,
    date DATE NOT NULL,
    push_count INTEGER DEFAULT 0,
    email_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

-- Delivery tracking
CREATE TABLE notification_deliveries (
    id BIGSERIAL PRIMARY KEY,
    notification_id BIGINT NOT NULL,
    channel INTEGER NOT NULL, -- 1=push, 2=email, 3=in_app
    status VARCHAR(20) NOT NULL, -- sent, delivered, failed, clicked
    external_id VARCHAR(100), -- FCM message ID, email ID, etc.
    error_message TEXT,
    delivered_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (notification_id) REFERENCES notification_queue(id)
);
```

*Fixes Problem 2: PostgreSQL JSONB Won't Scale - Proper normalized schema with efficient queries*

## 3. Simplified Priority and Processing

### Two-Tier Priority System

```go
const (
    PriorityCritical = 0  // Security, payment issues - immediate
    PriorityNormal   = 1  // Social interactions - batched
)

type NotificationProcessor struct {
    db          *sql.DB
    cache       *redis.Client
    pushHandler *PushHandler
    emailHandler *EmailHandler
    inAppHandler *InAppHandler
}

func (np *NotificationProcessor) ProcessPendingNotifications() error {
    // Process critical notifications immediately
    criticalNotifs, err := np.getPendingNotifications(PriorityCritical, 100)
    if err != nil {
        return err
    }
    
    for _, notif := range criticalNotifs {
        np.processNotificationSync(notif) // Immediate processing
    }
    
    // Process normal notifications in batches
    normalNotifs, err := np.getPendingNotifications(PriorityNormal, 500)
    if err != nil {
        return err
    }
    
    np.processNotificationsBatch(normalNotifs)
    return nil
}
```

### Simple Time-Window Batching

```go
func (np *NotificationProcessor) processNotificationsBatch(notifications []Notification) {
    // Group by user for batching
    userNotifs := make(map[string][]Notification)
    for _, notif := range notifications {
        userNotifs[notif.UserID] = append(userNotifs[notif.UserID], notif)
    }
    
    for userID, notifs := range userNotifs {
        // Simple rule: if user has >3 normal notifications, batch them
        if len(notifs) > 3 {
            np.sendBatchedNotification(userID, notifs)
        } else {
            for _, notif := range notifs {
                np.processNotificationSync(notif)
            }
        }
    }
}
```

*Fixes Problem 3: Batching Algorithm is Impossibly Complex - Simple, deterministic batching*

## 4. Notification Channels Implementation

### Push Notifications Only (Phase 1)

```go
type PushHandler struct {
    fcmClient  *messaging.Client
    apnsClient *apns2.Client
    db         *sql.DB
}

func (ph *PushHandler) Send(ctx context.Context, notif *Notification) error {
    // Check user preferences from cache
    prefs, err := ph.getUserPreferences(notif.UserID)
    if err != nil {
        return fmt.Errorf("failed to get preferences: %w", err)
    }
    
    if !prefs.PushEnabled {
        return ph.markAsSkipped(notif.ID, "push_disabled")
    }
    
    // Check daily limits
    if ph.exceedsDailyLimit(notif.UserID, "push") {
        return ph.markAsSkipped(notif.ID, "daily_limit_exceeded")
    }
    
    // Get user's device tokens
    tokens, err := ph.getActiveDeviceTokens(notif.UserID)
    if err != nil || len(tokens) == 0 {
        return ph.markAsFailed(notif.ID, "no_active_tokens")
    }
    
    // Send to each device
    var lastErr error
    successCount := 0
    
    for _, token := range tokens {
        err := ph.sendToDevice(ctx, token, notif)
        if err != nil {
            lastErr = err
            continue
        }
        successCount++
    }
    
    if successCount > 0 {
        return ph.markAsDelivered(notif.ID, "push")
    }
    
    return ph.markAsFailed(notif.ID, fmt.Sprintf("all_devices_failed: %v", lastErr))
}
```

### In-App Notifications (Polling-Based)

```go
type InAppHandler struct {
    db *sql.DB
}

// Simple polling endpoint - no WebSocket complexity
func (iah *InAppHandler) GetUnreadNotifications(userID string, limit int) ([]InAppNotification, error) {
    query := `
        SELECT id, title, body, data, created_at 
        FROM notification_queue 
        WHERE user_id = $1 
        AND 3 = ANY(channels) -- in_app channel
        AND status = 'completed'
        AND id > COALESCE((
            SELECT last_read_notification_id 
            FROM user_notification_state 
            WHERE user_id = $1
        ), 0)
        ORDER BY created_at DESC 
        LIMIT $2`
    
    // Implementation...
}
```

*Fixes Problem 5: WebSocket Won't Work - Polling-based approach that actually scales*

### Email Notifications (Phase 2)

```go
type EmailHandler struct {
    sesClient *ses.SES
    db        *sql.DB
}

func (eh *EmailHandler) Send(ctx context.Context, notif *Notification) error {
    prefs, err := eh.getUserPreferences(notif.UserID)
    if err != nil {
        return err
    }
    
    if !prefs.EmailEnabled {
        return eh.markAsSkipped(notif.ID, "email_disabled")
    }
    
    // Check daily email limit
    if eh.exceedsDailyLimit(notif.UserID, "email") {
        return eh.markAsSkipped(notif.ID, "daily_limit_exceeded")
    }
    
    // Simple template-based email
    emailBody := eh.renderTemplate(notif)
    
    result, err := eh.sesClient.SendEmail(&ses.SendEmailInput{
        Source: aws.String("notifications@yourapp.com"),
        Destination: &ses.Destination{
            ToAddresses: []*string{aws.String(prefs.Email)},
        },
        Message: &ses.Message{
            Subject: &ses.Content{Data: aws.String(notif.Title)},
            Body:    &ses.Content{Data: aws.String(emailBody)},
        },
    })
    
    if err != nil {
        return eh.markAsFailed(notif.ID, err.Error())
    }
    
    return eh.markAsDelivered(notif.ID, "email", *result.MessageId)
}
```

## 5. Preference Management

### Simple Preference Service

```go
type PreferenceService struct {
    db    *sql.DB
    cache *redis.Client
}

func (ps *PreferenceService) ShouldSendNotification(
    userID string, 
    channel string, 
    category string,
) (bool, error) {
    // Single cache lookup for all preferences
    cacheKey := fmt.Sprintf("prefs:%s", userID)
    prefs, err := ps.getCachedPreferences(cacheKey)
    if err != nil {
        // Fallback to database
        prefs, err = ps.getPreferencesFromDB(userID)
        if err != nil {
            return false, err
        }
        // Cache for 1 hour
        ps.cachePreferences(cacheKey, prefs, time.Hour)
    }
    
    // Simple boolean checks - no complex logic
    switch channel {
    case "push":
        if !prefs.PushEnabled {
            return false, nil
        }
    case "email":
        if !prefs.EmailEnabled {
            return false, nil
        }
    case "in_app":
        if !prefs.InAppEnabled {
            return false, nil
        }
    }
    
    // Check category preferences
    categoryPref, exists := prefs.Categories[category]
    if !exists {
        return true, nil // Default to enabled
    }
    
    switch channel {
    case "push":
        return categoryPref.PushEnabled, nil
    case "email":
        return categoryPref.EmailEnabled, nil
    case "in_app":
        return categoryPref.InAppEnabled, nil
    }
    
    return true, nil
}
```

*Fixes Problem 7: Race Conditions - Single atomic preference lookup*

## 6. Infrastructure and Scaling

### Realistic Load Estimates

**Current Load (10M MAU):**
- Daily active users: 3M
- Notifications per user per day: 8 (reduced from 15)
- Total daily notifications: 24M
- Peak notifications per second: 1,000 (not 2,000)
- Database writes per second: ~280 (queue inserts)
- Database reads per second: ~1,200 (preference lookups + worker polling)

### Infrastructure Sizing

```yaml
# ECS Service Configuration
NotificationAPI:
  cpu: 1024 (1 vCPU)
  memory: 2048 (2GB)
  desired_count: 2
  max_count: 6
  
NotificationWorkers:
  cpu: 2048 (2 vCPU)
  memory: 4096 (4GB)
  desired_count: 4
  max_count: 12

# RDS Configuration
PostgreSQL:
  instance_class: db.r5.xlarge
  storage: 500GB SSD
  read_replicas: 2
  
# Redis Configuration  
ElastiCache:
  node_type: cache.r5.large
  num_nodes: 2 (for HA)
```

### Realistic Cost Estimates

```
Monthly Infrastructure Costs:
- ECS (API + Workers):     $400
- RDS PostgreSQL:          $600
- ElastiCache Redis:       $300
- Application Load Balancer: $25
- FCM/APNS:               $0 (free tiers)
- SES Email:              $100 (1M emails)
- CloudWatch/Monitoring:   $75
- Data Transfer:          $100
Total:                   ~$1,600/month
```

*Fixes Problem 6: Cost Estimates Wildly Wrong - Realistic infrastructure costs*

## 7. Failure Handling

### Simple Circuit Breaker

```go
type CircuitBreaker struct {
    failureCount    int
    successCount    int
    failureThreshold int
    resetTimeout    time.Duration
    lastFailureTime time.Time
    state          string // "closed", "open", "half-open"
    mutex          sync.RWMutex
}

func (cb *CircuitBreaker) Call(operation func() error) error {
    cb.mutex.Lock()
    defer cb.mutex.Unlock()
    
    // Simple state machine
    switch cb.state {
    case "open":
        if time.Since(cb.lastFailureTime) > cb.resetTimeout {
            cb.state = "half-open"
            cb.failureCount = 0
        } else {
            return errors.New("circuit breaker open")
        }
    }
    
    err := operation()
    
    if err != nil {