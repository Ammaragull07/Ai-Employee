"""
email_mcp_server.py - Gmail MCP Server for AI Employee Silver Tier

Provides three tools to Claude Code:
  • send_email   – Actually sends an email via the Gmail API
  • draft_email  – Creates a Pending_Approval file (human-in-the-loop)
  • list_sent    – Lists recently sent email records

Claude Code registers this server via mcp_config.json and calls these tools
when it needs to take email actions.

USAGE (as MCP server — Claude Code calls this automatically):
    python email_mcp_server.py

USAGE (quick test from terminal):
    python email_mcp_server.py --test-send --to you@example.com --subject "Test" --body "Hello"
"""

import asyncio
import json
import sys
import os
import base64
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load .env if present
def _load_dotenv(env_path: Path):
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

_load_dotenv(Path(__file__).parent / '.env')

def _find_creds_file() -> Path:
    """Find credentials.json in vault/, repo root, or CWD."""
    candidates = [
        Path(__file__).parent / 'credentials.json',         # vault/
        Path(__file__).parent.parent / 'credentials.json',  # Ai-Employee/ (repo root)
        Path('credentials.json'),
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[1]

CREDENTIALS_FILE = _find_creds_file()
# token.json lives next to credentials.json
TOKEN_FILE = CREDENTIALS_FILE.parent / 'token.json'
DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'

# Attempt Gmail API import
_gmail_available = False
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    _gmail_available = True
except ImportError:
    pass  # Falls back to file-based simulation


def _get_gmail_service():
    """Build and return an authenticated Gmail service, or None if unavailable."""
    if not _gmail_available:
        return None
    if not TOKEN_FILE.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
        return build('gmail', 'v1', credentials=creds)
    except Exception:
        return None


def _send_via_gmail(to: str, subject: str, body: str,
                    cc: str = '', bcc: str = '') -> Dict[str, Any]:
    """Send an email using the Gmail API."""
    service = _get_gmail_service()
    if not service:
        return {'success': False, 'error': 'Gmail service unavailable. Run: python gmail_watcher.py --setup'}

    try:
        msg = MIMEMultipart('alternative')

        # Get sender's email from Gmail profile
        try:
            profile = service.users().getProfile(userId='me').execute()
            sender_email = profile.get('emailAddress', 'me@gmail.com')
        except Exception:
            sender_email = 'me@gmail.com'

        msg['From'] = sender_email
        msg['To'] = to
        msg['Subject'] = subject
        if cc:
            msg['Cc'] = cc
        if bcc:
            msg['Bcc'] = bcc
        msg.attach(MIMEText(body, 'plain'))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = service.users().messages().send(userId='me', body={'raw': raw}).execute()

        return {
            'success': True,
            'message_id': sent.get('id'),
            'thread_id': sent.get('threadId'),
            'message': f"Email sent to {to} | subject: '{subject}'"
        }
    except HttpError as e:
        return {'success': False, 'error': f'Gmail API error: {e}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _log_email(vault_path: Path, action: str, params: Dict, result: Dict):
    """Append an entry to today's JSON log."""
    logs_dir = vault_path / 'Logs'
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"

    entry = {
        'timestamp': datetime.now().isoformat(),
        'action_type': action,
        'actor': 'email_mcp_server',
        'target': params.get('to', ''),
        'parameters': {'subject': params.get('subject', '')},
        'result': 'success' if result.get('success') else 'failure',
        'dry_run': DRY_RUN
    }

    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text())
        except Exception:
            entries = []
    entries.append(entry)
    log_file.write_text(json.dumps(entries, indent=2))


class EmailMCPServer:
    def __init__(self):
        self.name = 'email-mcp'
        self.version = '0.2.0'
        self.vault_path = Path(__file__).parent

    # ------------------------------------------------------------------ #
    #  MCP capability declaration
    # ------------------------------------------------------------------ #

    def get_capabilities(self) -> Dict[str, Any]:
        tools = [
            {
                'name': 'send_email',
                'description': 'Send an email immediately via Gmail API (requires prior approval for external contacts)',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'to':      {'type': 'string', 'description': 'Recipient email address'},
                        'subject': {'type': 'string', 'description': 'Email subject line'},
                        'body':    {'type': 'string', 'description': 'Plain-text email body'},
                        'cc':      {'type': 'string', 'description': 'CC address (optional)'},
                        'bcc':     {'type': 'string', 'description': 'BCC address (optional)'},
                    },
                    'required': ['to', 'subject', 'body']
                }
            },
            {
                'name': 'draft_email',
                'description': 'Create an email draft in Pending_Approval/ for human review before sending',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'to':      {'type': 'string', 'description': 'Recipient email address'},
                        'subject': {'type': 'string', 'description': 'Email subject line'},
                        'body':    {'type': 'string', 'description': 'Plain-text email body'},
                        'cc':      {'type': 'string', 'description': 'CC address (optional)'},
                        'reason':  {'type': 'string', 'description': 'Why this email needs to be sent'},
                    },
                    'required': ['to', 'subject', 'body']
                }
            },
            {
                'name': 'list_sent',
                'description': 'List recently sent email records from the vault log',
                'inputSchema': {'type': 'object', 'properties': {}}
            }
        ]
        return {
            'version': '1.0',
            'name': self.name,
            'capabilities': [{'type': 'tools', 'tools': tools}]
        }

    # ------------------------------------------------------------------ #
    #  Tool implementations
    # ------------------------------------------------------------------ #

    def send_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        to = params['to']
        subject = params['subject']
        body = params['body']
        cc = params.get('cc', '')

        if DRY_RUN:
            result = {
                'success': True,
                'dry_run': True,
                'message': f"[DRY RUN] Would send email to {to} | subject: '{subject}'"
            }
        else:
            result = _send_via_gmail(to=to, subject=subject, body=body, cc=cc)

        _log_email(self.vault_path, 'email_send', params, result)

        # Write a Sent_Emails record regardless of mode
        sent_dir = self.vault_path / 'Sent_Emails'
        sent_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        record = sent_dir / f"EMAIL_{ts}.md"
        record.write_text(
            f"---\nsent_at: {datetime.now().isoformat()}\nto: {to}\nsubject: {subject}\n"
            f"status: {'sent' if result.get('success') else 'failed'}\n---\n\n"
            f"**To:** {to}\n**Subject:** {subject}\n\n{body}\n"
        )

        return result

    def draft_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        to = params['to']
        subject = params['subject']
        body = params['body']
        cc = params.get('cc', '')
        reason = params.get('reason', 'Outgoing email requires review')

        pending_dir = self.vault_path / 'Pending_Approval'
        pending_dir.mkdir(exist_ok=True)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"EMAIL_DRAFT_{ts}.md"
        filepath = pending_dir / filename

        filepath.write_text(
            f"---\ntype: email_draft\nstatus: pending_approval\n"
            f"to: {to}\nsubject: {subject}\ncc: {cc}\n"
            f"created_at: {datetime.now().isoformat()}\n---\n\n"
            f"# Email Draft — Approval Required\n\n"
            f"**Reason:** {reason}\n\n"
            f"---\n\n"
            f"**To:** {to}\n**Subject:** {subject}\n{'**CC:** ' + cc + chr(10) if cc else ''}\n"
            f"## Body\n\n{body}\n\n"
            f"---\n\n"
            f"**To approve:** Move this file to `/Approved`  \n"
            f"**To reject:** Move this file to `/Rejected`\n"
        )

        result = {
            'success': True,
            'draft_file': filename,
            'message': f"Draft created: {filename} — awaiting approval in Pending_Approval/"
        }
        _log_email(self.vault_path, 'email_draft', params, result)
        return result

    def list_sent(self, params: Dict[str, Any]) -> Dict[str, Any]:
        sent_dir = self.vault_path / 'Sent_Emails'
        if not sent_dir.exists():
            return {'success': True, 'emails': [], 'count': 0}

        emails = []
        for f in sorted(sent_dir.glob('*.md'), reverse=True)[:20]:
            lines = {l.split(':')[0].strip(): ':'.join(l.split(':')[1:]).strip()
                     for l in f.read_text().splitlines() if ':' in l}
            emails.append({
                'file': f.name,
                'to': lines.get('to', ''),
                'subject': lines.get('subject', ''),
                'sent_at': lines.get('sent_at', ''),
            })

        return {'success': True, 'emails': emails, 'count': len(emails)}

    # ------------------------------------------------------------------ #
    #  MCP stdio protocol
    # ------------------------------------------------------------------ #

    def dispatch(self, request: Dict) -> Dict:
        rid = request.get('id', 1)
        method = request.get('method', '')

        if method == 'initialize':
            return {'jsonrpc': '2.0', 'id': rid, 'result': self.get_capabilities()}

        if method == 'tools/list':
            return {'jsonrpc': '2.0', 'id': rid,
                    'result': {'tools': self.get_capabilities()['capabilities'][0]['tools']}}

        if method in ('tools/call', 'tools/run'):
            params = request.get('params', {})
            tool_name = params.get('name', '')
            args = params.get('arguments', params.get('input', {}))
            if isinstance(args, str):
                args = json.loads(args)

            handler = {'send_email': self.send_email,
                       'draft_email': self.draft_email,
                       'list_sent': self.list_sent}.get(tool_name)

            if handler:
                result = handler(args)
                return {'jsonrpc': '2.0', 'id': rid, 'result': result}
            return {'jsonrpc': '2.0', 'id': rid,
                    'error': {'code': -32601, 'message': f'Unknown tool: {tool_name}'}}

        return {'jsonrpc': '2.0', 'id': rid,
                'error': {'code': -32601, 'message': f'Unknown method: {method}'}}


async def serve():
    server = EmailMCPServer()
    print('Email MCP Server ready.', file=sys.stderr)
    loop = asyncio.get_event_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            request = json.loads(line.strip())
            response = server.dispatch(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            continue
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(json.dumps({'jsonrpc': '2.0', 'error': {'code': -32603, 'message': str(e)}}),
                  flush=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Email MCP Server')
    parser.add_argument('--test-send', action='store_true')
    parser.add_argument('--to')
    parser.add_argument('--subject', default='Test from AI Employee')
    parser.add_argument('--body', default='This is a test email from the AI Employee system.')
    args = parser.parse_args()

    if args.test_send:
        if not args.to:
            print('ERROR: --to is required for --test-send')
            sys.exit(1)
        server = EmailMCPServer()
        result = server.send_email({'to': args.to, 'subject': args.subject, 'body': args.body})
        print(json.dumps(result, indent=2))
        return

    asyncio.run(serve())


if __name__ == '__main__':
    main()
