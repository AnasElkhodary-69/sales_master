# Brevo Webhook Setup Guide

## Why Webhooks Are Required

In a multi-tenant system where each client uses their own Brevo account and API key, **each client MUST configure webhooks** in their Brevo dashboard to enable:

- ✅ **Stop-on-reply** - Automatically stop email sequences when contacts reply
- ✅ **Real-time tracking** - Opens, clicks, bounces, unsubscribes
- ✅ **Better deliverability** - Stop sending to contacts who bounced or marked as spam

Without webhooks configured, the system will:
- ❌ Continue sending follow-up emails even after a contact replies
- ❌ Miss bounce and spam events
- ❌ Have no real-time engagement tracking

## Configuration Steps for Each Client

### Step 1: Log into Brevo Dashboard

Each client needs to log into their own Brevo account at https://app.brevo.com

### Step 2: Navigate to Webhooks Settings

1. Click on **Settings** (top right corner)
2. Click on **Webhooks** in the left sidebar
3. Click **Add a new webhook**

### Step 3: Configure the Webhook

**Webhook URL**: `https://marketing.savety.online/webhooks/brevo`

**Events to Enable** (check ALL of these):

#### Transactional Emails:
- ✅ `delivered` - Email successfully delivered
- ✅ `opened` - Recipient opened the email
- ✅ `clicked` - Recipient clicked a link
- ✅ `hard_bounce` - Email address is invalid/doesn't exist
- ✅ `soft_bounce` - Temporary delivery failure
- ✅ `blocked` - Email blocked by spam filters
- ✅ `spam` - Recipient marked email as spam
- ✅ `unsubscribed` - Recipient unsubscribed
- ✅ **`replied`** - **MOST IMPORTANT** - Recipient replied to the email

### Step 4: Test the Webhook

After saving, Brevo will send a test webhook. You should see:
- ✅ Green checkmark indicating the webhook is working
- If it fails, check that the URL is correct and the server is accessible

### Step 5: Verify in Application

After webhook is configured:

1. Send a test email to yourself
2. Reply to that email
3. Check that the sequence stops (no more follow-ups are sent)
4. Check the contact in the dashboard - should show `has_responded: True`

## Technical Details

### Webhook Endpoint

- **URL**: `https://marketing.savety.online/webhooks/brevo`
- **Method**: POST
- **Content-Type**: application/json
- **Authentication**: Optional signature verification (configured via BREVO_WEBHOOK_SECRET in .env)

### What Happens When a Reply is Detected

1. Brevo detects the reply in the client's inbox
2. Brevo sends a webhook to your server with event type `replied`
3. Your server identifies the contact by email address
4. The system marks the contact as `has_responded = True`
5. All scheduled future emails for this contact are cancelled with status `skipped_replied`
6. The campaign's `response_count` is incremented

### Multi-Tenant Support

The webhook system is **client-agnostic**:
- Each client configures webhooks in their own Brevo account
- All webhooks point to the same URL on your server
- Your server identifies contacts by email address (works across all clients)
- No additional configuration needed in your application

## Troubleshooting

### Webhook Not Working

1. **Check webhook status in Brevo dashboard**
   - Look for failed webhook attempts
   - Check error messages

2. **Verify server is accessible**
   ```bash
   curl -X POST https://marketing.savety.online/webhooks/brevo \
     -H "Content-Type: application/json" \
     -d '{"event": "replied", "email": "test@example.com"}'
   ```

3. **Check application logs**
   - Look for "Received Brevo webhook" messages
   - Check for errors in webhook processing

### Sequences Still Sending After Reply

1. **Confirm webhook is configured** in client's Brevo account
2. **Check the `replied` event is enabled** in webhook settings
3. **Verify contact email matches** - webhook email must match contact email in database
4. **Check timing** - if reply came after all emails already sent, webhook won't help (emails already sent)

### Testing Without Actual Replies

You can simulate webhooks for testing:

```bash
# Simulate a reply event
curl -X POST http://localhost:5001/webhooks/brevo \
  -H "Content-Type: application/json" \
  -d '{
    "event": "replied",
    "email": "contact@example.com",
    "subject": "Re: Your email subject",
    "message-id": "<message-id-from-brevo>"
  }'
```

## Client Onboarding Checklist

When adding a new client to the system:

- [ ] Client provides Brevo API key
- [ ] Add client to database with Brevo credentials
- [ ] **Configure webhook in client's Brevo dashboard** (point to your server)
- [ ] Enable all transactional email events (especially `replied`)
- [ ] Send test email and verify webhook is working
- [ ] Test reply detection by replying to test email
- [ ] Confirm sequences stop after reply

## Alternative: IMAP-Based Reply Detection (Not Recommended)

If a client cannot configure webhooks, you can use IMAP-based reply detection:

**Disadvantages**:
- Requires client to provide IMAP credentials (security risk)
- Polling-based (5-minute delay, not real-time)
- More complex to maintain
- Doesn't work with all email providers

**Only use IMAP if webhooks are absolutely not possible.**

For IMAP setup, each client would need to add:
- `imap_server` (e.g., imap.gmail.com)
- `imap_email` (their sender email)
- `imap_password` (app password for Gmail, or email password)

Then the system would poll each client's inbox every 5 minutes looking for replies.

## Summary

**For best results and stop-on-reply to work correctly:**

1. ✅ Each client MUST configure Brevo webhooks
2. ✅ Webhook URL: `https://marketing.savety.online/webhooks/brevo`
3. ✅ Enable the `replied` event (and all other transactional events)
4. ✅ Test webhook after configuration
5. ✅ Verify stop-on-reply works with a test email

Without webhooks, the system will continue sending emails even after replies! 🚨
