# Notification System Design for Social App (10M MAU) - REVISED v2

## Executive Summary

After addressing the critical issues identified, this **realistically scoped** design acknowledges the true complexity of building a production notification system. We propose a **phased delivery approach** that provides immediate business value while building toward full-scale capability.

**Revised Key Principles:**
- **Phase-based delivery** with measurable business outcomes at each stage
- **Honest complexity assessment** with appropriate team sizing
- **Complete cost accounting** including all hidden expenses
- **Simplified architecture** that actually works at stated scale
- **Production-ready from day one** with proper security and monitoring

---

## 1. Honest Scope Assessment & Phased Delivery

### Phase 1 (Months 1-3): Core Foundation - **6 Engineers**
**Deliverable:** Basic push notifications + email for 1M users
```
Team Composition:
- 2 Senior Backend Engineers (notification service, API)
- 2 Mid-level Engineers (database, infrastructure)
- 1 DevOps Engineer (deployment, monitoring)
- 1 Frontend Engineer (user preferences UI)

Business Value: 70% of notification use cases covered
Technical Debt: Minimal - solid foundation for scaling
```

### Phase 2 (Months 4-6): Scale & Reliability - **4 Engineers**
**Deliverable:** Full 10M MAU support + WebSocket + advanced features
```
Team Composition:
- 2 Senior Engineers (scaling, optimization)
- 1 Mid-level Engineer (WebSocket implementation)
- 1 DevOps Engineer (production hardening)

Business Value: 100% of requirements met
Technical Debt: Production-ready, documented, monitored
```

### Phase 3 (Months 7-9): Advanced Features - **2 Engineers**
**Deliverable:** Analytics, A/B testing, advanced personalization
```
Maintenance mode with feature additions
```

---

## 2. Simplified, Actually Deployable Architecture

### Core Components (No Over-Engineering)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ALB           │    │   API Service   │    │   Queue Service │
│   (AWS)         │────│   (Go/Gin)      │────│   (SQS + Lambda)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   RDS Postgres  │    │   External APIs │
                       │   (Multi-AZ)    │    │   (FCM/APNS/    │
                       │                 │    │   SendGrid)     │
                       └─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐
                       │   ElastiCache   │
                       │   (Redis)       │
                       └─────────────────┘
```

### Technology Stack Justification

**Why Go instead of Node.js:**
- Better memory management for high-concurrency workloads
- Simpler deployment (single binary)
- Excellent AWS SDK support
- Team can learn Go faster than mastering Node.js at scale

**Why AWS SQS instead of Redis Bull:**
- Fully managed (no cluster management overhead)
- Built-in dead letter queues and retry logic
- Auto-scaling with Lambda consumers
- $1.20 per million messages vs Redis cluster operational cost

**Why RDS instead of self-managed PostgreSQL:**
- Automated backups, patching, monitoring
- Multi-AZ failover without engineering effort
- Performance Insights for query optimization
- Scales to 10M users without sharding

---

## 3. Complete Cost Analysis (All Expenses Included)

### Infrastructure Costs (Monthly)

**Phase 1 (1M users):**
- ALB + EC2 instances (2 x t3.medium): **$180/month**
- RDS PostgreSQL (db.t3.large Multi-AZ): **$320/month**
- ElastiCache Redis (cache.t3.medium): **$85/month**
- SQS (5M messages/month): **$2/month**
- Lambda (notification processing): **$25/month**
- **Infrastructure Subtotal: $612/month**

**Phase 2 (10M users):**
- ALB + EC2 instances (4 x t3.large): **$480/month**
- RDS PostgreSQL (db.r5.xlarge Multi-AZ): **$890/month**
- ElastiCache Redis (cache.r5.large): **$180/month**
- SQS (50M messages/month): **$20/month**
- Lambda (notification processing): **$150/month**
- **Infrastructure Subtotal: $1,720/month**

### External Services (Monthly)
- **FCM/APNS:** $0 (free tier: 20M messages/month)
- **SendGrid:** $150 (5M emails/month)
- **Twilio SMS:** $75 (10K messages/month - security only)
- **DataDog:** $300 (infrastructure + APM)
- **AWS CloudWatch/X-Ray:** $100
- **External Services Subtotal: $625/month**

### Development & Operations (6 months)
- **6 Engineers (Phase 1, 3 months):** $270,000
- **4 Engineers (Phase 2, 3 months):** $180,000
- **DevOps tooling (CI/CD, staging, testing):** $15,000
- **Security audit & compliance:** $25,000
- **Team Costs Subtotal: $490,000**

### Hidden Costs Often Missed
- **SSL certificates, domain management:** $500
- **Backup storage (7 years retention):** $2,400
- **Disaster recovery testing:** $5,000
- **Legal review (privacy policies, terms):** $8,000
- **Performance testing tools:** $3,000
- **Hidden Costs Subtotal: $18,900**

**Total 6-Month Cost: $524,000**

---

## 4. Production-Ready Delivery Channels

### 4.1 Push Notifications (Robust, Not Over-Engineered)

```go
package notification

import (
    "context"
    "encoding/json"
    "fmt"
    "time"
    
    "github.com/aws/aws-sdk-go-v2/service/sqs"
    "go.uber.org/zap"
)

// Simple, testable structure
type PushService struct {
    fcmClient  FCMClient
    apnsClient APNSClient
    sqsClient  *sqs.Client
    logger     *zap.Logger
    metrics    MetricsClient
    
    // Simple retry configuration
    maxRetries int
    baseDelay  time.Duration
}

type NotificationRequest struct {
    UserID      string                 `json:"user_id"`
    DeviceToken string                 `json:"device_token"`
    Platform    string                 `json:"platform"` // "ios" or "android"
    Title       string                 `json:"title"`
    Body        string                 `json:"body"`
    Data        map[string]interface{} `json:"data,omitempty"`
    Priority    string                 `json:"priority"` // "high", "normal"
    TTL         int                    `json:"ttl_seconds"`
}

func (ps *PushService) SendNotification(ctx context.Context, req NotificationRequest) error {
    // Input validation
    if err := ps.validateRequest(req); err != nil {
        ps.metrics.IncrementCounter("notifications.validation_failed", map[string]string{
            "platform": req.Platform,
            "error":    err.Error(),
        })
        return fmt.Errorf("invalid request: %w", err)
    }
    
    // Route to appropriate platform
    switch req.Platform {
    case "ios":
        return ps.sendAPNS(ctx, req)
    case "android":
        return ps.sendFCM(ctx, req)
    default:
        return fmt.Errorf("unsupported platform: %s", req.Platform)
    }
}

func (ps *PushService) sendFCM(ctx context.Context, req NotificationRequest) error {
    startTime := time.Now()
    
    fcmPayload := FCMMessage{
        Token: req.DeviceToken,
        Notification: FCMNotification{
            Title: req.Title,
            Body:  req.Body,
        },
        Data: req.Data,
        Android: FCMAndroid{
            Priority: req.Priority,
            TTL:      fmt.Sprintf("%ds", req.TTL),
        },
    }
    
    // Single attempt with proper error handling
    response, err := ps.fcmClient.Send(ctx, fcmPayload)
    
    // Record metrics regardless of outcome
    duration := time.Since(startTime)
    ps.metrics.RecordHistogram("notifications.fcm.duration", duration.Milliseconds())
    
    if err != nil {
        ps.logger.Error("FCM send failed",
            zap.String("user_id", req.UserID),
            zap.String("error", err.Error()),
        )
        
        // Determine if we should retry
        if ps.shouldRetryFCMError(err) {
            return ps.scheduleRetry(ctx, req, err)
        }
        
        // Handle permanent failures
        if ps.isPermanentFCMError(err) {
            return ps.handlePermanentFailure(ctx, req, err)
        }
        
        ps.metrics.IncrementCounter("notifications.fcm.failed", map[string]string{
            "error_type": ps.classifyError(err),
        })
        return err
    }
    
    // Success
    ps.metrics.IncrementCounter("notifications.fcm.sent", map[string]string{
        "priority": req.Priority,
    })
    
    ps.logger.Info("FCM notification sent",
        zap.String("user_id", req.UserID),
        zap.String("message_id", response.MessageID),
        zap.Duration("duration", duration),
    )
    
    return nil
}

func (ps *PushService) shouldRetryFCMError(err error) bool {
    // Simple retry logic based on FCM documentation
    retryableErrors := []string{
        "INTERNAL",
        "SERVER_UNAVAILABLE", 
        "TIMEOUT",
    }
    
    errorCode := ps.extractFCMErrorCode(err)
    for _, retryable := range retryableErrors {
        if errorCode == retryable {
            return true
        }
    }
    return false
}

func (ps *PushService) scheduleRetry(ctx context.Context, req NotificationRequest, originalErr error) error {
    // Use SQS delay for retry (simpler than custom retry logic)
    retryPayload := RetryPayload{
        OriginalRequest: req,
        AttemptCount:    1, // Track retry attempts
        OriginalError:   originalErr.Error(),
        ScheduledAt:     time.Now(),
    }
    
    payloadBytes, err := json.Marshal(retryPayload)
    if err != nil {
        return fmt.Errorf("failed to marshal retry payload: %w", err)
    }
    
    // SQS delay queue (5 minute delay)
    _, err = ps.sqsClient.SendMessage(ctx, &sqs.SendMessageInput{
        QueueUrl:     &ps.retryQueueURL,
        MessageBody:  aws.String(string(payloadBytes)),
        DelaySeconds: 300, // 5 minutes
    })
    
    if err != nil {
        ps.logger.Error("Failed to schedule retry",
            zap.String("user_id", req.UserID),
            zap.Error(err),
        )
        return err
    }
    
    ps.metrics.IncrementCounter("notifications.retry_scheduled", map[string]string{
        "platform": req.Platform,
    })
    
    return nil
}

// Clean device token management
func (ps *PushService) handlePermanentFailure(ctx context.Context, req NotificationRequest, err error) error {
    errorCode := ps.extractFCMErrorCode(err)
    
    if errorCode == "INVALID_REGISTRATION_TOKEN" || errorCode == "REGISTRATION_TOKEN_NOT_REGISTERED" {
        // Clean up invalid token asynchronously
        go func() {
            if cleanupErr := ps.cleanupDeviceToken(context.Background(), req.DeviceToken); cleanupErr != nil {
                ps.logger.Error("Failed to cleanup device token",
                    zap.String("token", req.DeviceToken),
                    zap.Error(cleanupErr),
                )
            }
        }()
    }
    
    ps.metrics.IncrementCounter("notifications.permanent_failure", map[string]string{
        "platform":   req.Platform,
        "error_code": errorCode,
    })
    
    return fmt.Errorf("permanent failure: %s", errorCode)
}

func (ps *PushService) validateRequest(req NotificationRequest) error {
    if req.UserID == "" {
        return fmt.Errorf("user_id is required")
    }
    if req.DeviceToken == "" {
        return fmt.Errorf("device_token is required")
    }
    if req.Title == "" {
        return fmt.Errorf("title is required")
    }
    if len(req.Title) > 100 {
        return fmt.Errorf("title too long (max 100 characters)")
    }
    if len(req.Body) > 500 {
        return fmt.Errorf("body too long (max 500 characters)")
    }
    if req.Platform != "ios" && req.Platform != "android" {
        return fmt.Errorf("platform must be 'ios' or 'android'")
    }
    return nil
}
```

### 4.2 Email Notifications (Simple, Reliable)

```go
package notification

import (
    "context"
    "fmt"
    "time"
    
    "github.com/sendgrid/sendgrid-go"
    "github.com/sendgrid/sendgrid-go/helpers/mail"
    "go.uber.org/zap"
)

type EmailService struct {
    client  *sendgrid.Client
    logger  *zap.Logger
    metrics MetricsClient
    
    fromEmail string
    fromName  string
}

type EmailRequest struct {
    UserID    string            `json:"user_id"`
    ToEmail   string            `json:"to_email"`
    Subject   string            `json:"subject"`
    HTMLBody  string            `json:"html_body"`
    TextBody  string            `json:"text_body"`
    Category  string            `json:"category"` // For SendGrid analytics
    Variables map[string]string `json:"variables,omitempty"`
}

func (es *EmailService) SendEmail(ctx context.Context, req EmailRequest) error {
    if err := es.validateEmailRequest(req); err != nil {
        return fmt.Errorf("invalid email request: %w", err)
    }
    
    from := mail.NewEmail(es.fromName, es.fromEmail)
    to := mail.NewEmail("", req.ToEmail)
    
    message := mail.NewSingleEmail(from, req.Subject, to, req.TextBody, req.HTMLBody)
    
    // Add category for analytics
    if req.Category != "" {
        message.SetCategories([]string{req.Category})
    }
    
    // Add custom headers for tracking
    message.SetCustomArg("user_id", req.UserID)
    message.SetCustomArg("sent_at", fmt.Sprintf("%d", time.Now().Unix()))
    
    startTime := time.Now()
    response, err := es.client.Send(message)
    duration := time.Since(startTime)
    
    // Always record metrics
    es.metrics.RecordHistogram("notifications.email.duration", duration.Milliseconds())
    
    if err != nil {
        es.logger.Error("Email send failed",
            zap.String("user_id", req.