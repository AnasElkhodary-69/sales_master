# Enhanced Webhook Analytics System

## Overview

The SalesBreachPro application now includes a comprehensive webhook analytics system that saves all Brevo email events to the database and provides accurate, real-time statistics for your email campaigns.

## Features Implemented

### 1. Database Schema Enhancement
- **New `WebhookEvent` model**: Stores all webhook events with detailed metadata
- **Event tracking**: Delivered, opened, clicked, replied, bounced, unsubscribed, spam complaints
- **Comprehensive data**: IP address, user agent, URLs clicked, bounce reasons, timestamps

### 2. Enhanced Webhook Processing
- **Automatic event saving**: All incoming webhooks are saved to the database
- **Campaign linking**: Events are linked to specific campaigns and contacts
- **Real-time updates**: Contact and email records are updated immediately
- **Error handling**: Robust error handling with rollback on failures

### 3. Analytics Service
- **Comprehensive statistics**: Open rates, click rates, reply rates, bounce rates
- **Time-based filtering**: Analytics for 7, 30, or custom day periods
- **Campaign-specific analytics**: Detailed metrics for individual campaigns
- **Contact timelines**: Event history for specific contacts
- **Top links tracking**: Most clicked links analysis

### 4. Enhanced Dashboard Integration
- **Real-time metrics**: Dashboard shows webhook-based statistics
- **Multiple timeframes**: 7-day and 30-day analytics
- **Event breakdown**: Detailed breakdown by event type
- **Daily analytics**: Day-by-day performance charts

## API Endpoints

### Webhook Analytics
```
GET /api/webhook-analytics?days=30
```
Returns comprehensive email analytics based on webhook events.

### Campaign Analytics  
```
GET /api/campaign-analytics/{campaign_id}?days=30
```
Returns webhook analytics for a specific campaign.

### Contact Timeline
```
GET /api/contact-timeline/{contact_id}?days=30
```
Returns event timeline for a specific contact.

### Daily Analytics
```
GET /api/daily-analytics?days=7
```
Returns day-by-day analytics for dashboard charts.

### Top Links
```
GET /api/top-links?days=30&limit=10
```
Returns most clicked links from webhook events.

### Dashboard Statistics
```
GET /api/webhook-dashboard-stats
```
Returns comprehensive statistics for dashboard display.

## Database Schema

### WebhookEvent Table
```sql
webhook_events:
├── id (Primary Key)
├── contact_id (Foreign Key -> contacts.id)
├── email_id (Foreign Key -> emails.id)
├── campaign_id (Foreign Key -> campaigns.id)
├── event_type (delivered, opened, clicked, replied, bounced, etc.)
├── provider (brevo, ses, etc.)
├── provider_message_id (External message ID)
├── event_data (JSON - Full webhook payload)
├── ip_address (User's IP address)
├── user_agent (User's browser/client)
├── clicked_url (URL clicked for click events)
├── bounce_reason (Bounce error message)
├── bounce_type (hard, soft)
├── event_timestamp (When event occurred)
├── received_at (When we received the webhook)
└── processed_at (When we processed the event)
```

## Analytics Metrics

### Email Performance
- **Open Rate**: Percentage of delivered emails that were opened
- **Click Rate**: Percentage of delivered emails that were clicked
- **Reply Rate**: Percentage of delivered emails that received replies
- **Bounce Rate**: Percentage of emails that bounced
- **Unsubscribe Rate**: Percentage that unsubscribed
- **Spam Rate**: Percentage marked as spam

### Engagement Metrics
- **Unique Opens**: Number of unique contacts who opened emails
- **Unique Clicks**: Number of unique contacts who clicked links
- **Unique Replies**: Number of unique contacts who replied
- **Total Events**: Total number of webhook events processed

### Campaign Insights
- **Campaign Performance**: Metrics specific to each campaign
- **Contact Journey**: Complete event timeline per contact
- **Link Performance**: Most clicked links and click counts
- **Daily Trends**: Performance trends over time

## Usage Examples

### Get Overall Analytics
```python
from services.webhook_analytics import create_webhook_analytics_service

analytics_service = create_webhook_analytics_service()
stats = analytics_service.get_email_analytics(days=30)

print(f"Open Rate: {stats['open_rate']}%")
print(f"Click Rate: {stats['click_rate']}%")
print(f"Reply Rate: {stats['reply_rate']}%")
```

### Get Campaign Analytics
```python
campaign_stats = analytics_service.get_campaign_analytics(
    campaign_id=1, 
    days=30
)
print(f"Campaign Open Rate: {campaign_stats['open_rate']}%")
```

### Get Contact Timeline
```python
timeline = analytics_service.get_contact_timeline(
    contact_id=1, 
    days=30
)
for event in timeline:
    print(f"{event['event_type']} at {event['event_timestamp']}")
```

## Migration

To add the webhook events table to an existing database:

```bash
python scripts/utilities/add_webhook_events_table.py
```

This script will:
- Check if the table already exists
- Create the `webhook_events` table if needed
- Verify the table structure
- Show table information

## Benefits

### Accurate Analytics
- **Real-time data**: Statistics update immediately when events occur
- **Complete tracking**: No missing events or delayed updates
- **Detailed insights**: Rich metadata for deeper analysis

### Campaign Optimization
- **Performance tracking**: Monitor campaign effectiveness in real-time
- **A/B testing support**: Compare different campaign strategies
- **Engagement analysis**: Understand contact behavior patterns

### Contact Management
- **Behavioral insights**: See complete contact interaction history
- **Segmentation**: Identify highly engaged vs. unresponsive contacts
- **Follow-up timing**: Optimize follow-up scheduling based on engagement

### Compliance & Quality
- **Bounce management**: Automatically handle hard bounces
- **Unsubscribe tracking**: Maintain compliance with email regulations
- **Spam monitoring**: Track and respond to spam complaints

## Dashboard Integration

The enhanced dashboard now shows:

1. **Real-time metrics** based on actual webhook events
2. **Comparative analytics** (7-day vs 30-day performance)
3. **Event breakdown** charts showing delivery, opens, clicks, replies
4. **Top performing links** with click counts
5. **Daily performance trends** for the past week

## Webhook Configuration

Ensure your Brevo webhook is configured to send events to:
```
https://yourdomain.com/webhooks/brevo
```

Supported events:
- `delivered` - Email successfully delivered
- `opened` - Email opened by recipient
- `clicked` - Link clicked in email
- `replied` - Reply received
- `bounced` - Email bounced (hard/soft)
- `unsubscribed` - Recipient unsubscribed
- `spam` - Marked as spam/complaint

## Testing

### Simulate Webhook Events
```bash
curl -X POST https://yourdomain.com/api/simulate-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event": "opened",
    "email": "test@example.com",
    "message_id": "test_123"
  }'
```

### View Analytics
```bash
curl https://yourdomain.com/api/webhook-analytics?days=30
```

The enhanced webhook analytics system provides comprehensive tracking and insights for your email campaigns, enabling data-driven optimization and better campaign performance.