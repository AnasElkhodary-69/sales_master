#!/usr/bin/env python3
"""
Manual reply detection check - shows recent emails in inbox
"""
import imaplib
import email
import os
import sys
from datetime import datetime, timedelta
from email.header import decode_header
from dotenv import load_dotenv

def decode_header_value(header_value):
    """Decode email header value"""
    try:
        decoded_parts = decode_header(header_value)
        decoded_string = ''

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or 'utf-8')
            else:
                decoded_string += part

        return decoded_string
    except Exception:
        return header_value

def extract_email_address(from_header):
    """Extract email address from From header"""
    import re
    try:
        email_pattern = r'<([^>]+)>|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        match = re.search(email_pattern, from_header)

        if match:
            return match.group(1) or match.group(2)

        return from_header.strip()
    except Exception:
        return ''

def main():
    # Load environment variables
    load_dotenv()

    email_address = os.getenv('REPLY_DETECTION_EMAIL', '')
    email_password = os.getenv('REPLY_DETECTION_PASSWORD', '')
    imap_server = os.getenv('REPLY_DETECTION_IMAP_SERVER', 'imap.gmail.com')

    print(f"Checking for replies in: {email_address}")
    print()

    if not email_address or not email_password:
        print("[ERROR] Email credentials not configured!")
        sys.exit(1)

    try:
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_address, email_password)
        mail.select('INBOX')

        # Search for emails from the last 24 hours
        since_date = (datetime.now() - timedelta(hours=24)).strftime("%d-%b-%Y")
        search_criteria = f'(SINCE {since_date})'

        # Get email IDs
        status, email_ids = mail.search(None, search_criteria)

        if status == 'OK':
            email_list = email_ids[0].split()
            print(f"Found {len(email_list)} emails in the last 24 hours\n")
            print("=" * 80)

            # Show last 10 emails
            for email_id in email_list[-10:]:
                try:
                    status, email_data = mail.fetch(email_id, '(RFC822)')

                    if status == 'OK':
                        raw_email = email_data[0][1]
                        parsed_email = email.message_from_bytes(raw_email)

                        # Extract details
                        from_header = parsed_email.get('From', '')
                        sender_email = extract_email_address(from_header)
                        subject = decode_header_value(parsed_email.get('Subject', ''))
                        date = parsed_email.get('Date', '')
                        in_reply_to = parsed_email.get('In-Reply-To', '')

                        print(f"\nEmail ID: {email_id.decode()}")
                        print(f"From: {sender_email}")
                        print(f"Subject: {subject}")
                        print(f"Date: {date}")
                        if in_reply_to:
                            print(f"In-Reply-To: {in_reply_to}")
                        print("-" * 80)

                except Exception as e:
                    print(f"Error processing email {email_id}: {e}")

        mail.logout()

    except Exception as e:
        print(f"[ERROR] Failed to check for replies: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
