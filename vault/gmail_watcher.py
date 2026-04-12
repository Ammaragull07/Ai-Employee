"""
gmail_watcher.py - Gmail Watcher for AI Employee Silver Tier

Monitors Gmail inbox for unread/important emails and creates action files
in the Obsidian vault's Needs_Action folder for Claude to process.

SETUP (run once):
    python gmail_watcher.py --setup

USAGE:
    python gmail_watcher.py                    # Continuous monitoring
    python gmail_watcher.py --once             # Single check and exit
    python gmail_watcher.py --interval 60      # Check every 60 seconds
"""

import time
import logging
import json
import base64
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Missing Google API libraries. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)


# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
]

def _find_credentials_file() -> Path:
    """
    Find credentials.json by checking multiple locations:
    1. Same directory as this script (vault/)
    2. Parent directory (Ai-Employee/ repo root)
    3. Current working directory
    """
    candidates = [
        Path(__file__).parent / 'credentials.json',         # vault/credentials.json
        Path(__file__).parent.parent / 'credentials.json',  # Ai-Employee/credentials.json (repo root)
        Path('credentials.json'),                            # wherever the script is run from
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[1]  # Default to repo root


CREDENTIALS_FILE = str(_find_credentials_file())
TOKEN_FILE = 'token.json'


class GmailWatcher:
    """
    Monitors Gmail for unread important emails and writes action files
    into the vault's Needs_Action folder for Claude to process.
    """

    def __init__(self, vault_path: str, credentials_path: str = None, check_interval: int = 120):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / 'Needs_Action'
        self.check_interval = check_interval
        self.processed_ids: set = set()

        # Credentials and token paths
        self.credentials_path = Path(credentials_path or CREDENTIALS_FILE)
        # Store token.json next to credentials.json (repo root, not vault)
        self.token_path = self.credentials_path.parent / TOKEN_FILE

        # Create necessary vault directories
        self.needs_action.mkdir(parents=True, exist_ok=True)
        (self.vault_path / 'Logs').mkdir(exist_ok=True)

        self._setup_logging()
        self._load_state()
        self._service = None

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.vault_path / 'Logs' / 'gmail_watcher.log',
                                    encoding='utf-8'),
                logging.StreamHandler(stream=open(sys.stdout.fileno(), 'w',
                                                   encoding='utf-8', closefd=False))
            ]
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    def _load_state(self):
        """Load previously processed email IDs to avoid duplicates across restarts."""
        state_file = self.vault_path / 'Logs' / 'gmail_processed.json'
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    self.processed_ids = set(json.load(f))
                self.logger.info(f"Loaded {len(self.processed_ids)} previously processed email IDs")
            except Exception as e:
                self.logger.warning(f"Could not load state file: {e}")
                self.processed_ids = set()

    def _save_state(self):
        """Persist processed email IDs (keep last 2000 to prevent unbounded growth)."""
        state_file = self.vault_path / 'Logs' / 'gmail_processed.json'
        try:
            ids_list = list(self.processed_ids)[-2000:]
            with open(state_file, 'w') as f:
                json.dump(ids_list, f)
        except Exception as e:
            self.logger.warning(f"Could not save state file: {e}")

    def authenticate(self) -> bool:
        """
        Authenticate with Gmail API using OAuth2.
        On first run, opens a browser window for authorization.
        Subsequent runs use the saved token.json.
        """
        creds = None

        # Try to load existing token
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
                self.logger.info("Loaded existing Gmail token")
            except Exception as e:
                self.logger.warning(f"Could not load existing token: {e}")
                creds = None

        # Refresh expired token or run new OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.info("Gmail token refreshed")
                except Exception as e:
                    self.logger.warning(f"Token refresh failed ({e}), re-authorizing...")
                    creds = None

            if not creds:
                if not self.credentials_path.exists():
                    self.logger.error(f"credentials.json not found at: {self.credentials_path.absolute()}")
                    self.logger.error("Please ensure credentials.json is in the vault directory.")
                    return False

                try:
                    self.logger.info("Opening browser for Gmail authorization...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    self.logger.info("Gmail authorization completed successfully")
                except Exception as e:
                    self.logger.error(f"OAuth2 authorization failed: {e}")
                    return False

            # Save token for future use
            try:
                with open(self.token_path, 'w') as f:
                    f.write(creds.to_json())
                self.logger.info(f"Token saved to {self.token_path}")
            except Exception as e:
                self.logger.warning(f"Could not save token: {e}")

        # Build and test the Gmail service
        try:
            self._service = build('gmail', 'v1', credentials=creds)
            profile = self._service.users().getProfile(userId='me').execute()
            self.logger.info(f"Gmail connected as: {profile.get('emailAddress')}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to build Gmail service: {e}")
            return False

    @property
    def service(self):
        if self._service is None:
            if not self.authenticate():
                raise RuntimeError("Gmail authentication failed. Run with --setup first.")
        return self._service

    def check_for_updates(self) -> List[Dict]:
        """
        Query Gmail for new unread emails in inbox (excluding promotions/social).
        Returns list of new message stubs (id + threadId only).
        """
        try:
            query = 'is:unread (label:inbox OR is:important) -label:promotions -label:social -label:forums'
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=25
            ).execute()

            all_messages = results.get('messages', [])
            new_messages = [m for m in all_messages if m['id'] not in self.processed_ids]

            if all_messages:
                self.logger.info(f"Gmail: {len(all_messages)} unread, {len(new_messages)} new to process")
            else:
                self.logger.info("Gmail: No new unread emails")

            return new_messages

        except HttpError as e:
            self.logger.error(f"Gmail API HTTP error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error querying Gmail: {e}")
            return []

    def _decode_body(self, data: str) -> str:
        """Decode a base64url-encoded email body part."""
        try:
            return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace')
        except Exception:
            return '[Could not decode email body]'

    def _extract_body(self, msg_data: Dict) -> str:
        """
        Extract plain-text body from email payload.
        Handles simple messages, multipart/alternative, and nested multipart.
        """
        payload = msg_data.get('payload', {})
        mime_type = payload.get('mimeType', '')

        # Simple plain-text message
        if mime_type == 'text/plain':
            data = payload.get('body', {}).get('data', '')
            if data:
                return self._decode_body(data)[:3000]

        # Walk the parts tree looking for text/plain
        def find_text_plain(parts):
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        return self._decode_body(data)[:3000]
                # Recurse into nested parts
                sub = part.get('parts', [])
                if sub:
                    result = find_text_plain(sub)
                    if result:
                        return result
            return None

        parts = payload.get('parts', [])
        text = find_text_plain(parts)
        if text:
            return text

        # Fall back to the Gmail snippet
        return msg_data.get('snippet', '[No readable body found]')

    def create_action_file(self, message: Dict) -> Optional[Path]:
        """
        Fetch full email data and write a markdown action file to Needs_Action/.
        """
        msg_id = message['id']
        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()

            # Parse headers into a dict
            headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}

            sender = headers.get('From', 'Unknown Sender')
            subject = headers.get('Subject', '(No Subject)')
            date = headers.get('Date', datetime.now().isoformat())
            reply_to = headers.get('Reply-To', sender)
            message_id_header = headers.get('Message-ID', '')

            # Priority based on Gmail labels
            labels = msg.get('labelIds', [])
            priority = 'high' if 'IMPORTANT' in labels else 'medium'

            body = self._extract_body(msg)

            # Sanitise subject for use in filename
            safe_subject = re.sub(r'[<>:"/\\|?*\n\r]', '', subject)[:40].strip()

            content = f"""---
type: email
source: gmail
gmail_id: {msg_id}
from: {sender}
reply_to: {reply_to}
subject: {subject}
received: {date}
processed_at: {datetime.now().isoformat()}
priority: {priority}
status: pending
labels: {', '.join(labels)}
---

# Email: {subject}

**From:** {sender}
**Received:** {date}
**Priority:** {priority}

---

## Message Body

{body}

---

## Suggested Actions
- [ ] Read and understand the email
- [ ] Draft a reply if needed (create a Pending_Approval request first)
- [ ] Forward to relevant party if required
- [ ] Archive after processing
- [ ] Update Dashboard.md with any key information

## Quick Reply Template
To reply, create `/Pending_Approval/EMAIL_REPLY_{msg_id[:8]}.md` with:
```
action: send_email
to: {reply_to}
subject: Re: {subject}
```
"""

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"EMAIL_{timestamp}_{msg_id[:8]}.md"
            filepath = self.needs_action / filename
            filepath.write_text(content, encoding='utf-8')

            # Mark as read so we don't pick it up again on the next cycle
            try:
                self.service.users().messages().modify(
                    userId='me',
                    id=msg_id,
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
            except Exception as e:
                self.logger.warning(f"Could not mark email as read: {e}")

            self.processed_ids.add(msg_id)
            self._save_state()

            self.logger.info(f"Action file created: {filename}  |  From: {sender}  |  Subject: {subject}")
            return filepath

        except HttpError as e:
            self.logger.error(f"Gmail API error for message {msg_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error processing message {msg_id}: {e}")
            return None

    def run(self):
        """Continuously monitor Gmail and create action files."""
        self.logger.info(f"Gmail Watcher starting (interval: {self.check_interval}s)")

        if not self.authenticate():
            self.logger.error("Authentication failed. Run: python gmail_watcher.py --setup")
            sys.exit(1)

        self.logger.info("Monitoring Gmail. Press Ctrl+C to stop.")

        while True:
            try:
                messages = self.check_for_updates()
                for msg in messages:
                    self.create_action_file(msg)
                    time.sleep(0.5)  # Avoid hitting rate limits
            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")

            time.sleep(self.check_interval)


def setup_gmail_auth(credentials_path: str = CREDENTIALS_FILE):
    """
    Interactive one-time Gmail OAuth2 setup.
    Opens a browser window — complete the authorization there.
    """
    print("=" * 50)
    print("  Gmail OAuth2 Authorization Setup")
    print("=" * 50)

    creds_path = Path(credentials_path)
    if not creds_path.exists():
        print(f"\nERROR: credentials.json not found at: {creds_path.absolute()}")
        print("Please place credentials.json in this directory and try again.")
        return False

    print(f"\nUsing credentials: {creds_path.absolute()}")
    print("Opening browser for authorization...\n")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
        creds = flow.run_local_server(port=0)

        token_path = creds_path.parent / TOKEN_FILE
        with open(token_path, 'w') as f:
            f.write(creds.to_json())

        # Verify connection
        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()

        print(f"\n[OK] Authorization successful!")
        print(f"[OK] Connected as: {profile.get('emailAddress')}")
        print(f"[OK] Token saved to: {token_path.absolute()}")
        print(f"\nYou can now run:  python gmail_watcher.py")
        return True

    except Exception as e:
        print(f"\nERROR: Authorization failed: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Gmail Watcher for AI Employee Silver Tier')
    parser.add_argument('--setup', action='store_true',
                        help='Run one-time OAuth2 authorization (opens browser)')
    parser.add_argument('--vault', default='.',
                        help='Path to Obsidian vault directory (default: current directory)')
    parser.add_argument('--credentials', default=CREDENTIALS_FILE,
                        help=f'Path to credentials.json (default: {CREDENTIALS_FILE})')
    parser.add_argument('--interval', type=int, default=120,
                        help='Check interval in seconds (default: 120)')
    parser.add_argument('--once', action='store_true',
                        help='Run a single check cycle and exit')
    args = parser.parse_args()

    if args.setup:
        success = setup_gmail_auth(args.credentials)
        sys.exit(0 if success else 1)

    watcher = GmailWatcher(
        vault_path=args.vault,
        credentials_path=args.credentials,
        check_interval=args.interval
    )

    if args.once:
        if not watcher.authenticate():
            print("Authentication failed. Run with --setup to authorize Gmail access.")
            sys.exit(1)
        messages = watcher.check_for_updates()
        processed = 0
        for msg in messages:
            if watcher.create_action_file(msg):
                processed += 1
        print(f"Done. Created {processed} action file(s) from {len(messages)} new email(s).")
    else:
        print(f"Gmail Watcher")
        print(f"Vault  : {Path(args.vault).absolute()}")
        print(f"Creds  : {Path(args.credentials).absolute()}")
        print(f"Interval: {args.interval}s")
        print("Press Ctrl+C to stop.\n")
        try:
            watcher.run()
        except KeyboardInterrupt:
            print("\nGmail Watcher stopped.")


if __name__ == "__main__":
    main()
