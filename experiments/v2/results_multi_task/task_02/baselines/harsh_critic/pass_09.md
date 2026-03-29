# REVISED PROPOSAL: PRODUCTION-READY NOTIFICATION SYSTEM
**10M MAU Social App - 4 Engineers, 6 Months**

## Executive Summary

This proposal delivers a **pragmatic notification system** that balances feature completeness with delivery timeline constraints. We prioritize **proven technologies** over architectural complexity and focus on **operational reliability** with realistic scale planning.

**Key Design Decisions:**
- Target 800K Daily Active Users (8% MAU conversion - industry standard)
- Handle 12M notifications/day normal, 60M during viral events (5x surge capacity)
- Single-region deployment with disaster recovery plan (not active-active)
- Simplified event logging instead of full event sourcing
- 99.9% uptime target (realistic for 6-month timeline)

## 1. Realistic Scale Planning & Constraints

### 1.1 Production Metrics (Conservative Estimates)

```yaml
Social App Reality (10M MAU, 6-month delivery):
  Daily Operations:
    - Daily Active Users: 800K (8% conversion)
    - Peak Concurrent Users: 160K (20% of DAU)
    - Normal Daily Volume: 12M notifications
    - Viral Surge Capacity: 60M notifications/day (5x normal)
    - Geographic: 50% US, 30% EU, 20% Other

  Channel Distribution:
    - Push: 70% (8.4M daily) - primary engagement
    - In-App: 20% (2.4M daily) - real-time features
    - Email: 8% (960K daily) - retention/digest
    - SMS: 2% (240K daily) - critical only

  Peak Load Scenarios:
    - Breaking news: 2M push in 5 minutes
    - Celebrity post: 8M notifications over 1 hour
    - System broadcast: 800K notifications in 15 minutes

Infrastructure Budget: $25K-35K monthly (realistic for startup)
```

### 1.2 Team & Timeline Constraints

```yaml
4 Backend Engineers, 6 Months:
  
  Month 1-2: Core Infrastructure
    - Basic notification API and database schema
    - Push notification integration (iOS/Android)
    - Simple email delivery via SES
    - User preference management
    
  Month 3-4: Scale & Reliability
    - Batch processing and queue management
    - Rate limiting and circuit breakers
    - Monitoring and alerting
    - Load testing and optimization
    
  Month 5-6: Production Hardening
    - Security audit and penetration testing
    - Compliance documentation (GDPR basics)
    - Disaster recovery procedures
    - Performance tuning and launch prep

  Deliberately Excluded (Future Phases):
    - Full event sourcing (too complex for timeline)
    - Multi-region active-active (operational overhead)
    - Advanced ML personalization
    - Real-time analytics dashboard
```

## 2. Simplified Architecture for 6-Month Delivery

### 2.1 Infrastructure: Single-Region with DR

```yaml
Primary Region (US-East-1):
  
  Compute:
    - EKS Cluster: 6x c5.xlarge nodes (2 AZs)
    - Application Load Balancer
    - CloudFront for static assets
  
  Database:
    - Aurora PostgreSQL: 1 writer + 2 readers (db.r5.large)
    - ElastiCache Redis: 3-node cluster
    - S3 for notification templates and assets
  
  Message Processing:
    - SQS: 4 queues (priority-based)
    - EventBridge for internal events
    - Lambda for lightweight processing
  
  External Services:
    - Amazon SES for email (10K/day free tier)
    - Amazon SNS for push notifications
    - Twilio for SMS (backup only)

Disaster Recovery (US-West-2):
    - Aurora cross-region replica
    - S3 cross-region replication
    - Infrastructure-as-code for rapid rebuild
    - RTO: 2 hours, RPO: 15 minutes

Monthly Cost: $18K-28K (scales with usage)
Capacity: 80M notifications/day burst
```

### 2.2 Database Schema: Event Logging Approach

```sql
-- Core notification table with audit trail
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    
    -- Content
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    image_url VARCHAR(1000),
    action_url VARCHAR(1000),
    
    -- Classification
    category VARCHAR(50) NOT NULL, -- social, content, system, marketing
    priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 5),
    
    -- Delivery configuration
    channels JSONB NOT NULL DEFAULT '[]', -- ["push", "email"]
    send_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Metadata
    custom_data JSONB DEFAULT '{}',
    template_id VARCHAR(100),
    campaign_id VARCHAR(100),
    
    -- State tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Partition by month for performance
CREATE TABLE notifications_2024_01 PARTITION OF notifications
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Delivery attempts and results
CREATE TABLE notification_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID NOT NULL REFERENCES notifications(id),
    channel VARCHAR(20) NOT NULL, -- push, email, sms, inapp
    
    -- Delivery details
    recipient_address VARCHAR(500) NOT NULL, -- device_token, email, phone
    provider VARCHAR(50) NOT NULL, -- fcm, apns, ses, sns
    
    -- Result tracking
    status VARCHAR(20) NOT NULL, -- sent, delivered, failed, bounced
    attempted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMP WITH TIME ZONE,
    
    -- Error handling
    error_code VARCHAR(100),
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    
    -- Provider response
    provider_message_id VARCHAR(200),
    provider_response JSONB DEFAULT '{}'
);

-- User preferences with consent tracking
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    
    -- Channel preferences
    push_enabled BOOLEAN NOT NULL DEFAULT true,
    email_enabled BOOLEAN NOT NULL DEFAULT true,
    sms_enabled BOOLEAN NOT NULL DEFAULT false,
    
    -- Category preferences
    social_notifications BOOLEAN NOT NULL DEFAULT true,
    content_notifications BOOLEAN NOT NULL DEFAULT true,
    system_notifications BOOLEAN NOT NULL DEFAULT true,
    marketing_notifications BOOLEAN NOT NULL DEFAULT false,
    
    -- Delivery controls
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Rate limiting
    max_push_per_hour INTEGER DEFAULT 20,
    max_email_per_day INTEGER DEFAULT 10,
    
    -- Consent tracking (GDPR)
    consent_date TIMESTAMP WITH TIME ZONE,
    consent_method VARCHAR(50), -- signup, settings, api
    consent_ip_address INET,
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Device registration for push notifications
CREATE TABLE user_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    device_token VARCHAR(500) NOT NULL,
    platform VARCHAR(20) NOT NULL, -- ios, android, web
    app_version VARCHAR(50),
    os_version VARCHAR(50),
    
    -- Status tracking
    active BOOLEAN NOT NULL DEFAULT true,
    last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    registered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    UNIQUE(user_id, device_token)
);

-- Indexes for performance
CREATE INDEX idx_notifications_user_status ON notifications(user_id, status);
CREATE INDEX idx_notifications_send_at ON notifications(send_at) 
    WHERE status IN ('pending', 'processing');
CREATE INDEX idx_deliveries_notification ON notification_deliveries(notification_id);
CREATE INDEX idx_deliveries_status_retry ON notification_deliveries(status, retry_count);
CREATE INDEX idx_devices_user_active ON user_devices(user_id) WHERE active = true;
```

### 2.3 Message Queue Architecture

```yaml
SQS Queue Design (Simple & Reliable):

high_priority_notifications:
  - Visibility timeout: 30 seconds
  - Message retention: 14 days
  - Dead letter queue after 3 attempts
  - Max receive count: 3
  - Usage: System alerts, security notifications

normal_priority_notifications:
  - Visibility timeout: 60 seconds  
  - Message retention: 14 days
  - Dead letter queue after 5 attempts
  - Max receive count: 5
  - Usage: Social interactions, content updates

low_priority_notifications:
  - Visibility timeout: 300 seconds
  - Message retention: 14 days  
  - Dead letter queue after 10 attempts
  - Max receive count: 10
  - Usage: Marketing, digest emails

notification_dlq:
  - Visibility timeout: 900 seconds
  - Message retention: 14 days
  - Manual processing required
  - Alerts on any messages

Queue Processing:
  - High: 4 Lambda consumers, 10 concurrent executions each
  - Normal: 6 Lambda consumers, 15 concurrent executions each  
  - Low: 2 Lambda consumers, 5 concurrent executions each
  - DLQ: Manual review process, daily monitoring
```

## 3. Multi-Channel Delivery Implementation

### 3.1 Push Notification Service

```go
package notification

import (
    "context"
    "fmt"
    "time"
    
    "github.com/aws/aws-sdk-go-v2/service/sns"
    "golang.org/x/time/rate"
)

type PushService struct {
    snsClient     *sns.Client
    rateLimiter   *rate.Limiter // 1000 requests/second
    retryPolicy   RetryPolicy
    metrics       MetricsCollector
}

type PushNotification struct {
    NotificationID string                 `json:"notification_id"`
    UserID         int64                 `json:"user_id"`
    DeviceToken    string                `json:"device_token"`
    Platform       string                `json:"platform"` // ios, android
    
    Title          string                `json:"title"`
    Body           string                `json:"body"`
    ImageURL       string                `json:"image_url,omitempty"`
    ActionURL      string                `json:"action_url,omitempty"`
    Badge          *int                  `json:"badge,omitempty"`
    
    CustomData     map[string]string     `json:"custom_data,omitempty"`
    Priority       int                   `json:"priority"` // 1-5
    TTL            int                   `json:"ttl"` // seconds
}

func (s *PushService) SendNotification(ctx context.Context, notification PushNotification) error {
    // Rate limiting
    if err := s.rateLimiter.Wait(ctx); err != nil {
        return fmt.Errorf("rate limit exceeded: %w", err)
    }
    
    // Build platform-specific payload
    payload, err := s.buildPayload(notification)
    if err != nil {
        return fmt.Errorf("failed to build payload: %w", err)
    }
    
    // Send via SNS with retry
    result, err := s.sendWithRetry(ctx, payload, notification.Platform)
    if err != nil {
        s.metrics.RecordDeliveryFailure(notification.Platform, err.Error())
        return err
    }
    
    // Log successful delivery
    s.metrics.RecordDeliverySuccess(notification.Platform)
    
    // Store delivery record
    return s.recordDelivery(ctx, notification.NotificationID, result.MessageID, "sent")
}

func (s *PushService) buildPayload(notification PushNotification) (map[string]string, error) {
    switch notification.Platform {
    case "ios":
        return s.buildAPNSPayload(notification)
    case "android":
        return s.buildFCMPayload(notification)
    default:
        return nil, fmt.Errorf("unsupported platform: %s", notification.Platform)
    }
}

func (s *PushService) buildAPNSPayload(notification PushNotification) (map[string]string, error) {
    aps := map[string]interface{}{
        "alert": map[string]string{
            "title": notification.Title,
            "body":  notification.Body,
        },
        "sound": "default",
    }
    
    if notification.Badge != nil {
        aps["badge"] = *notification.Badge
    }
    
    payload := map[string]interface{}{
        "aps": aps,
    }
    
    // Add custom data
    for key, value := range notification.CustomData {
        payload[key] = value
    }
    
    jsonPayload, err := json.Marshal(payload)
    if err != nil {
        return nil, err
    }
    
    return map[string]string{
        "APNS": string(jsonPayload),
    }, nil
}

func (s *PushService) buildFCMPayload(notification PushNotification) (map[string]string, error) {
    data := map[string]interface{}{
        "title":        notification.Title,
        "body":         notification.Body,
        "click_action": notification.ActionURL,
    }
    
    if notification.ImageURL != "" {
        data["image"] = notification.ImageURL
    }
    
    // Add custom data
    for key, value := range notification.CustomData {
        data[key] = value
    }
    
    payload := map[string]interface{}{
        "data":     data,
        "priority": s.mapPriorityToFCM(notification.Priority),
    }
    
    jsonPayload, err := json.Marshal(payload)
    if err != nil {
        return nil, err
    }
    
    return map[string]string{
        "GCM": string(jsonPayload),
    }, nil
}
```

### 3.2 Email Service with Template Management

```go
package notification

import (
    "bytes"
    "context"
    "fmt"
    "html/template"
    "time"
    
    "github.com/aws/aws-sdk-go-v2/service/ses"
)

type EmailService struct {
    sesClient      *ses.Client
    templateCache  map[string]*template.Template
    rateLimiter    *rate.Limiter // 200 emails/second (SES limit)
    fromAddress    string
    replyToAddress string
}

type EmailNotification struct {
    NotificationID string            `json:"notification_id"`
    UserID         int64            `json:"user_id"`
    ToAddress      string           `json:"to_address"`
    
    Subject        string           `json:"subject"`
    TemplateID     string           `json:"template_id"`
    TemplateData   map[string]interface{} `json:"template_data"`
    
    Category       string           `json:"category"`
    UnsubscribeURL string           `json:"unsubscribe_url"`
    
    Priority       int              `json:"priority"`
}

func (s *EmailService) SendNotification(ctx context.Context, notification EmailNotification) error {
    // Rate limiting
    if err := s.rateLimiter.Wait(ctx); err != nil {
        return fmt.Errorf("rate limit exceeded: %w", err)
    }
    
    // Render email content
    htmlContent, textContent, err := s.renderTemplate(notification)
    if err != nil {
        return fmt.Errorf("failed to render template: %w", err)
    }
    
    // Build SES email
    input := &ses.SendEmailInput{
        Source: &s.fromAddress,
        Destination: &ses.Destination{
            ToAddresses: []string