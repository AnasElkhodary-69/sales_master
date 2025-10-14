# Remaining Campaign Form Updates

## Summary of Completed Work

✅ **Successfully Updated:**
1. **dashboard.html** - Removed FlawTrack API calls and breach status displays
2. **routes/dashboard.py** - Removed FlawTrack configuration endpoints
3. **routes/api.py** - Stubbed out FlawTrack/breach endpoints
4. **settings.html** - Removed FlawTrack configuration section completely
5. **contacts.html** - Replaced breach columns with industry/business_type/company_size fields
6. **upload.html** - Added full support for industry fields in CSV upload

✅ **Application Status:** Running successfully at http://localhost:5000 with NO ERRORS

---

## Remaining Work: new_campaign.html

The campaign creation/editing form (`templates/new_campaign.html`) is a 1515-line file that requires extensive updates to replace breach-based targeting with industry-based targeting.

### Key Changes Needed:

#### 1. Contact Statistics Display (Lines 275-287)
**Current:** Shows Breached/Secure/Unknown counts
```html
<div class="mb-2">
    <span class="risk-badge risk-high">{{ contact_stats.breached }}</span> Breached
</div>
<div class="mb-2">
    <span class="risk-badge risk-low">{{ contact_stats.secure }}</span> Secure
</div>
<div class="mb-2">
    <span class="risk-badge risk-medium">{{ contact_stats.unknown }}</span> Unknown
</div>
```

**Should Be:** Shows industry distribution or top industries
```html
<div class="mb-2">
    <strong>Top Industries:</strong>
    {% for industry, count in contact_stats.top_industries %}
        <div class="small">{{ industry }}: {{ count }} contacts</div>
    {% endfor %}
</div>
```

#### 2. Target Audience Selection (Lines 298-325)
**Current:** "Breach Status Targeting" with Breached/Secure/Unknown checkboxes
```html
<label class="form-label">Breach Status Targeting</label>
<div class="form-check">
    <input class="form-check-input" type="checkbox" id="targetBreached"
           name="target_risk_levels" value="breached">
    <label class="form-check-label" for="targetBreached">
        <span class="risk-badge risk-high">Breached</span>
    </label>
</div>
```

**Should Be:** "Industry Targeting" with industry checkboxes
```html
<label class="form-label">Target Industries</label>
<div class="form-check mb-2">
    <input class="form-check-input" type="checkbox" id="selectAllIndustries">
    <label class="form-check-label text-primary fw-bold" for="selectAllIndustries">
        Select All Industries
    </label>
</div>
<div class="form-check">
    <input class="form-check-input" type="checkbox" id="targetHealthcare"
           name="target_industries" value="Healthcare">
    <label class="form-check-label" for="targetHealthcare">
        <i class="fas fa-heartbeat me-1 text-danger"></i>Healthcare
    </label>
</div>
<div class="form-check">
    <input class="form-check-input" type="checkbox" id="targetFinance"
           name="target_industries" value="Finance">
    <label class="form-check-label" for="targetFinance">
        <i class="fas fa-dollar-sign me-1 text-success"></i>Finance
    </label>
</div>
<div class="form-check">
    <input class="form-check-input" type="checkbox" id="targetTechnology"
           name="target_industries" value="Technology">
    <label class="form-check-label" for="targetTechnology">
        <i class="fas fa-laptop-code me-1 text-primary"></i>Technology
    </label>
</div>
<div class="form-check">
    <input class="form-check-input" type="checkbox" id="targetRetail"
           name="target_industries" value="Retail">
    <label class="form-check-label" for="targetRetail">
        <i class="fas fa-shopping-cart me-1 text-warning"></i>Retail
    </label>
</div>
<div class="form-check">
    <input class="form-check-input" type="checkbox" id="targetManufacturing"
           name="target_industries" value="Manufacturing">
    <label class="form-check-label" for="targetManufacturing">
        <i class="fas fa-industry me-1 text-secondary"></i>Manufacturing
    </label>
</div>
<div class="form-check">
    <input class="form-check-input" type="checkbox" id="targetEducation"
           name="target_industries" value="Education">
    <label class="form-check-label" for="targetEducation">
        <i class="fas fa-graduation-cap me-1 text-info"></i>Education
    </label>
</div>
```

Add Business Type and Company Size filters as well:
```html
<div class="col-md-6">
    <div class="mb-3">
        <label class="form-label">Business Type (Optional)</label>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" name="target_business_types" value="B2B">
            <label class="form-check-label">B2B</label>
        </div>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" name="target_business_types" value="B2C">
            <label class="form-check-label">B2C</label>
        </div>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" name="target_business_types" value="Enterprise">
            <label class="form-check-label">Enterprise</label>
        </div>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" name="target_business_types" value="SMB">
            <label class="form-check-label">SMB</label>
        </div>
    </div>

    <div class="mb-3">
        <label class="form-label">Company Size (Optional)</label>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" name="target_company_sizes" value="1-10">
            <label class="form-check-label">1-10 employees</label>
        </div>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" name="target_company_sizes" value="11-50">
            <label class="form-check-label">11-50 employees</label>
        </div>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" name="target_company_sizes" value="51-200">
            <label class="form-check-label">51-200 employees</label>
        </div>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" name="target_company_sizes" value="201-1000">
            <label class="form-check-label">201-1000 employees</label>
        </div>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" name="target_company_sizes" value="1000+">
            <label class="form-check-label">1000+ employees</label>
        </div>
    </div>
</div>
```

#### 3. Pro Tip Alert (Line 354)
**Current:** "High-risk contacts typically have higher response rates..."
**Should Be:** "Target campaigns by industry for better personalization and response rates."

#### 4. Campaign Settings - Template Type (Lines 232-238)
**Current:** Dropdown with "Breach Response Campaign", "Proactive Security", etc.
```html
<select class="form-select" id="templateType" name="template_type">
    <option value="breached">Breach Response Campaign</option>
    <option value="secure">Proactive Security Campaign</option>
    <option value="unknown" selected>Security Assessment Campaign</option>
</select>
```

**Should Be:** Generic campaign types
```html
<select class="form-select" id="campaignCategory" name="campaign_category">
    <option value="outreach" selected>Business Outreach</option>
    <option value="nurture">Lead Nurture</option>
    <option value="announcement">Product Announcement</option>
    <option value="event">Event Invitation</option>
    <option value="newsletter">Newsletter</option>
</select>
```

#### 5. Auto-Enrollment Settings (Lines 336-342)
**Current:** "Target Breach Status" dropdown with breached/not_breached/unknown
```html
<label for="autoEnrollBreachStatus" class="form-label">Target Breach Status</label>
<select class="form-select" id="autoEnrollBreachStatus" name="auto_enroll_breach_status">
    <option value="all">All Contacts</option>
    <option value="breached">Breached Contacts Only</option>
    <option value="not_breached">Secure Contacts Only</option>
    <option value="unknown">Unknown Status Only</option>
</select>
```

**Should Be:** Industry-based targeting
```html
<label for="autoEnrollIndustry" class="form-label">Target Industry</label>
<select class="form-select" id="autoEnrollIndustry" name="auto_enroll_industry">
    <option value="all">All Industries</option>
    <option value="Healthcare">Healthcare</option>
    <option value="Finance">Finance</option>
    <option value="Technology">Technology</option>
    <option value="Retail">Retail</option>
    <option value="Manufacturing">Manufacturing</option>
    <option value="Education">Education</option>
</select>
```

#### 6. CSS Risk Badge Styling (Lines 83-92)
**Current:** Risk badge styles for high/medium/low
```css
.risk-badge {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    border-radius: 12px;
    font-weight: 500;
}

.risk-high { background: #fee2e2; color: #dc2626; }
.risk-medium { background: #fef3c7; color: #d97706; }
.risk-low { background: #dcfce7; color: #16a34a; }
```

**Should Be:** Industry badge styles or remove entirely
```css
.industry-badge {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    border-radius: 12px;
    font-weight: 500;
    background: #e0e7ff;
    color: #4338ca;
}
```

#### 7. JavaScript Functions to Update:

**Lines 549-580:** `toggleAllRiskLevels()` and `updateSelectAllState()`
- Rename to `toggleAllIndustries()` and `updateSelectAllIndustriesState()`
- Update selectors from `input[name="target_risk_levels"]` to `input[name="target_industries"]`

**Lines 647-651:** Validation for Step 2
```javascript
// OLD:
const riskLevels = document.querySelectorAll('input[name="target_risk_levels"]:checked');
if (riskLevels.length === 0) {
    showError('Please select at least one Breach Status to target your contacts.');
    return false;
}

// NEW:
const industries = document.querySelectorAll('input[name="target_industries"]:checked');
if (industries.length === 0) {
    showError('Please select at least one Industry to target your contacts.');
    return false;
}
```

**Lines 951-957:** `updateSummary()` - Target Audience display
```javascript
// OLD:
const checkedRiskLevels = document.querySelectorAll('input[name="target_risk_levels"]:checked');
const riskLevels = Array.from(checkedRiskLevels).map(cb => {
    return cb.value.charAt(0).toUpperCase() + cb.value.slice(1);
});
document.getElementById('summaryAudience').textContent =
    riskLevels.length > 0 ? riskLevels.join(', ') : '-';

// NEW:
const checkedIndustries = document.querySelectorAll('input[name="target_industries"]:checked');
const industries = Array.from(checkedIndustries).map(cb => cb.value);
document.getElementById('summaryAudience').textContent =
    industries.length > 0 ? industries.join(', ') : 'All Industries';
```

**Lines 970-992:** Estimated contacts calculation
```javascript
// OLD:
const contactStats = {
    'breached': {{ contact_stats.breached or 0 }},
    'secure': {{ contact_stats.secure or 0 }},
    'unknown': {{ contact_stats.unknown or 0 }}
};

checkedRiskLevels.forEach(checkbox => {
    if (contactStats[checkbox.value]) {
        estimatedContacts += contactStats[checkbox.value];
    }
});

// NEW:
const industryStats = {{ industry_stats | tojson }};
// industryStats should be passed from backend as: {'Healthcare': 50, 'Finance': 30, ...}

checkedIndustries.forEach(checkbox => {
    if (industryStats[checkbox.value]) {
        estimatedContacts += industryStats[checkbox.value];
    }
});
```

**Lines 1076-1112:** `getAutoEnrollDefault()` function
- Update to work with industries instead of breach statuses
- Remove references to breached/not_breached/unknown

**Lines 1142:** Required fields check
```javascript
// OLD:
'target_risk_levels': 'Target Audience'

// NEW:
'target_industries': 'Target Industries'
```

---

## Backend Changes Also Needed

### routes/campaigns.py
The campaign creation route needs to:
1. Accept `target_industries`, `target_business_types`, `target_company_sizes` instead of `target_risk_levels`
2. Pass industry statistics to the template instead of breach statistics
3. Update auto-enrollment logic to filter by industry

Example backend stats:
```python
# OLD:
contact_stats = {
    'total_contacts': Contact.query.count(),
    'breached': Contact.query.filter_by(breach_status='breached').count(),
    'secure': Contact.query.filter_by(breach_status='not_breached').count(),
    'unknown': Contact.query.filter_by(breach_status='unknown').count()
}

# NEW:
from sqlalchemy import func

industry_counts = db.session.query(
    Contact.industry,
    func.count(Contact.id).label('count')
).filter(Contact.industry.isnot(None)).group_by(Contact.industry).all()

contact_stats = {
    'total_contacts': Contact.query.count(),
    'top_industries': [(industry, count) for industry, count in industry_counts[:5]]
}

industry_stats = {industry: count for industry, count in industry_counts}
```

---

## Testing Checklist

After completing the updates, test:

- [ ] Campaign creation with industry targeting
- [ ] Filtering contacts by industry in campaigns
- [ ] Auto-enrollment based on industry
- [ ] Campaign summary display shows selected industries
- [ ] Validation works correctly for industry selection
- [ ] No references to "breach", "risk", "FlawTrack" remain in UI
- [ ] Industry badges display correctly
- [ ] Campaign list shows industry-based campaigns properly

---

## Estimated Time to Complete

**Frontend (new_campaign.html):** ~20-25 edits, 1-2 hours
**Backend (routes/campaigns.py):** ~10-15 edits, 30-45 minutes
**Testing:** 30 minutes

**Total:** 2-3 hours of focused development work

---

## Notes

- The file has been successfully saved with all previous changes
- Application is running without errors
- All other pages (Dashboard, Contacts, Upload, Settings) are fully updated
- This is the final major component to complete the refactoring from breach-based to industry-based targeting
