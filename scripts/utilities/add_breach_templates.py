#!/usr/bin/env python3
"""
Add breach-aware email templates to the database
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.database import EmailTemplate, db

def add_breach_templates():
    """Add email templates that use breach data from FlawTrack"""
    
    print("[INFO] Adding breach-aware email templates...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Breach response templates (when FlawTrack finds breaches)
            breach_templates = [
                {
                    'name': 'Urgent Breach Alert - Initial',
                    'template_type': 'breached',
                    'risk_level': 'high',
                    'sequence_step': 0,
                    'breach_template_type': 'breached',
                    'subject_line': 'URGENT: {{company}} affected by {{breach_name}} breach',
                    'email_body_html': '''
                    <div style="font-family: Arial, sans-serif; max-width: 600px;">
                        <div style="background: #ff0000; color: white; padding: 15px; text-align: center;">
                            <h2>🚨 URGENT SECURITY ALERT</h2>
                        </div>
                        
                        <div style="padding: 20px; background: #fff8f8; border-left: 5px solid #ff0000;">
                            <p>Hi {{first_name}},</p>
                            
                            <p><strong>We discovered that {{company}}'s data was exposed in the {{breach_name}} breach.</strong></p>
                            
                            <div style="background: white; padding: 15px; margin: 15px 0; border-radius: 5px;">
                                <h3>Breach Details:</h3>
                                <ul>
                                    <li><strong>Breach:</strong> {{breach_name}}</li>
                                    <li><strong>Year:</strong> {{breach_year}}</li>
                                    <li><strong>Records Affected:</strong> {{records_affected}}</li>
                                    <li><strong>Data Types:</strong> {{data_types}}</li>
                                    <li><strong>Risk Score:</strong> {{risk_score}}/10 ({{risk_level}})</li>
                                </ul>
                            </div>
                            
                            <div style="background: #fff; padding: 15px; margin: 15px 0; border-radius: 5px;">
                                <h3>Immediate Action Required:</h3>
                                <p>We're offering a <strong>complimentary emergency security assessment</strong> to help {{company}}:</p>
                                <ul>
                                    <li>Assess your current exposure</li>
                                    <li>Identify compromised data</li>
                                    <li>Implement protective measures</li>
                                    <li>Prevent future breaches</li>
                                </ul>
                            </div>
                            
                            <div style="text-align: center; margin: 25px 0;">
                                <a href="https://calendly.com/emergency-security" 
                                   style="background: #ff0000; color: white; padding: 15px 30px; 
                                          text-decoration: none; border-radius: 5px; font-weight: bold;">
                                    🚨 BOOK EMERGENCY ASSESSMENT
                                </a>
                            </div>
                            
                            <p>Time is critical - the longer exposed data remains unprotected, the higher your risk.</p>
                            
                            <p>Best regards,<br>
                            Emergency Response Team<br>
                            SalesBreachPro</p>
                        </div>
                    </div>
                    ''',
                    'email_body': 'URGENT: {{company}} affected by {{breach_name}} breach. {{records_affected}} records exposed including {{data_types}}. Risk Score: {{risk_score}}/10. Book emergency assessment: https://calendly.com/emergency-security',
                    'active': True
                },
                {
                    'name': 'Breach Follow-up - Day 2',
                    'template_type': 'breached',
                    'risk_level': 'high',
                    'sequence_step': 1,
                    'breach_template_type': 'breached',
                    'subject_line': 'Did you see our {{breach_name}} security alert for {{company}}?',
                    'email_body_html': '''
                    <div style="font-family: Arial, sans-serif; max-width: 600px;">
                        <p>Hi {{first_name}},</p>
                        
                        <p>I sent you an urgent security alert about {{company}}'s exposure in the <strong>{{breach_name}}</strong> breach, but I haven't heard back.</p>
                        
                        <div style="background: #fff8e1; padding: 15px; margin: 15px 0; border-left: 4px solid #ff9800;">
                            <h3>Why This Matters:</h3>
                            <ul>
                                <li>{{records_affected}} records were exposed</li>
                                <li>Data included: {{data_types}}</li>
                                <li>Your domain {{domain}} was affected</li>
                                <li>Risk level: {{risk_level}}</li>
                            </ul>
                        </div>
                        
                        <p>Many companies in {{industry}} don't realize the full impact until it's too late.</p>
                        
                        <p><strong>Free 15-minute assessment:</strong></p>
                        <ul>
                            <li>Check if your current data is secure</li>
                            <li>Identify potential vulnerabilities</li>
                            <li>Get actionable next steps</li>
                        </ul>
                        
                        <div style="text-align: center; margin: 20px 0;">
                            <a href="https://calendly.com/security-assessment" 
                               style="background: #ff9800; color: white; padding: 12px 25px; 
                                      text-decoration: none; border-radius: 5px;">
                                Schedule Free Assessment
                            </a>
                        </div>
                        
                        <p>Best regards,<br>
                        {{first_name}} - Security Specialist<br>
                        SalesBreachPro</p>
                    </div>
                    ''',
                    'email_body': 'Hi {{first_name}}, Following up on {{breach_name}} security alert for {{company}}. {{records_affected}} records exposed. Free assessment available: https://calendly.com/security-assessment',
                    'active': True
                }
            ]
            
            # Add templates to database
            added_count = 0
            for template_data in breach_templates:
                # Check if template already exists
                existing = EmailTemplate.query.filter_by(
                    name=template_data['name'],
                    template_type=template_data['template_type']
                ).first()
                
                if not existing:
                    template = EmailTemplate(**template_data)
                    db.session.add(template)
                    added_count += 1
                    print(f"[OK] Added: {template_data['name']}")
                else:
                    # Update existing template with breach data
                    for key, value in template_data.items():
                        setattr(existing, key, value)
                    print(f"[UPDATE] Updated: {template_data['name']}")
            
            db.session.commit()
            
            print(f"\n[SUCCESS] Added/Updated {len(breach_templates)} breach-aware templates!")
            print("These templates now use real FlawTrack data:")
            print("- {{breach_name}} - Name of the specific breach")
            print("- {{breach_year}} - Year the breach occurred") 
            print("- {{records_affected}} - Number of records compromised")
            print("- {{data_types}} - Types of data exposed")
            print("- {{risk_score}} - FlawTrack risk score (0-10)")
            print("- {{risk_level}} - HIGH/MEDIUM risk level")
            print("- {{domain}} - Contact's domain that was breached")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to add templates: {e}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    success = add_breach_templates()
    sys.exit(0 if success else 1)