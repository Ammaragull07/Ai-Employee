"""
email_responder.py - AI Email Response Generator

Analyzes incoming emails using Claude API and generates intelligent responses.
Auto-sends replies and logs them for review.

USAGE:
    python -c "from email_responder import EmailResponder; EmailResponder().respond_to_email('EMAIL_...md')"
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import json
import re

try:
    from anthropic import Anthropic
except ImportError:
    print("Missing 'anthropic'. Run: pip install anthropic")
    exit(1)

try:
    from api_config import ANTHROPIC_API_KEY, CLAUDE_MODEL, MAX_TOKENS
except ImportError:
    print("Missing 'api_config.py'. Please create it with your API key.")
    exit(1)


class EmailResponder:
    """
    Uses Claude AI to analyze emails and generate intelligent responses.
    Auto-sends via Gmail API.
    """

    def __init__(self, vault_path: str = '.'):
        self.vault_path = Path(vault_path)
        self.logs_path = self.vault_path / 'Logs'
        self.logs_path.mkdir(exist_ok=True)

        self._setup_logging()

        # Claude API client (using API key from environment variables)
        if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your_api_key_here":
            self.logger.error("ANTHROPIC_API_KEY not configured in environment")
            raise ValueError("Please set ANTHROPIC_API_KEY in your .env file or as an environment variable")

        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = CLAUDE_MODEL
        self.max_tokens = MAX_TOKENS

        # Gmail service (imported lazily)
        self._gmail_service = None

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.logs_path / 'email_responder.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def gmail_service(self):
        """Lazy-load Gmail service."""
        if self._gmail_service is None:
            from gmail_watcher import GmailWatcher
            watcher = GmailWatcher(str(self.vault_path))
            if watcher.authenticate():
                self._gmail_service = watcher.service
            else:
                raise RuntimeError("Gmail authentication failed")
        return self._gmail_service

    def should_respond(self, email_data: Dict) -> bool:
        """
        Determine if the email should get an AI response.
        Skip: notifications, auto-replies, marketing, system emails
        """
        sender = email_data.get('from', '').lower()
        subject = email_data.get('subject', '').lower()

        # Skip auto-replies and notifications
        skip_keywords = [
            'noreply', 'no-reply', 'do-not-reply',
            'notification', 'alert', 'digest',
            'unsubscribe', 'automated', 'auto-reply',
            'linkedin', 'facebook', 'twitter', 'instagram',
            'google', 'amazon', 'ebay',
            'promocode', 'discount', 'offer', 'sale',
        ]

        for keyword in skip_keywords:
            if keyword in sender or keyword in subject:
                return False

        return True

    def extract_email_content(self, email_file: Path) -> Dict:
        """Extract email data from action file."""
        try:
            content = email_file.read_text(encoding='utf-8')

            # Parse YAML frontmatter
            lines = content.split('\n')
            from_match = re.search(r'^from:\s*(.+)$', content, re.MULTILINE)
            subject_match = re.search(r'^subject:\s*(.+)$', content, re.MULTILINE)

            # Extract body (after ## Message Body)
            body_match = re.search(r'## Message Body\n+(.+?)(?:\n---|\Z)', content, re.DOTALL)

            return {
                'from': from_match.group(1).strip() if from_match else 'Unknown',
                'subject': subject_match.group(1).strip() if subject_match else 'No Subject',
                'body': body_match.group(1).strip() if body_match else '',
                'original_file': email_file.name,
            }
        except Exception as e:
            self.logger.error(f"Error extracting email content: {e}")
            return {}

    def generate_response(self, email_data: Dict) -> Optional[str]:
        """
        Use Claude to generate an intelligent email response.
        """
        try:
            prompt = f"""You are an AI assistant helping Ammara respond to emails.
Analyze this email and generate a professional, friendly response.

FROM: {email_data['from']}
SUBJECT: {email_data['subject']}

EMAIL BODY:
{email_data['body']}

---

Generate a concise, professional response. Be friendly but brief (2-3 sentences max).
Only return the response text, no subject line needed."""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = message.content[0].text.strip()
            self.logger.info(f"Response generated for: {email_data['subject']}")
            return response_text

        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return None

    def send_response(self, email_data: Dict, response_text: str) -> bool:
        """
        Send the generated response via Gmail.
        """
        try:
            from email.mime.text import MIMEText
            import base64

            # Extract recipient email
            from_field = email_data['from']
            recipient = self._extract_email(from_field)

            if not recipient:
                self.logger.error(f"Could not extract email address from: {from_field}")
                return False

            # Get sender's email address from Gmail profile
            try:
                profile = self.gmail_service.users().getProfile(userId='me').execute()
                sender_email = profile.get('emailAddress', 'me')
            except Exception as e:
                self.logger.warning(f"Could not get sender email from profile: {e}, using 'me'")
                sender_email = 'me'

            # Create reply subject
            original_subject = email_data['subject']
            if not original_subject.startswith('Re:'):
                reply_subject = f"Re: {original_subject}"
            else:
                reply_subject = original_subject

            # Create message with all required headers
            message = MIMEText(response_text)
            message['from'] = sender_email
            message['to'] = recipient
            message['subject'] = reply_subject

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

            # Send via Gmail API
            send_message = {
                'raw': raw_message
            }

            self.gmail_service.users().messages().send(
                userId='me',
                body=send_message
            ).execute()

            self.logger.info(f"Response sent to: {recipient}")
            return True

        except Exception as e:
            self.logger.error(f"Error sending response: {e}")
            return False

    def log_response(self, email_data: Dict, response_text: str, sent: bool):
        """Log the response to Sent_Responses/ folder."""
        try:
            sent_dir = self.vault_path / 'Sent_Responses'
            sent_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            recipient = self._extract_email(email_data['from'])

            log_content = f"""---
sent_at: {datetime.now().isoformat()}
to: {recipient}
subject: Re: {email_data['subject']}
status: {'sent' if sent else 'failed'}
source_email: {email_data['original_file']}
---

# Auto-Response Sent

**To:** {email_data['from']}
**Subject:** Re: {email_data['subject']}
**Sent:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Generated Response

{response_text}

---

## Original Email

**From:** {email_data['from']}
**Subject:** {email_data['subject']}

{email_data['body']}
"""

            filename = f"RESPONSE_{timestamp}_{recipient.split('@')[0]}.md"
            filepath = sent_dir / filename
            filepath.write_text(log_content, encoding='utf-8')

            self.logger.info(f"Response logged: {filename}")
            return filepath

        except Exception as e:
            self.logger.error(f"Error logging response: {e}")
            return None

    def respond_to_email(self, email_file_name: str) -> bool:
        """
        Main entry point: analyze email and send response.
        """
        email_file = self.vault_path / 'Needs_Action' / email_file_name

        if not email_file.exists():
            self.logger.error(f"Email file not found: {email_file_name}")
            return False

        self.logger.info(f"Processing: {email_file_name}")

        # Extract email data
        email_data = self.extract_email_content(email_file)
        if not email_data:
            return False

        # Check if we should respond
        if not self.should_respond(email_data):
            self.logger.info(f"Skipping (auto-reply/notification): {email_data['subject']}")
            return False

        # Generate response
        response_text = self.generate_response(email_data)
        if not response_text:
            return False

        # Send response
        sent = self.send_response(email_data, response_text)

        # Log response
        self.log_response(email_data, response_text, sent)

        if sent:
            self.logger.info(f"SUCCESS: Response sent to {self._extract_email(email_data['from'])}")
        else:
            self.logger.warning(f"FAILED: Could not send response")

        return sent

    @staticmethod
    def _extract_email(email_string: str) -> str:
        """Extract email address from 'Name <email@domain.com>' format."""
        match = re.search(r'<(.+?)>', email_string)
        if match:
            return match.group(1)
        return email_string.strip()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python email_responder.py EMAIL_FILE_NAME.md")
        print("Example: python email_responder.py EMAIL_20260412_150602_19d80c98.md")
        sys.exit(1)

    responder = EmailResponder()
    success = responder.respond_to_email(sys.argv[1])
    sys.exit(0 if success else 1)
