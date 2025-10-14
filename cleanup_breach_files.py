#!/usr/bin/env python3
"""
Automated Cleanup Script: Remove Breach-Related Files
Run this AFTER database migration to remove all breach-scanning code

This script will:
1. Move breach-related files to a backup folder
2. Update app.py to remove breach imports
3. Create a summary of changes
"""

import os
import shutil
from datetime import datetime

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, 'refactoring_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S'))

# Files to remove
FILES_TO_REMOVE = [
    # Services
    'services/flawtrack_api.py',
    'services/flawtrack_monitor.py',
    'services/background_scanner.py',
    'services/simple_background_scanner.py',
    'services/breach_email_automation.py',
    'services/contact_upload_integration.py',

    # Routes
    'routes/breach_checker.py',
    'routes/flawtrack_admin.py',
    'routes/scan_progress.py',
    'routes/campaign_testing.py',

    # Tasks
    'tasks/domain_scanning.py',
    'tasks/__init__.py',

    # Templates
    'templates/breach_analysis.html',
    'templates/breach_checker.html',
    'templates/campaign_testing.html',

    # Scripts
    'scripts/tests/test_breach_scan.py',
    'scripts/utilities/add_breach_templates.py',

    # Optional: Celery (uncomment if you want to remove)
    # 'celery_app.py',
    # 'start_celery_worker.py',
]

# Optional files (keep validation services if desired)
OPTIONAL_FILES = [
    'services/zerobounce_validator.py',
    'services/emaillistverify_validator.py',
]


def create_backup_dir():
    """Create backup directory for removed files"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    print(f"Created backup directory: {BACKUP_DIR}")


def backup_and_remove_file(filepath):
    """Backup file to backup directory and remove from original location"""
    full_path = os.path.join(BASE_DIR, filepath)

    if not os.path.exists(full_path):
        print(f"  ⊘ {filepath} - doesn't exist")
        return False

    # Create backup subdirectory structure
    backup_path = os.path.join(BACKUP_DIR, filepath)
    backup_dir = os.path.dirname(backup_path)
    os.makedirs(backup_dir, exist_ok=True)

    # Move file to backup
    shutil.move(full_path, backup_path)
    print(f"  ✓ {filepath} - moved to backup")
    return True


def cleanup_files():
    """Remove all breach-related files"""
    print("\n" + "=" * 60)
    print("Removing Breach-Related Files")
    print("=" * 60)

    removed_count = 0

    for filepath in FILES_TO_REMOVE:
        if backup_and_remove_file(filepath):
            removed_count += 1

    print(f"\n✓ Removed {removed_count} files")
    return removed_count


def prompt_optional_files():
    """Ask about optional files (validation services)"""
    print("\n" + "=" * 60)
    print("Optional Files")
    print("=" * 60)
    print("\nThe following files are email validation services:")
    for filepath in OPTIONAL_FILES:
        print(f"  - {filepath}")

    response = input("\nDo you want to keep email validation services? (yes/no): ")

    if response.lower() not in ['yes', 'y']:
        print("\nRemoving validation services...")
        for filepath in OPTIONAL_FILES:
            backup_and_remove_file(filepath)
    else:
        print("\nKeeping validation services...")


def update_app_py():
    """Update app.py to remove breach-related imports"""
    print("\n" + "=" * 60)
    print("Updating app.py")
    print("=" * 60)

    app_file = os.path.join(BASE_DIR, 'app.py')

    if not os.path.exists(app_file):
        print("  ⚠ app.py not found")
        return

    # Backup original
    backup_path = os.path.join(BACKUP_DIR, 'app.py.backup')
    shutil.copy2(app_file, backup_path)

    with open(app_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove breach-related imports
    imports_to_remove = [
        'from routes.breach_checker import breach_checker_bp',
        'from routes.flawtrack_admin import flawtrack_admin_bp',
        'from routes.scan_progress import scan_progress_bp',
        'from routes.campaign_testing import campaign_testing_bp',
    ]

    # Remove blueprint registrations
    blueprints_to_remove = [
        'app.register_blueprint(breach_checker_bp)',
        'app.register_blueprint(flawtrack_admin_bp)',
        'app.register_blueprint(scan_progress_bp)',
        'app.register_blueprint(campaign_testing_bp)',
    ]

    # Update imports in database
    content = content.replace(
        'from models.database import (\n    db, Contact, Campaign, TemplateVariant, Breach, Email',
        'from models.database import (\n    db, Contact, Campaign, TemplateVariant, Email'
    )

    # Remove breach-related lines
    lines = content.split('\n')
    new_lines = []
    skip_flawtrack_block = False

    for line in lines:
        # Skip import lines
        if any(imp in line for imp in imports_to_remove):
            print(f"  ✓ Removed import: {line.strip()}")
            continue

        # Skip blueprint registration
        if any(bp in line for bp in blueprints_to_remove):
            print(f"  ✓ Removed blueprint: {line.strip()}")
            continue

        # Skip FlawTrack monitoring block
        if 'from services.flawtrack_monitor import start_monitoring' in line:
            skip_flawtrack_block = True
            print(f"  ✓ Removing FlawTrack monitoring block...")
            continue

        if skip_flawtrack_block:
            if 'except Exception as e:' in line and 'FlawTrack' in content[content.index(line):content.index(line)+200]:
                continue
            elif line.strip().startswith('print("') and 'FlawTrack' in line:
                continue
            elif line.strip() == '' and skip_flawtrack_block:
                skip_flawtrack_block = False
                continue

        new_lines.append(line)

    # Write updated content
    with open(app_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    print(f"  ✓ app.py updated")


def create_summary():
    """Create summary document"""
    summary_file = os.path.join(BACKUP_DIR, 'CLEANUP_SUMMARY.txt')

    with open(summary_file, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("Breach Features Cleanup Summary\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("Removed Files:\n")
        f.write("-" * 60 + "\n")
        for filepath in FILES_TO_REMOVE:
            full_path = os.path.join(BASE_DIR, filepath)
            if os.path.exists(os.path.join(BACKUP_DIR, filepath)):
                f.write(f"✓ {filepath}\n")

        f.write("\n\nBackup Location:\n")
        f.write(f"{BACKUP_DIR}\n")

        f.write("\n\nNext Steps:\n")
        f.write("-" * 60 + "\n")
        f.write("1. Replace models/database.py with models/database_new.py\n")
        f.write("2. Update services/scheduler.py (remove scanning jobs)\n")
        f.write("3. Update services/auto_enrollment.py (use industry filtering)\n")
        f.write("4. Update services/email_sequence_service.py (remove breach checking)\n")
        f.write("5. Update services/email_processor.py (remove breach variables)\n")
        f.write("6. Update routes/contacts.py (remove breach routes)\n")
        f.write("7. Update routes/campaigns.py (update targeting)\n")
        f.write("8. Update routes/templates.py (update variables)\n")
        f.write("9. Update routes/dashboard.py (update stats)\n")
        f.write("10. Update routes/api.py (remove breach endpoints)\n")
        f.write("11. Update all frontend templates\n")
        f.write("12. Test the application\n\n")

        f.write("See REFACTORING_GUIDE.md for detailed instructions.\n")

    print(f"\n✓ Summary created: {summary_file}")


def main():
    """Main cleanup function"""
    print("\n" + "=" * 60)
    print("AUTOMATED BREACH FEATURES CLEANUP")
    print("=" * 60)
    print("\nThis script will:")
    print("  1. Move breach-related files to backup folder")
    print("  2. Update app.py to remove breach imports")
    print("  3. Create a cleanup summary")
    print("\nFiles will be backed up to:", BACKUP_DIR)
    print("\n" + "=" * 60)

    response = input("\nContinue with cleanup? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cleanup cancelled.")
        return

    try:
        # Create backup directory
        create_backup_dir()

        # Remove files
        cleanup_files()

        # Ask about optional files
        prompt_optional_files()

        # Update app.py
        update_app_py()

        # Create summary
        create_summary()

        print("\n" + "=" * 60)
        print("CLEANUP COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"\nBackup location: {BACKUP_DIR}")
        print("\nNext steps:")
        print("  1. Review REFACTORING_GUIDE.md")
        print("  2. Replace models/database.py with models/database_new.py")
        print("  3. Update remaining files per guide")
        print("  4. Update frontend templates")
        print("  5. Test the application")
        print("\n" + "=" * 60 + "\n")

    except Exception as e:
        print(f"\n\nERROR during cleanup: {e}")
        print(f"Files are backed up in: {BACKUP_DIR}")
        print("You can restore them manually if needed.")
        raise


if __name__ == "__main__":
    main()
