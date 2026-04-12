#!/usr/bin/env python3
"""
Simple Gmail Test Script
Run this after sending yourself a test email to verify Gmail integration is working.

Usage:
    python test_gmail.py
"""

import sys
from gmail_watcher import GmailWatcher
from pathlib import Path

def test_gmail():
    print("=" * 60)
    print("GMAIL WATCHER TEST")
    print("=" * 60)

    # Initialize watcher
    watcher = GmailWatcher(vault_path='.')

    # Step 1: Authenticate
    print("\n[1] Authenticating with Gmail...")
    if not watcher.authenticate():
        print("ERROR: Gmail authentication failed!")
        return False

    print(f"SUCCESS: Connected to Gmail")

    # Step 2: Check for unread emails
    print("\n[2] Checking for unread emails...")
    items = watcher.check_for_updates()

    if not items:
        print("No new unread emails found")
        print("(Try sending yourself a test email first!)")
        return True

    print(f"Found {len(items)} new unread email(s)")

    # Step 3: Process each email
    print("\n[3] Processing emails...")
    for idx, item in enumerate(items, 1):
        msg_id = item['id']
        print(f"\n  Email {idx}/{len(items)}:")
        print(f"    ID: {msg_id}")

        # Create action file
        action_file = watcher.create_action_file(item)
        if action_file:
            print(f"    Action file: {action_file.name}")
            print(f"    Status: CREATED")
        else:
            print(f"    Status: FAILED")

    # Step 4: Summary
    print("\n[4] Summary:")
    print(f"    Total processed: {len(items)}")
    print(f"    Action files created: {len(items)}")
    print(f"    Location: Needs_Action/")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

    return True

if __name__ == "__main__":
    try:
        success = test_gmail()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
