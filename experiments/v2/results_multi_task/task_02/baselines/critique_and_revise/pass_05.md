## Critical Review of Original Proposal

### Major Problems Identified:

1. **Inconsistent Cost Analysis**: Claims PostgreSQL is "cost effective" at $800/month vs DynamoDB at $15K+, but then shows total infrastructure at only $2,500/month - the math doesn't add up for 10M MAU scale.

2. **Unrealistic Database Scaling Claims**: PostgreSQL handling 10M users with "proper indexing" ignores write throughput reality. At 174 notifications/second average (15M/day), a single RDS instance will bottleneck quickly.

3. **Incomplete Implementation**: The FastAPI code cuts off mid-function and lacks the actual delivery workers, queue processing, and failure handling - the core of the system.

4. **Missing Viral Traffic Handling**: Claims to handle 50x spikes (8,700 notifications/second) but provides no autoscaling, queue depth monitoring, or circuit breaker patterns.

5. **No Delivery Worker Architecture**: Shows SQS queues but no workers to process them. How do notifications actually get sent?

6. **Oversimplified Preference System**: Boolean flags can't handle complex social app needs like "notify me about comments on my posts but not likes from strangers."

7. **No Monitoring or Alerting Strategy**: CloudWatch mentioned but no specific metrics, thresholds, or runbook procedures defined.

8. **Partition Strategy Incomplete**: Shows monthly partitioning but no cleanup strategy. Notifications table will grow indefinitely.

---

# Notification System Design for 10M MAU Social App - COMPLETE REVISION

## Executive Summary

This proposal designs a **production-ready notification system** for a social media platform with 10M monthly active users. The architecture balances pragmatic engineering with genuine scalability needs, ensuring the 4-person team can deliver a working system in 6 months while handling viral traffic patterns.

**Key Design Principles:**
- **Start simple, scale smart**: Begin with proven patterns, add complexity only when needed
- **Fail gracefully**: System degrades performance before failing completely
- **Observable by default**: Every component has monitoring and alerting built-in
- **Cost-conscious**: Target $8K/month operational costs with clear scaling economics

**Delivery Timeline:**
- **Month 1-2**: Core API + basic push notifications
- **Month 3-4**: Email/SMS channels + user preferences
- **Month 5-6**: Advanced features + production hardening

## 1. Traffic Analysis & System Requirements

### Realistic Load Patterns
```
Daily Active Users: 3M (30% of 10M MAU)
Notification Generation:
- Comments: 2M/day (high engagement)
- Likes: 8M/day (bulk of traffic) 
- Follows: 500K/day
- Direct Messages: 4M/day
- System alerts: 500K/day
Total: 15M notifications/day = 174/second average

Peak Traffic (5-8pm daily):
- 5x average = 870 notifications/second

Viral Events (2-3x weekly):
- 30-45 minute duration
- 25x average = 4,350 notifications/second
- Affects 2M users simultaneously
```

### Channel Distribution & Costs
```
Push Notifications (FCM/APNS):
- 2.5M users opted-in (25% rate)
- 8M daily notifications
- Cost: Free tier sufficient

Email (SendGrid):
- 6M users opted-in (60% rate) 
- 4M daily emails
- Cost: $1,200/month

SMS (Twilio):
- 300K users opted-in (3% premium feature)
- 50K daily SMS (high-value only)
- Cost: $1,500/month

In-App:
- All 3M daily active users
- 15M daily notifications
- Cost: Storage only
```

## 2. Architecture Overview

### Multi-Tier Architecture
```
┌─────────────────────────────────────────────────────────┐
│                    Load Balancer                        │
└─────────────────┬───────────────────┬───────────────────┘
                  │                   │
        ┌─────────────────────┐ ┌─────────────────────┐
        │   Ingestion API     │ │   Delivery API      │
        │   (2 instances)     │ │   (2 instances)     │
        └─────────┬───────────┘ └─────────┬───────────┘
                  │                       │
        ┌─────────────────────────────────────────────────┐
        │                SQS Queues                      │
        │  Critical│High │Medium │Low │DLQ               │
        └─────────┬───────────────────────────────────────┘
                  │
        ┌─────────────────────────────────────────────────┐
        │              Delivery Workers                   │
        │   Push(4)│Email(2)│SMS(1)│InApp(2)             │
        └─────────┬───────────────────────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │        PostgreSQL         │
    │     (Read Replicas)       │
    └───────────────────────────┘
```

### Component Responsibilities
```
Ingestion API:
- Validate notification requests
- Apply user preferences
- Enqueue for delivery
- Rate limiting

Delivery Workers:
- Process queue messages
- Call external APIs
- Handle retries/failures
- Update delivery status

Delivery API:
- User preference management
- Notification history
- Analytics queries
```

## 3. Database Design (PostgreSQL with Read Replicas)

### Core Schema
```sql
-- Users table (simplified)
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255),
    phone VARCHAR(20),
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Comprehensive notification preferences
CREATE TABLE notification_preferences (
    user_id BIGINT REFERENCES users(id) PRIMARY KEY,
    
    -- Channel preferences
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    
    -- Content type preferences with granular controls
    comments_on_my_posts BOOLEAN DEFAULT true,
    comments_on_followed_posts BOOLEAN DEFAULT false,
    likes_on_my_posts BOOLEAN DEFAULT true,
    likes_from_followers_only BOOLEAN DEFAULT false,
    new_followers BOOLEAN DEFAULT true,
    direct_messages BOOLEAN DEFAULT true,
    friend_requests BOOLEAN DEFAULT true,
    
    -- Rate limiting
    max_push_per_hour INTEGER DEFAULT 10,
    max_email_per_day INTEGER DEFAULT 5,
    
    -- Quiet hours (stored as minutes from midnight in user's timezone)
    quiet_start INTEGER DEFAULT 1320, -- 22:00
    quiet_end INTEGER DEFAULT 480,    -- 08:00
    
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Device tokens for push notifications
CREATE TABLE device_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    token_hash VARCHAR(64) NOT NULL, -- SHA256 of actual token
    platform VARCHAR(10) NOT NULL CHECK (platform IN ('ios', 'android', 'web')),
    app_version VARCHAR(20),
    active BOOLEAN DEFAULT true,
    last_used TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(token_hash),
    INDEX idx_user_platform_active (user_id, platform, active)
);

-- Separate table for actual tokens (encrypted)
CREATE TABLE device_token_data (
    token_hash VARCHAR(64) PRIMARY KEY REFERENCES device_tokens(token_hash),
    encrypted_token TEXT NOT NULL -- AES-256 encrypted
);

-- Main notifications table (partitioned by month)
CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    
    -- Content
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    deep_link VARCHAR(500), -- App deep link
    image_url VARCHAR(500),
    data JSONB DEFAULT '{}',
    
    -- Delivery configuration
    priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 4),
    channels TEXT[] NOT NULL DEFAULT '{}',
    
    -- Timing
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    scheduled_for TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP, -- Optional expiration
    
    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'delivered', 'failed', 'expired')),
    delivered_at TIMESTAMP,
    failed_reason TEXT,
    
    -- Metadata
    source_service VARCHAR(50), -- Which service created this
    correlation_id VARCHAR(100), -- For tracing
    
    -- Indexes
    INDEX idx_user_created (user_id, created_at DESC),
    INDEX idx_status_scheduled (status, scheduled_for),
    INDEX idx_type_created (type, created_at)
) PARTITION BY RANGE (created_at);

-- Create partitions for current and next month
CREATE TABLE notifications_2024_01 PARTITION OF notifications
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Delivery attempts with exponential backoff tracking
CREATE TABLE delivery_attempts (
    id BIGSERIAL PRIMARY KEY,
    notification_id BIGINT NOT NULL,
    channel VARCHAR(20) NOT NULL,
    
    attempt_number INTEGER NOT NULL,
    attempted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    success BOOLEAN NOT NULL,
    
    -- Provider response
    external_id VARCHAR(255), -- FCM/SendGrid message ID
    http_status INTEGER,
    error_code VARCHAR(50),
    error_message TEXT,
    response_time_ms INTEGER,
    
    INDEX idx_notification_channel (notification_id, channel),
    INDEX idx_attempted_success (attempted_at, success)
) PARTITION BY RANGE (attempted_at);

-- Rate limiting tracking
CREATE TABLE user_rate_limits (
    user_id BIGINT NOT NULL,
    channel VARCHAR(20) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    
    PRIMARY KEY (user_id, channel, window_start),
    INDEX idx_window_start (window_start)
);

-- Automated partition management
CREATE OR REPLACE FUNCTION create_monthly_partitions()
RETURNS void AS $$
DECLARE
    start_date date;
    end_date date;
    table_name text;
BEGIN
    -- Create partition for next month
    start_date := date_trunc('month', CURRENT_DATE + interval '1 month');
    end_date := start_date + interval '1 month';
    
    -- Notifications partition
    table_name := 'notifications_' || to_char(start_date, 'YYYY_MM');
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF notifications FOR VALUES FROM (%L) TO (%L)',
                   table_name, start_date, end_date);
    
    -- Delivery attempts partition
    table_name := 'delivery_attempts_' || to_char(start_date, 'YYYY_MM');
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF delivery_attempts FOR VALUES FROM (%L) TO (%L)',
                   table_name, start_date, end_date);
END;
$$ LANGUAGE plpgsql;

-- Drop old partitions (keep 6 months)
CREATE OR REPLACE FUNCTION drop_old_partitions()
RETURNS void AS $$
DECLARE
    cutoff_date date;
    table_name text;
BEGIN
    cutoff_date := date_trunc('month', CURRENT_DATE - interval '6 months');
    
    FOR table_name IN 
        SELECT schemaname||'.'||tablename 
        FROM pg_tables 
        WHERE tablename ~ '^(notifications|delivery_attempts)_\d{4}_\d{2}$'
        AND tablename < 'notifications_' || to_char(cutoff_date, 'YYYY_MM')
    LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || table_name;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Schedule maintenance
SELECT cron.schedule('create-partitions', '0 0 1 * *', 'SELECT create_monthly_partitions()');
SELECT cron.schedule('drop-partitions', '0 2 1 * *', 'SELECT drop_old_partitions()');
```

### Database Scaling Strategy
```
Primary Database (r6g.2xlarge):
- 8 vCPU, 64GB RAM
- 500 IOPS provisioned
- Handles writes + real-time reads
- Cost: ~$1,400/month

Read Replicas (2x r6g.xlarge):
- 4 vCPU, 32GB RAM each
- For analytics and history queries
- Cost: ~$1,200/month total

Connection Pooling:
- PgBouncer on each app instance
- Max 100 connections to primary
- Max 50 connections per replica
```

## 4. Core Service Implementation

### Ingestion API (FastAPI)
```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, validator
from typing import List, Optional, Dict
import asyncio
import asyncpg
import json
import hashlib
from datetime import datetime, timedelta
import boto3
from cryptography.fernet import Fernet
import structlog

app = FastAPI(title="Notification Ingestion API")
logger = structlog.get_logger()

class NotificationRequest(BaseModel):
    user_ids: List[int]
    type: str
    title: str
    body: str
    deep_link: Optional[str] = None
    image_url: Optional[str] = None
    data: Dict = {}
    priority: int = 3
    channels: Optional[List[str]] = None
    scheduled_for: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    correlation_id: Optional[str] = None
    
    @validator('user_ids')
    def validate_user_ids(cls, v):
        if len(v) > 1000:
            raise ValueError('Maximum 1000 users per request')
        return v
    
    @validator('priority')
    def validate_priority(cls, v):
        if v not in [1, 2, 3, 4]:
            raise ValueError('Priority must be 1-4')
        return v
    
    @validator('type')
    def validate_type(cls, v):
        valid_types = ['comment', 'like', 'follow', 'message', 'friend_request', 'system']
        if v not in valid_types:
            raise ValueError(f'Type must be one of: {valid_types}')
        return v

class NotificationService:
    def __init__(self, db_pool, sqs_client, encryption_key):
        self.db = db_pool
        self.sqs = sqs_client
        self.cipher = Fernet(encryption_key)
        self.queue_urls = {
            1: 'https://sqs.us-east-1.amazonaws.com/123456789/notifications-critical',
            2: 'https://sqs.us-east-1.amazonaws.com/123456789/notifications-high',
            3: 'https://sqs.us-east-1.amazonaws.com/123456789/notifications-medium',
            4: 'https://sqs.us-east-1.amazonaws.com/123456789/notifications-low'
        }
    
    async def create_notifications(self, request: NotificationRequest) -> Dict[str, any]:
        """Create and queue notifications with comprehensive validation"""
        
        start_time = datetime.utcnow()
        correlation_id = request.correlation_id or f"req_{int(start_time.timestamp())}"
        
        try:
            # 1. Validate users exist and get preferences
            user_data = await self.get_user_preferences(request.user_ids)
            if not user_data:
                raise HTTPException(404, "No valid users found")
            
            # 2. Apply preference filtering and rate limiting
            eligible_notifications = []
            rate_limited_users = []
            
            for user_id, preferences in user_data.items():