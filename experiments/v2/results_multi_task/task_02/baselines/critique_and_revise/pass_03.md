## Critical Review of Original Proposal

### Major Problems Identified:

1. **Code-Heavy Instead of System Design**: This reads like a technical implementation guide rather than a system design proposal. A 4-engineer team needs architectural decisions, not code snippets they'll rewrite anyway.

2. **PostgreSQL Will Collapse Under Load**: 450M notification records/month in PostgreSQL is a recipe for disaster. Even with partitioning, write throughput will bottleneck at ~50K notifications/minute, far below the 150K/minute requirement.

3. **Missing Critical System Components**: No mention of load balancers, CDN for templates, monitoring/alerting, or deployment strategy. These are essential for 10M users.

4. **Naive Batching Strategy**: The proposal mentions batching but provides no actual batching logic. Email batching alone could save 70% on costs but isn't designed.

5. **No Failure Recovery Plan**: What happens when SQS fills up? When push services are down? When the database is overwhelmed? Zero discussion of graceful degradation.

6. **Unrealistic Channel Distribution**: 70% push notifications for 10M users means 7M push notifications daily. Most apps see 20-30% push opt-in rates, making this impossible.

7. **Missing Business Logic**: No discussion of notification types, content personalization, or how the social app's viral nature affects notification patterns.

8. **Infrastructure Costs Ignored**: The proposed architecture would cost $80K+/month with no cost optimization strategies.

---

# Notification System Design for 10M MAU Social App - COMPLETE REVISION

## Executive Summary

This proposal designs a notification system capable of handling 10M monthly active users (2.5M daily active) for a social media platform. The system prioritizes reliability, cost-effectiveness, and operational simplicity while planning for viral traffic spikes that can increase notification volume by 50x during trending events.

**Core Constraints:**
- 4 backend engineers, 6 months delivery timeline
- Social app viral traffic patterns (extreme spikes)
- Budget target: <$25K/month operational costs
- 99.9% delivery reliability for critical notifications

**Key Design Decisions:**
- Hybrid database approach: PostgreSQL for users, DynamoDB for notifications
- Aggressive batching to reduce costs by 60%
- Circuit breakers and graceful degradation for viral spikes
- Simple infrastructure: ECS instead of Kubernetes

## 1. Realistic Traffic Analysis & Business Context

### Social App Notification Patterns
```
Base Traffic (Normal Days):
- 2.5M DAU (25% of MAU - typical for social apps)
- 8M notifications/day (3.2 per active user)
- 93 notifications/second average
- 500 notifications/second peak (5x multiplier)

Viral Event Traffic (5-10 times per month):
- Trending content triggers notification storms
- 50x traffic spike possible (25K notifications/second)
- Duration: 15-30 minutes typically
- Affects 20-40% of user base simultaneously
```

### Channel Adoption Reality Check
```
Realistic Channel Distribution (based on social app benchmarks):
- Push: 25% of users (not 70% - most disable after initial spam)
- Email: 60% of users (higher tolerance, better engagement)
- In-app: 95% of users (unavoidable)
- SMS: 5% of users (expensive, high-value only)

Daily Volume:
- Push: 2M notifications
- Email: 4.8M notifications  
- In-app: 7.6M notifications
- SMS: 400K notifications
```

### Notification Categories for Social Apps
```
Critical (immediate delivery required):
- Direct messages
- Live video from followed users
- Safety/security alerts

High Priority (deliver within 5 minutes):
- Comments on user's content
- New followers
- Mentions in posts

Medium Priority (batch delivery acceptable):
- Likes on content
- Friend suggestions
- Weekly digest

Low Priority (daily batch):
- Trending content suggestions
- App feature announcements
```

## 2. System Architecture Overview

### High-Level Architecture
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Social    │───▶│ Notification│───▶│   Message   │───▶│   Channel   │
│    App      │    │   Gateway   │    │   Router    │    │ Processors  │
│  Services   │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                            │                   │                   │
                    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                    │   User      │    │  Batching   │    │  Delivery   │
                    │ Preferences │    │   Engine    │    │  Tracking   │
                    └─────────────┘    └─────────────┘    └─────────────┘
```

### Infrastructure Stack (Optimized for Team Size)
```
Load Balancing: AWS Application Load Balancer
Compute: ECS Fargate (auto-scaling, no server management)
Databases: 
  - PostgreSQL RDS (user data, preferences)
  - DynamoDB (notifications, delivery logs)
Queues: SQS Standard + FIFO for ordered delivery
Cache: ElastiCache Redis (preferences, rate limiting)
Storage: S3 (email templates, large payloads)
CDN: CloudFront (template assets, images)
Monitoring: CloudWatch + DataDog (application metrics)
```

### Why This Stack?
- **ECS over Kubernetes**: 4-person team can't manage K8s complexity
- **Hybrid Database**: PostgreSQL for ACID transactions, DynamoDB for scale
- **Managed Services**: Reduces operational burden on small team
- **Proven Technologies**: Lower risk, faster implementation

## 3. Database Design Strategy

### User & Preferences (PostgreSQL RDS)
**Why PostgreSQL**: User preferences need ACID compliance, complex queries, and are relatively small dataset (<50GB).

```sql
-- Optimized for read-heavy workload
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    timezone VARCHAR(50) DEFAULT 'UTC',
    push_opt_in BOOLEAN DEFAULT false,
    email_opt_in BOOLEAN DEFAULT true,
    sms_opt_in BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Denormalized preferences for performance
CREATE TABLE notification_settings (
    user_id BIGINT PRIMARY KEY,
    
    -- Channel preferences
    push_enabled BOOLEAN DEFAULT false,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    
    -- Category preferences (bitfield for performance)
    enabled_categories INTEGER DEFAULT 2047, -- All enabled initially
    
    -- Timing controls
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Rate limiting
    daily_push_limit INTEGER DEFAULT 10,
    daily_email_limit INTEGER DEFAULT 5,
    
    -- Tracking
    last_updated TIMESTAMP DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_push_enabled (user_id, push_enabled),
    INDEX idx_email_enabled (user_id, email_enabled)
);

-- Device tokens (separate table for normalization)
CREATE TABLE device_tokens (
    token_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    token_hash VARCHAR(64) UNIQUE, -- SHA-256 of actual token
    platform ENUM('ios', 'android', 'web'),
    active BOOLEAN DEFAULT true,
    last_used TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_user_active (user_id, active, last_used)
);
```

### Notifications & Delivery (DynamoDB)
**Why DynamoDB**: Handles write-heavy workload (150K/minute), auto-scaling, and cost-effective at scale.

```json
// Notification Storage Table
{
  "TableName": "notifications",
  "KeySchema": [
    {"AttributeName": "user_id", "KeyType": "HASH"},
    {"AttributeName": "created_at", "KeyType": "RANGE"}
  ],
  "AttributeDefinitions": [
    {"AttributeName": "user_id", "AttributeType": "N"},
    {"AttributeName": "created_at", "AttributeType": "S"},
    {"AttributeName": "notification_id", "AttributeType": "S"},
    {"AttributeName": "category", "AttributeType": "S"}
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "category-created_at-index",
      "KeySchema": [
        {"AttributeName": "category", "KeyType": "HASH"},
        {"AttributeName": "created_at", "KeyType": "RANGE"}
      ]
    }
  ],
  "BillingMode": "ON_DEMAND",
  "TimeToLiveSpecification": {
    "AttributeName": "ttl",
    "Enabled": true
  }
}

// Sample notification record
{
  "user_id": 12345,
  "created_at": "2024-01-15T10:30:00Z",
  "notification_id": "uuid-here",
  "category": "comment",
  "priority": "high",
  "title": "New comment on your post",
  "body": "John commented: 'Great photo!'",
  "data": {
    "post_id": "67890",
    "comment_id": "11111",
    "action_url": "app://post/67890"
  },
  "channels": ["push", "email"],
  "status": "pending",
  "ttl": 1705402200 // 90 days from creation
}
```

### Delivery Tracking (DynamoDB)
```json
{
  "TableName": "delivery_logs",
  "KeySchema": [
    {"AttributeName": "notification_id", "KeyType": "HASH"},
    {"AttributeName": "channel", "KeyType": "RANGE"}
  ],
  "AttributeDefinitions": [
    {"AttributeName": "notification_id", "AttributeType": "S"},
    {"AttributeName": "channel", "AttributeType": "S"},
    {"AttributeName": "user_id", "AttributeType": "N"},
    {"AttributeName": "delivered_at", "AttributeType": "S"}
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "user-delivered-index",
      "KeySchema": [
        {"AttributeName": "user_id", "KeyType": "HASH"},
        {"AttributeName": "delivered_at", "KeyType": "RANGE"}
      ]
    }
  ]
}
```

## 4. Notification Gateway & Routing

### Message Ingestion API
```python
# Simple, focused API design
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict

class NotificationRequest(BaseModel):
    user_ids: List[int]  # Support batch creation
    category: str        # 'comment', 'like', 'follow', 'dm'
    priority: str        # 'critical', 'high', 'medium', 'low'
    title: str
    body: str
    data: Dict          # Custom payload
    channels: Optional[List[str]] = None  # Override default channels
    send_at: Optional[datetime] = None    # Scheduled delivery

app = FastAPI()

@app.post("/notifications")
async def create_notifications(request: NotificationRequest):
    """
    Create notifications for multiple users
    Handles up to 1000 users per request for efficiency
    """
    if len(request.user_ids) > 1000:
        raise HTTPException(400, "Maximum 1000 users per request")
    
    # Generate unique notification IDs
    notification_ids = []
    
    for user_id in request.user_ids:
        notification_id = f"{uuid.uuid4()}"
        
        # Create notification record
        notification = {
            'user_id': user_id,
            'created_at': datetime.utcnow().isoformat(),
            'notification_id': notification_id,
            'category': request.category,
            'priority': request.priority,
            'title': request.title,
            'body': request.body,
            'data': request.data,
            'channels': request.channels or get_default_channels(request.category),
            'status': 'pending',
            'ttl': int((datetime.utcnow() + timedelta(days=90)).timestamp())
        }
        
        # Store in DynamoDB
        await dynamodb_client.put_item(
            TableName='notifications',
            Item=notification
        )
        
        # Route to appropriate queue based on priority
        queue_name = get_queue_for_priority(request.priority)
        
        await sqs_client.send_message(
            QueueUrl=queue_name,
            MessageBody=json.dumps({
                'notification_id': notification_id,
                'user_id': user_id,
                'priority': request.priority,
                'send_at': request.send_at.isoformat() if request.send_at else None
            }),
            DelaySeconds=0 if request.priority == 'critical' else 30
        )
        
        notification_ids.append(notification_id)
    
    return {"notification_ids": notification_ids, "status": "queued"}

def get_default_channels(category: str) -> List[str]:
    """Define default channels per category"""
    channel_map = {
        'dm': ['push'],  # Direct messages: immediate push only
        'comment': ['push', 'email'],  # Comments: push + email
        'like': ['push'],  # Likes: push only (high volume)
        'follow': ['push', 'email'],  # New followers: both channels
        'digest': ['email'],  # Weekly digest: email only
        'security': ['push', 'email', 'sms']  # Security: all channels
    }
    return channel_map.get(category, ['push'])

def get_queue_for_priority(priority: str) -> str:
    """Route to different queues for priority handling"""
    queue_map = {
        'critical': 'notifications-critical.fifo',  # FIFO for ordering
        'high': 'notifications-high',
        'medium': 'notifications-medium', 
        'low': 'notifications-low'
    }
    return queue_map.get(priority, 'notifications-medium')
```

## 5. Intelligent Batching Engine

### Email Batching (Critical for Cost Control)
```python
class EmailBatcher:
    """
    Batches email notifications to reduce costs by 70%
    Key insight: Users don't need immediate emails for social notifications
    """
    
    def __init__(self):
        self.batch_intervals = {
            'critical': 0,      # Send immediately
            'high': 300,        # 5 minutes
            'medium': 1800,     # 30 minutes  
            'low': 86400        # Daily digest
        }
        
    async def process_email_queue(self):
        """Main batching loop - runs every 5 minutes"""
        
        while True:
            try:
                # Process each priority level
                for priority, interval in self.batch_intervals.items():
                    if self.should_process_batch(priority, interval):
                        await self.create_batches_for_priority(priority)
                
                await asyncio.sleep(300)  # 5 minute cycle
                
            except Exception as e:
                logger.error(f"Batching error: {e}")
                await asyncio.sleep(60)  # Shorter retry on error
    
    async def create_batches_for_priority(self, priority: str):
        """Create email batches for a priority level"""
        
        # Get pending email notifications for this priority
        cutoff_time = datetime.utcnow() - timedelta(
            seconds=self.batch_intervals[priority]
        )
        
        pending_notifications = await self.get_pending_emails(
            priority=priority,
            older_than=cutoff_time
        )
        
        if not pending_notifications:
            return
        
        # Group by user for batching
        user_batches = {}
        for notification