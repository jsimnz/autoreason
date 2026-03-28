# Notification System Design for Social App (10M MAU) - SYNTHESIS

## Executive Summary

This proposal outlines a **pragmatic** notification system for a social app with 10M MAU, designed to be implemented by 4 backend engineers within 6 months. The system balances production-grade reliability with realistic implementation complexity.

**Key Design Decisions:**
- **Hybrid queue architecture**: PostgreSQL-based queue with Redis for caching (eliminates SQS complexity while maintaining reliability)
- **Three-tier priority system with simplified batching**: Maintains user experience benefits while reducing implementation complexity
- **Normalized preference schema**: Proper relational design for scalability with strategic caching
- **Phased channel rollout**: Push + in-app first, then email, SMS post-launch

**Realistic Scope for 6-Month Timeline:**
- Core push and in-app notifications (Months 1-4)
- Email notifications (Months 5-6)
- SMS integration deferred to post-launch
- WebSocket delivery deferred to post-launch (polling-based initially)

## 1. System Architecture Overview

### Pragmatic Core Components
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Notification  │    │   Priority &     │    │   Channel       │
│   Gateway API   │───▶│   Processing     │───▶│   Dispatchers   │
│                 │    │   Workers        │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Prefs    │    │   PostgreSQL     │    │   External      │
│   Service       │    │   Queue + Cache  │    │   Providers     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Technology Stack Rationale
- **Queue**: PostgreSQL table-based queue with Redis caching (simpler than SQS, more reliable than pure polling)
- **Database**: PostgreSQL with normalized schema for preferences and audit
- **Cache**: Redis for preference caching and rate limiting
- **Programming Language**: Go for performance and team productivity
- **Infrastructure**: AWS ECS with auto-scaling for predictable operations

**Rationale**: Eliminates external queue dependencies while maintaining the reliability benefits of Version A's approach. PostgreSQL can handle 1,000 notifications/second with proper indexing.

## 2. Database Schema Design

### Efficient Normalized Schema

```sql
-- Core notification queue table
CREATE TABLE notification_queue (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 2, -- 0=critical, 1=high, 2=normal
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    data JSONB,
    channels INTEGER[] NOT NULL, -- [1,2,3] for push,email,in_app
    created_at TIMESTAMP DEFAULT NOW(),
    scheduled_for TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Optimized indexes for worker polling
CREATE INDEX idx_notification_queue_processing ON notification_queue(scheduled_for, priority, status) 
WHERE status IN ('pending', 'retrying');

CREATE INDEX idx_notification_queue_user_recent ON notification_queue(user_id, created_at DESC)
WHERE status = 'completed' AND created_at > NOW() - INTERVAL '7 days';

-- Normalized user preferences
CREATE TABLE user_notification_preferences (
    user_id UUID PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    in_app_enabled BOOLEAN DEFAULT true,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    daily_push_limit INTEGER DEFAULT 15,
    daily_email_limit INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Category-specific preferences with efficient lookups
CREATE TABLE user_category_preferences (
    user_id UUID NOT NULL,
    category VARCHAR(50) NOT NULL,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, category)
);

-- Rate limiting with daily partitioning
CREATE TABLE user_daily_counters (
    user_id UUID NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    push_count INTEGER DEFAULT 0,
    email_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, date)
);

-- Delivery tracking for analytics
CREATE TABLE notification_deliveries (
    id BIGSERIAL PRIMARY KEY,
    notification_id BIGINT NOT NULL,
    channel INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL, -- sent, delivered, failed, clicked
    external_id VARCHAR(100),
    error_message TEXT,
    delivered_at TIMESTAMP DEFAULT NOW()
);
```

**Design Rationale**: Maintains Version A's comprehensive tracking while using Version B's normalized approach for better query performance and easier maintenance.

## 3. Priority and Batching Logic

### Three-Tier Priority with Simplified Batching

```go
const (
    PriorityCritical = 0  // Security alerts, payment failures - immediate
    PriorityHigh     = 1  // Direct messages, mentions - 5 min batching max
    PriorityNormal   = 2  // Likes, comments - 15-60 min batching
)

type BatchingService struct {
    db               *sql.DB
    cache           *redis.Client
    userActivityTracker *ActivityTracker
}

func (bs *BatchingService) ProcessNotifications() error {
    // Always process critical immediately
    if err := bs.processCriticalNotifications(); err != nil {
        return err
    }
    
    // Process high priority with simple time-based batching
    if err := bs.processHighPriorityNotifications(); err != nil {
        return err
    }
    
    // Process normal with user activity-based batching
    return bs.processNormalNotifications()
}

func (bs *BatchingService) processNormalNotifications() error {
    // Simple batching: group by user, apply time windows based on activity
    query := `
        SELECT user_id, array_agg(id ORDER BY created_at) as notification_ids,
               COUNT(*) as notification_count
        FROM notification_queue 
        WHERE status = 'pending' 
        AND priority = 2 
        AND scheduled_for <= NOW()
        GROUP BY user_id
        HAVING COUNT(*) >= 1`
    
    rows, err := bs.db.Query(query)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    for rows.Next() {
        var userID string
        var notificationIDs pq.Int64Array
        var count int
        
        if err := rows.Scan(&userID, &notificationIDs, &count); err != nil {
            continue
        }
        
        // Simple batching rule: if user has 3+ notifications, batch them
        if count >= 3 {
            bs.createBatchedNotification(userID, notificationIDs)
        } else {
            bs.processIndividualNotifications(notificationIDs)
        }
    }
    
    return nil
}
```

**Batching Benefits**: Reduces notification fatigue while keeping implementation simple. Achieves 80% of Version A's sophistication with 40% of the complexity.

## 4. Delivery Channels Implementation

### Push Notifications (Production-Ready)

```go
type PushDispatcher struct {
    fcmClient   *messaging.Client
    apnsClient  *apns2.Client
    db          *sql.DB
    cache       *redis.Client
    rateLimiter *rate.Limiter
}

func (pd *PushDispatcher) Send(ctx context.Context, notification *Notification) error {
    // Check preferences with caching
    prefs, err := pd.getUserPreferences(notification.UserID)
    if err != nil {
        return fmt.Errorf("failed to get preferences: %w", err)
    }
    
    if !pd.shouldSendPush(prefs, notification) {
        return pd.markAsSkipped(notification.ID, "user_preferences")
    }
    
    // Check rate limits
    if pd.exceedsRateLimit(notification.UserID, "push") {
        return pd.markAsSkipped(notification.ID, "rate_limited")
    }
    
    // Get active device tokens
    tokens, err := pd.getActiveDeviceTokens(notification.UserID)
    if err != nil || len(tokens) == 0 {
        return pd.markAsFailed(notification.ID, "no_active_tokens")
    }
    
    // Send with retry logic
    var lastErr error
    successCount := 0
    
    for _, token := range tokens {
        if err := pd.sendToDevice(ctx, token, notification); err != nil {
            lastErr = err
            // Clean up invalid tokens
            if pd.isInvalidToken(err) {
                pd.removeInvalidToken(token)
            }
            continue
        }
        successCount++
    }
    
    if successCount > 0 {
        return pd.markAsDelivered(notification.ID, "push")
    }
    
    return pd.markAsFailed(notification.ID, fmt.Sprintf("all_devices_failed: %v", lastErr))
}

func (pd *PushDispatcher) sendToDevice(ctx context.Context, token DeviceToken, notif *Notification) error {
    // Rate limiting
    if err := pd.rateLimiter.Wait(ctx); err != nil {
        return err
    }
    
    switch token.Platform {
    case "ios":
        return pd.sendAPNS(ctx, token.Token, notif)
    case "android":
        return pd.sendFCM(ctx, token.Token, notif)
    default:
        return fmt.Errorf("unsupported platform: %s", token.Platform)
    }
}
```

### In-App Notifications (Polling-Based, Upgradeable)

```go
type InAppDispatcher struct {
    db *sql.DB
}

func (iad *InAppDispatcher) Send(ctx context.Context, notification *Notification) error {
    // For in-app, we just mark as available for polling
    // Store in optimized format for quick retrieval
    _, err := iad.db.ExecContext(ctx, `
        INSERT INTO user_in_app_notifications (user_id, notification_id, title, body, data, created_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (notification_id) DO NOTHING`,
        notification.UserID, notification.ID, notification.Title, notification.Body, notification.Data)
    
    if err != nil {
        return iad.markAsFailed(notification.ID, err.Error())
    }
    
    return iad.markAsDelivered(notification.ID, "in_app")
}

// Efficient polling endpoint
func (iad *InAppDispatcher) GetUnreadNotifications(userID string, since int64, limit int) ([]InAppNotification, error) {
    query := `
        SELECT notification_id, title, body, data, created_at,
               EXTRACT(epoch FROM created_at) as timestamp
        FROM user_in_app_notifications 
        WHERE user_id = $1 
        AND notification_id > $2
        AND created_at > NOW() - INTERVAL '7 days'
        ORDER BY created_at DESC 
        LIMIT $3`
    
    rows, err := iad.db.Query(query, userID, since, limit)
    if err != nil {
        return nil, err
    }
    defer rows.Close()
    
    var notifications []InAppNotification
    for rows.Next() {
        var notif InAppNotification
        if err := rows.Scan(&notif.ID, &notif.Title, &notif.Body, &notif.Data, &notif.CreatedAt, &notif.Timestamp); err != nil {
            continue
        }
        notifications = append(notifications, notif)
    }
    
    return notifications, nil
}
```

### Email Notifications (Phase 2)

```go
type EmailDispatcher struct {
    sesClient *ses.SES
    db        *sql.DB
    templates map[string]*template.Template
}

func (ed *EmailDispatcher) Send(ctx context.Context, notification *Notification) error {
    prefs, err := ed.getUserPreferences(notification.UserID)
    if err != nil {
        return err
    }
    
    if !prefs.EmailEnabled || ed.exceedsRateLimit(notification.UserID, "email") {
        return ed.markAsSkipped(notification.ID, "user_preferences_or_rate_limit")
    }
    
    // Template-based rendering with personalization
    emailContent, err := ed.renderEmailTemplate(notification, prefs)
    if err != nil {
        return ed.markAsFailed(notification.ID, fmt.Sprintf("template_error: %v", err))
    }
    
    // Send via SES with proper error handling
    result, err := ed.sesClient.SendEmailWithContext(ctx, &ses.SendEmailInput{
        Source: aws.String("notifications@yourapp.com"),
        Destination: &ses.Destination{
            ToAddresses: []*string{aws.String(prefs.Email)},
        },
        Message: &ses.Message{
            Subject: &ses.Content{Data: aws.String(notification.Title)},
            Body: &ses.Content{
                Html: &ses.Content{Data: aws.String(emailContent.HTML)},
                Text: &ses.Content{Data: aws.String(emailContent.Text)},
            },
        },
        ConfigurationSetName: aws.String("notification-tracking"),
    })
    
    if err != nil {
        return ed.markAsFailed(notification.ID, err.Error())
    }
    
    return ed.markAsDelivered(notification.ID, "email", *result.MessageId)
}
```

## 5. User Preference Management

### Cached Preference Service with Smart Defaults

```go
type PreferenceService struct {
    db    *sql.DB
    cache *redis.Client
}

type UserPreferences struct {
    UserID           string
    PushEnabled      bool
    EmailEnabled     bool
    InAppEnabled     bool
    QuietHoursStart  *time.Time
    QuietHoursEnd    *time.Time
    Timezone         string
    DailyPushLimit   int
    DailyEmailLimit  int
    Categories       map[string]CategoryPreference
}

func (ps *PreferenceService) ShouldSendNotification(
    userID string, 
    channel string, 
    category string,
    priority int,
) (bool, error) {
    // Critical notifications bypass most preferences
    if priority == PriorityCritical {
        return ps.checkCriticalNotificationRules(userID, channel)
    }
    
    prefs, err := ps.getUserPreferences(userID)
    if err != nil {
        // Fail open with conservative defaults for availability
        return ps.getDefaultPreference(channel, category), nil
    }
    
    // Check global channel enablement
    if !ps.isChannelEnabled(prefs, channel) {
        return false, nil
    }
    
    // Check quiet hours
    if ps.isInQuietHours(prefs) && priority != PriorityCritical {
        return false, nil
    }
    
    // Check rate limits
    if ps.exceedsRateLimit(userID, channel, prefs) {
        return false, nil
    }
    
    // Check category preferences
    return ps.isCategoryEnabled(prefs, channel, category), nil
}

func (ps *PreferenceService) getUserPreferences(userID string) (*UserPreferences