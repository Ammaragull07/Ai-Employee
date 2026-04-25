#!/usr/bin/env python3
"""
Test script to verify AI Employee can send emails to recipients.
Tests the complete email sending pipeline.

USAGE:
    python test_email_sending.py --to your-email@example.com [--subject "Test"] [--body "Test message"]
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

def test_email_responder(to_email: str, subject: str = "Test Email", body: str = "Hello from AI Employee"):
    """Test sending via email_responder.py"""
    print("\n" + "=" * 60)
    print("TEST 1: Email Responder (Auto-Reply)")
    print("=" * 60)

    try:
        from email_responder import EmailResponder

        responder = EmailResponder('.')

        # Simulate received email data
        email_data = {
            'from': f'Test Sender <test@example.com>',
            'subject': subject,
            'body': body,
            'original_file': 'TEST_EMAIL.md'
        }

        # Generate a test response
        test_response = "Thank you for your email. This is an automated test response from AI Employee."

        # Attempt to send
        print(f"\nSending test response to: {to_email}")
        success = responder.send_response(email_data, test_response)

        if success:
            print("✅ SUCCESS: Email sent via email_responder!")
            return True
        else:
            print("❌ FAILED: Email responder returned False")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_email_mcp_server(to_email: str, subject: str = "Test Email", body: str = "Hello from AI Employee"):
    """Test sending via email_mcp_server.py"""
    print("\n" + "=" * 60)
    print("TEST 2: Email MCP Server")
    print("=" * 60)

    try:
        from email_mcp_server import EmailMCPServer

        server = EmailMCPServer()

        params = {
            'to': to_email,
            'subject': subject,
            'body': body
        }

        print(f"\nSending email to: {to_email}")
        result = server.send_email(params)

        if result.get('success'):
            print(f"✅ SUCCESS: {result.get('message')}")
            return True
        else:
            print(f"❌ FAILED: {result.get('error')}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_orchestrator(to_email: str, subject: str = "Test Email", body: str = "Hello from AI Employee"):
    """Test sending via orchestrator.py"""
    print("\n" + "=" * 60)
    print("TEST 3: Orchestrator")
    print("=" * 60)

    try:
        from orchestrator import Orchestrator

        orch = Orchestrator('.')

        print(f"\nSending email to: {to_email}")
        success = orch._send_gmail(to=to_email, subject=subject, body=body)

        if success:
            print("✅ SUCCESS: Email sent via orchestrator!")
            return True
        else:
            print("❌ FAILED: Orchestrator returned False")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_sent_emails():
    """Check what emails have been sent"""
    print("\n" + "=" * 60)
    print("SENT EMAILS LOG")
    print("=" * 60)

    sent_dir = Path('Sent_Emails')
    if not sent_dir.exists():
        print("No Sent_Emails folder found")
        return

    files = list(sent_dir.glob('*.md'))
    if not files:
        print("No sent emails logged yet")
        return

    print(f"\nFound {len(files)} sent email(s):\n")
    for file in sorted(files, reverse=True)[:10]:
        print(f"  📧 {file.name}")
        content = file.read_text()
        # Extract to and subject from frontmatter
        for line in content.split('\n')[:10]:
            if line.startswith('to:') or line.startswith('subject:'):
                print(f"     {line}")


def main():
    parser = argparse.ArgumentParser(description='Test AI Employee email sending')
    parser.add_argument('--to', required=True, help='Recipient email address')
    parser.add_argument('--subject', default='AI Employee Test', help='Email subject')
    parser.add_argument('--body', default='This is a test email from AI Employee system.', help='Email body')

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("AI EMPLOYEE - EMAIL SENDING VERIFICATION TEST")
    print("=" * 60)
    print(f"Recipient: {args.to}")
    print(f"Subject: {args.subject}")
    print(f"Body: {args.body[:50]}...")

    results = []

    # Test 1: Email Responder
    results.append(("Email Responder", test_email_responder(args.to, args.subject, args.body)))

    # Test 2: Email MCP Server
    results.append(("Email MCP Server", test_email_mcp_server(args.to, args.subject, args.body)))

    # Test 3: Orchestrator
    results.append(("Orchestrator", test_orchestrator(args.to, args.subject, args.body)))

    # Check sent emails log
    check_sent_emails()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ ALL TESTS PASSED - Emails are being sent correctly!")
        return 0
    else:
        print("\n⚠️  Some tests failed - check errors above")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
