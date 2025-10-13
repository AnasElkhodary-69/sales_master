# Flexible Email Delay Units

The email sequence system now supports flexible delay units (minutes, hours, days) instead of just days.

## Features

### Supported Units
- **Minutes**: `minutes`, `minute`, `min`
- **Hours**: `hours`, `hour`, `hr`  
- **Days**: `days`, `day`

### Database Changes

New columns added to the `email_templates` table:
- `delay_amount` (INTEGER) - The numeric amount (e.g., 15, 2, 1)
- `delay_unit` (VARCHAR(10)) - The unit ('minutes', 'hours', 'days')

The old `delay_days` column is still supported for backward compatibility.

### Usage Examples

#### Setting Up Templates with Flexible Delays

```python
# Update a template to send after 15 minutes
template.delay_amount = 15
template.delay_unit = 'minutes'

# Update a template to send after 2 hours
template.delay_amount = 2
template.delay_unit = 'hours'

# Update a template to send after 1 day
template.delay_amount = 1
template.delay_unit = 'days'
```

#### Example Sequence Flow

1. **Immediate Email**: `0 minutes` - Sent right away
2. **Follow-up 1**: `30 minutes` - Sent 30 minutes later
3. **Follow-up 2**: `2 hours` - Sent 2 hours after enrollment
4. **Follow-up 3**: `1 days` - Sent 1 day after enrollment

## Technical Details

### Conversion Logic

The system converts delay amounts and units to Python `timedelta` objects:

```python
def _calculate_delay_timedelta(self, delay_amount: int, delay_unit: str) -> timedelta:
    unit = delay_unit.lower()
    if unit in ['minute', 'minutes', 'min']:
        return timedelta(minutes=delay_amount)
    elif unit in ['hour', 'hours', 'hr']:
        return timedelta(hours=delay_amount)
    elif unit in ['day', 'days']:
        return timedelta(days=delay_amount)
```

### Backward Compatibility

The system prioritizes the new delay system but falls back to the old `delay_days` system:

1. If `delay_amount` and `delay_unit` are set, use them
2. Otherwise, fall back to `delay_days` (converted to days)
3. Default to no delay if neither is set

### Database Migration

The migration script automatically:
- Adds new columns to existing tables
- Migrates existing `delay_days` values to the new format
- Sets default values (`delay_amount=0`, `delay_unit='days'`)

## API Response Format

When enrolling contacts, the response now includes both old and new delay information:

```json
{
  "success": true,
  "emails_scheduled": 4,
  "scheduled_emails": [
    {
      "step": 0,
      "delay_days": 0,
      "delay_amount": 0,
      "delay_unit": "minutes",
      "scheduled_date": "2025-09-13"
    },
    {
      "step": 1, 
      "delay_days": 0,
      "delay_amount": 30,
      "delay_unit": "minutes",
      "scheduled_date": "2025-09-13"
    }
  ]
}
```

## Testing

Use the provided test scripts:
- `test_delay_units.py` - Tests conversion functions
- `test_flexible_delay_flow.py` - Tests complete email flow

## Frontend Integration

When building forms for template editing, provide dropdown options:

```html
<input type="number" name="delay_amount" placeholder="Amount">
<select name="delay_unit">
  <option value="minutes">Minutes</option>
  <option value="hours">Hours</option>
  <option value="days">Days</option>
</select>
```

This enables users to set precise timing like "Send follow-up after 15 minutes" or "Send reminder after 2 hours".