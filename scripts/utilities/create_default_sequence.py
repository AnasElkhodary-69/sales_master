#!/usr/bin/env python3
"""
Create default email sequence configuration with steps
This is required for the email system to work
"""

from app import create_app
from models.database import db, EmailSequenceConfig, SequenceStep
from datetime import datetime

def create_default_sequence():
    """Create a default email sequence configuration"""
    
    app = create_app()
    
    with app.app_context():
        print("Creating default email sequence configuration...")
        print("=" * 50)
        
        # Check if we already have a sequence config
        existing = EmailSequenceConfig.query.first()
        if existing:
            print(f"Sequence config already exists: {existing.name}")
            return True
        
        # Create default sequence configuration
        default_config = EmailSequenceConfig(
            name="Default Email Sequence",
            description="Standard email sequence with follow-ups",
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        db.session.add(default_config)
        db.session.flush()  # Get the ID
        
        print(f"Created sequence config: {default_config.name} (ID: {default_config.id})")
        
        # Create sequence steps
        steps = [
            {
                'step_number': 0,
                'delay_days': 0,  # Send immediately
                'step_name': 'Initial contact email'
            },
            {
                'step_number': 1,
                'delay_days': 3,  # Wait 3 days
                'step_name': 'First follow-up'
            },
            {
                'step_number': 2,
                'delay_days': 7,  # Wait 7 days total
                'step_name': 'Second follow-up'
            },
            {
                'step_number': 3,
                'delay_days': 14,  # Wait 14 days total
                'step_name': 'Final follow-up'
            }
        ]
        
        for step_data in steps:
            step = SequenceStep(
                sequence_config_id=default_config.id,
                step_number=step_data['step_number'],
                delay_days=step_data['delay_days'],
                step_name=step_data['step_name'],
                is_active=True
            )
            db.session.add(step)
            print(f"  Added step {step.step_number}: {step.step_name} (delay: {step.delay_days} days)")
        
        # Update all campaigns to use this sequence config if they don't have one
        from models.database import Campaign
        campaigns_updated = 0
        campaigns = Campaign.query.filter_by(sequence_config_id=None).all()
        
        for campaign in campaigns:
            campaign.sequence_config_id = default_config.id
            campaigns_updated += 1
            print(f"  Updated campaign '{campaign.name}' to use default sequence")
        
        db.session.commit()
        
        print(f"\n[SUCCESS] Created default sequence with {len(steps)} steps")
        print(f"Updated {campaigns_updated} campaigns to use this sequence")
        print("\nSequence timeline:")
        print("  Day 0: Initial email")
        print("  Day 3: First follow-up")
        print("  Day 7: Second follow-up")
        print("  Day 14: Final follow-up")
        
        return True

if __name__ == "__main__":
    try:
        success = create_default_sequence()
        
        if success:
            print("\n[COMPLETE] Default sequence created successfully!")
            print("\nNow re-run the enrollment fix to schedule emails with the new sequence")
            
    except Exception as e:
        print(f"[ERROR] Error creating sequence: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")