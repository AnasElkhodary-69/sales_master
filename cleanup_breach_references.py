"""
Cleanup script to remove critical breach-related code references
Focuses on code that will cause AttributeError when accessing non-existent database fields
"""
import re
import os

def cleanup_file(filepath, replacements):
    """Apply regex replacements to a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        changes_made = []

        for pattern, replacement, description in replacements:
            new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            if new_content != content:
                changes_made.append(description)
                content = new_content

        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[OK] {filepath}")
            for change in changes_made:
                print(f"  - {change}")
            return True
        else:
            print(f"  {filepath} - No changes needed")
            return False

    except Exception as e:
        print(f"[ERROR] Error processing {filepath}: {e}")
        return False

# Define critical replacements for routes/campaigns.py
campaigns_replacements = [
    # Replace Contact.breach_status queries with safe alternatives
    (r"Contact\.query\.filter\(Contact\.breach_status == 'breached'\)\.count\(\)",
     "0  # breach_status field removed",
     "Remove breach_status queries"),

    (r"Contact\.query\.filter\(Contact\.breach_status == 'not_breached'\)\.count\(\)",
     "0  # breach_status field removed",
     "Remove not_breached queries"),

    (r"Contact\.query\.filter\(\s*\(Contact\.breach_status == 'unknown'\) \| \(Contact\.breach_status\.is_\(None\)\)\s*\)\.count\(\)",
     "Contact.query.count()  # Show all contacts",
     "Remove unknown status queries"),

    # Replace breach_status in contact data
    (r"'breach_status': contact\.breach_status or 'unknown'",
     "'industry': contact.industry or 'Unknown'",
     "Replace breach_status with industry"),

    # Replace risk_score references
    (r"contact\.risk_score or 0",
     "0  # risk_score field removed",
     "Remove risk_score references"),

    # Replace auto_enroll_breach_status
    (r"auto_enroll_breach_status = request\.form\.get\('auto_enroll_breach_status'\) if auto_enroll else None",
     "# auto_enroll_breach_status removed - now uses industry targeting",
     "Remove auto_enroll_breach_status"),

    (r"auto_enroll_breach_status=auto_enroll_breach_status",
     "# Breach-based enrollment removed",
     "Remove breach enrollment parameter"),

    (r"campaign\.auto_enroll_breach_status = request\.form\.get\('auto_enroll_breach_status'\) if campaign\.auto_enroll else None",
     "# auto_enroll_breach_status removed",
     "Remove breach status assignment"),

    (r"auto_enroll_breach_status=original_campaign\.auto_enroll_breach_status",
     "# Breach targeting removed",
     "Remove breach status from duplicate"),

    # Replace template.risk_level references
    (r"template\.risk_level",
     "template.category",
     "Replace risk_level with category"),

    (r"template\.breach_template_type",
     "template.template_type",
     "Replace breach_template_type with template_type"),
]

print("=" * 60)
print("CRITICAL BREACH REFERENCE CLEANUP")
print("=" * 60)
print()

# Clean routes/campaigns.py
print("Cleaning routes/campaigns.py...")
cleanup_file("routes/campaigns.py", campaigns_replacements)

print()
print("=" * 60)
print("Cleanup complete!")
print("=" * 60)
print("\nNext steps:")
print("1. Review the changes made")
print("2. Test the application")
print("3. Additional service files may need manual cleanup")
