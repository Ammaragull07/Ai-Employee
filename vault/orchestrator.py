"""
orchestrator.py - Master Orchestrator for AI Employee Silver Tier

Coordinates the complete workflow:
  1. Watches Needs_Action/ for new items from watchers
  2. Decides what requires human approval vs. auto-processing
  3. Processes Approved/ items — sends emails via Gmail, publishes LinkedIn posts
  4. Generates daily and weekly CEO briefings
  5. Updates Dashboard.md after every cycle

USAGE:
    python orchestrator.py              # Single cycle
    python orchestrator.py --watch      # Continuous (watches folders in real time)
    python orchestrator.py --briefing   # Generate CEO briefing now
"""

import time
import logging
import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

try:
    import schedule
except ImportError:
    schedule = None  # Scheduling is optional

# Load .env
def _load_dotenv(env_path: Path):
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

_load_dotenv(Path(__file__).parent / '.env')

DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'


class Orchestrator:
    """
    Master coordinator that processes vault folders and executes approved actions.
    """

    # Actions that always require human approval
    ALWAYS_APPROVE = {'payment', 'transfer', 'contract', 'legal', 'delete'}
    # Keywords that trigger approval routing
    APPROVAL_KEYWORDS = {'approval', 'payment', 'financial', 'contract', 'invoice',
                         'send', 'post', 'transfer', 'sensitive'}

    def __init__(self, vault_path: str = '.'):
        self.vault_path = Path(vault_path)
        self.logs_path = self.vault_path / 'Logs'

        # Folder layout
        self.folders = {
            'needs_action':     self.vault_path / 'Needs_Action',
            'pending_approval': self.vault_path / 'Pending_Approval',
            'approved':         self.vault_path / 'Approved',
            'rejected':         self.vault_path / 'Rejected',
            'done':             self.vault_path / 'Done',
            'plans':            self.vault_path / 'Plans',
            'briefings':        self.vault_path / 'Briefings',
            'sent_emails':      self.vault_path / 'Sent_Emails',
            'inbox':            self.vault_path / 'Inbox',
            'posted_updates':   self.vault_path / 'Posted_Updates',
        }
        for path in self.folders.values():
            path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(exist_ok=True)

        self._setup_logging()
        self._gmail_service = None
        self._linkedin_watcher = None

    def _setup_logging(self):
        log_file = self.logs_path / f"orchestrator_{datetime.now().strftime('%Y%m%d')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('Orchestrator')

    # ------------------------------------------------------------------ #
    #  Gmail helper
    # ------------------------------------------------------------------ #

    def _get_gmail_service(self):
        """Return a Gmail service if credentials are available."""
        if self._gmail_service:
            return self._gmail_service
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            # token.json lives next to credentials.json in repo root
            token_file = self.vault_path.parent / 'token.json'
            if not token_file.exists():
                token_file = self.vault_path / 'token.json'  # fallback
            if not token_file.exists():
                return None
            creds = Credentials.from_authorized_user_file(str(token_file))
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                token_file.write_text(creds.to_json())
            self._gmail_service = build('gmail', 'v1', credentials=creds)
            return self._gmail_service
        except Exception as e:
            self.logger.warning(f"Gmail service unavailable: {e}")
            return None

    def _send_gmail(self, to: str, subject: str, body: str, cc: str = '') -> bool:
        """Actually send an email via Gmail API. Returns True on success."""
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        service = self._get_gmail_service()
        if not service:
            self.logger.error("Cannot send email: Gmail service not available")
            return False
        if DRY_RUN:
            self.logger.info(f"[DRY RUN] Would send email to {to} | subject: {subject}")
            return True
        try:
            msg = MIMEMultipart('alternative')
            msg['To'] = to
            msg['Subject'] = subject
            if cc:
                msg['Cc'] = cc
            msg.attach(MIMEText(body, 'plain'))
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(userId='me', body={'raw': raw}).execute()
            self.logger.info(f"Email sent to {to} | subject: {subject}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  LinkedIn helper
    # ------------------------------------------------------------------ #

    def _get_linkedin_watcher(self):
        if self._linkedin_watcher is None:
            try:
                from linkedin_watcher import LinkedInWatcher
                self._linkedin_watcher = LinkedInWatcher(str(self.vault_path))
            except Exception as e:
                self.logger.warning(f"LinkedIn watcher unavailable: {e}")
        return self._linkedin_watcher

    # ------------------------------------------------------------------ #
    #  Email AI Responder
    # ------------------------------------------------------------------ #

    def _auto_respond_to_email(self, file_path: Path) -> bool:
        """
        Use Claude AI to generate and send an automatic response to an email.
        Returns True if response was sent successfully.
        """
        try:
            from email_responder import EmailResponder
            responder = EmailResponder(str(self.vault_path))
            return responder.respond_to_email(file_path.name)
        except ImportError:
            self.logger.warning("email_responder module not available (anthropic SDK may not be installed)")
            return False
        except Exception as e:
            self.logger.error(f"Error generating email response: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Needs_Action processing
    # ------------------------------------------------------------------ #

    def process_needs_action(self) -> int:
        """
        Process all .md files in Needs_Action/.
        Routes each file to Pending_Approval or Done based on content.
        Returns number of files processed.
        """
        files = list(self.folders['needs_action'].glob('*.md'))
        if not files:
            return 0

        self.logger.info(f"Processing {len(files)} file(s) in Needs_Action/")
        processed = 0

        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8')
                # Create a Plan.md for each item
                plan_file = self._create_plan(file_path, content)
                if plan_file:
                    self.logger.info(f"Plan created: {plan_file.name}")

                # Auto-respond to emails using Claude AI
                if file_path.name.upper().startswith('EMAIL_'):
                    response_sent = self._auto_respond_to_email(file_path)
                    if response_sent:
                        self.logger.info(f"AI response sent automatically for: {file_path.name}")
                        # Move original email to Done after auto-response
                        dest = self.folders['done'] / file_path.name
                        file_path.rename(dest)
                        self.logger.info(f"Original email archived to Done: {file_path.name}")
                        processed += 1
                        continue

                if self._requires_approval(file_path, content):
                    dest = self.folders['pending_approval'] / file_path.name
                    file_path.rename(dest)
                    self.logger.info(f"Moved to Pending_Approval: {file_path.name}")
                else:
                    dest = self.folders['done'] / file_path.name
                    file_path.rename(dest)
                    self.logger.info(f"Auto-resolved (moved to Done): {file_path.name}")
                processed += 1
            except Exception as e:
                self.logger.error(f"Error processing {file_path.name}: {e}")

        return processed

    def _requires_approval(self, file_path: Path, content: str) -> bool:
        """True if the item should be queued for human approval."""
        name_upper = file_path.name.upper()
        if any(kw.upper() in name_upper for kw in ['EMAIL', 'LINKEDIN', 'WHATSAPP', 'APPROVAL', 'PAYMENT']):
            return True
        content_lower = content.lower()
        return any(kw in content_lower for kw in self.APPROVAL_KEYWORDS)

    def _create_plan(self, source_file: Path, content: str) -> Optional[Path]:
        """
        Generate a Plan.md for an incoming Needs_Action item.
        This is the 'reasoning loop' — Claude can later refine these plans.
        """
        # Determine item type from filename prefix
        name = source_file.name
        item_type = 'general'
        for prefix in ('EMAIL_', 'LINKEDIN_', 'WHATSAPP_', 'FILE_DROP_'):
            if name.upper().startswith(prefix):
                item_type = prefix.rstrip('_').lower()
                break

        # Extract subject/summary from first non-frontmatter heading
        subject_match = re.search(r'^#+\s+(.+)$', content, re.MULTILINE)
        summary = subject_match.group(1)[:80] if subject_match else name

        steps = {
            'email': [
                'Read and understand the email content',
                'Determine if a reply is required',
                'Draft reply (create Pending_Approval file if sending externally)',
                'Update Dashboard.md',
                'Archive original email to Done/',
            ],
            'linkedin': [
                'Review LinkedIn post content',
                'Approve or reject the post',
                'If approved, move approval file to Approved/',
                'Confirm post was published in Posted_Updates/',
            ],
            'whatsapp': [
                'Read the WhatsApp message',
                'Determine urgency and required response',
                'Draft response if needed',
                'Flag for priority handling if urgent keyword detected',
            ],
            'file_drop': [
                'Review the dropped file',
                'Determine file type and purpose',
                'Route to appropriate folder or process',
            ],
            'general': [
                'Review item details',
                'Determine required action',
                'Execute action or route for approval',
                'Update Dashboard.md',
            ],
        }.get(item_type, ['Review item', 'Take appropriate action', 'Update Dashboard.md'])

        steps_md = '\n'.join(f'- [ ] {s}' for s in steps)
        plan_content = f"""---
created: {datetime.now().isoformat()}
source: {source_file.name}
type: {item_type}_plan
status: pending
---

# Plan: {summary}

## Objective
Process `{source_file.name}` and take the appropriate action.

## Steps
{steps_md}

## Approval Required
{'Yes — move the corresponding Pending_Approval file to /Approved when ready.' if item_type in ('email', 'linkedin', 'whatsapp') else 'No — this can be auto-processed.'}
"""

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        plan_path = self.folders['plans'] / f"PLAN_{item_type.upper()}_{ts}.md"
        plan_path.write_text(plan_content, encoding='utf-8')
        return plan_path

    # ------------------------------------------------------------------ #
    #  Approved-action processing
    # ------------------------------------------------------------------ #

    def process_approved(self) -> int:
        """Execute all approved actions and move files to Done/."""
        files = list(self.folders['approved'].glob('*.md'))
        if not files:
            return 0

        self.logger.info(f"Executing {len(files)} approved action(s)")
        executed = 0

        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8')
                name_upper = file_path.name.upper()

                if 'EMAIL' in name_upper:
                    ok = self._execute_email_action(file_path, content)
                elif 'LINKEDIN' in name_upper:
                    ok = self._execute_linkedin_action(file_path, content)
                elif 'PAYMENT' in name_upper:
                    ok = self._execute_payment_action(file_path, content)
                else:
                    self.logger.info(f"No specific handler for {file_path.name} — moving to Done")
                    ok = True

                dest_folder = self.folders['done'] if ok else self.folders['rejected']
                dest = dest_folder / file_path.name
                file_path.rename(dest)
                executed += 1
            except Exception as e:
                self.logger.error(f"Error executing approved action {file_path.name}: {e}")

        return executed

    def process_rejected(self) -> int:
        """Log and archive rejected items."""
        files = list(self.folders['rejected'].glob('*.md'))
        for file_path in files:
            self.logger.info(f"Rejected (archived): {file_path.name}")
            dest = self.folders['done'] / file_path.name
            try:
                file_path.rename(dest)
            except Exception:
                pass
        return len(files)

    def _execute_email_action(self, file_path: Path, content: str) -> bool:
        """Send an approved email draft via Gmail."""
        # Parse frontmatter fields
        to_match = re.search(r'^to:\s*(.+)$', content, re.MULTILINE)
        subject_match = re.search(r'^subject:\s*(.+)$', content, re.MULTILINE)
        cc_match = re.search(r'^cc:\s*(.+)$', content, re.MULTILINE)

        # Extract body (text after the last --- line)
        body_match = re.search(r'## Body\s*\n+([\s\S]+?)(?:\n---|\Z)', content)
        if not body_match:
            # Fall back: everything after the second ---
            parts = content.split('---')
            body = parts[-1].strip() if len(parts) >= 3 else content
        else:
            body = body_match.group(1).strip()

        if not to_match or not subject_match:
            self.logger.error(f"Cannot parse email fields from {file_path.name}")
            return False

        to = to_match.group(1).strip()
        subject = subject_match.group(1).strip()
        cc = cc_match.group(1).strip() if cc_match else ''
        # Ignore placeholder "None" cc values
        if cc.lower() in ('none', 'n/a', ''):
            cc = ''

        return self._send_gmail(to=to, subject=subject, body=body, cc=cc)

    def _execute_linkedin_action(self, file_path: Path, content: str) -> bool:
        """Publish an approved LinkedIn post."""
        lw = self._get_linkedin_watcher()
        if lw is None:
            self.logger.error("LinkedIn watcher not available")
            return False
        try:
            lw._publish_approved_post(file_path)
            # _publish_approved_post moves the file itself, so prevent double-move
            return True
        except Exception as e:
            self.logger.error(f"LinkedIn post execution failed: {e}")
            return False

    def _execute_payment_action(self, file_path: Path, content: str) -> bool:
        """Placeholder — payment execution always requires manual action."""
        self.logger.warning(
            f"PAYMENT action in {file_path.name} requires manual execution. "
            "Automated payments are disabled for security."
        )
        return False

    # ------------------------------------------------------------------ #
    #  Dashboard update
    # ------------------------------------------------------------------ #

    def update_dashboard(self):
        """Rewrite Dashboard.md with current system status."""
        na = len(list(self.folders['needs_action'].glob('*.md')))
        pa = len(list(self.folders['pending_approval'].glob('*.md')))
        done_today = len([
            f for f in self.folders['done'].glob('*.md')
            if datetime.fromtimestamp(f.stat().st_mtime).date() == datetime.now().date()
        ])
        plans = len(list(self.folders['plans'].glob('*.md')))
        sent = len(list(self.folders['sent_emails'].glob('*.md')))
        posted = len(list(self.folders['posted_updates'].glob('*.md')))

        dashboard = f"""# AI Employee Dashboard
## Silver Tier — Personal AI Employee

**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## System Status

| Folder | Count |
|--------|-------|
| Needs Action | {na} |
| Pending Approval | {pa} |
| Done Today | {done_today} |
| Active Plans | {plans} |
| Emails Sent | {sent} |
| LinkedIn Posts | {posted} |

---

## Active Watchers
- Gmail Watcher — monitoring inbox every 2 min
- LinkedIn Watcher — monitoring Pending_Social_Posts/ every 5 min
- WhatsApp Watcher — monitoring DropFolder/ every 30 sec
- Filesystem Watcher — monitoring DropFolder/ in real time

---

## Pending Approvals ({pa})
{'_None — all clear!_' if pa == 0 else
 chr(10).join(f'- `{f.name}`' for f in self.folders['pending_approval'].glob('*.md'))}

---

## Recent Activity
_Check `Logs/` for detailed activity logs._

---

## Quick Actions
- Drop a file in `DropFolder/` to trigger processing
- Add a post to `Pending_Social_Posts/` for LinkedIn auto-posting
- Move files from `Pending_Approval/` to `Approved/` or `Rejected/`
"""
        dashboard_path = self.vault_path / 'Dashboard.md'
        dashboard_path.write_text(dashboard, encoding='utf-8')
        self.logger.info("Dashboard.md updated")

    # ------------------------------------------------------------------ #
    #  CEO Briefings
    # ------------------------------------------------------------------ #

    def generate_briefing(self, period: str = 'daily'):
        """Generate a CEO briefing and save to Briefings/."""
        days_back = 1 if period == 'daily' else 7
        cutoff = datetime.now() - timedelta(days=days_back)

        done_files = [f for f in self.folders['done'].glob('*.md')
                      if datetime.fromtimestamp(f.stat().st_mtime) >= cutoff]
        email_count = sum(1 for f in done_files if 'EMAIL' in f.name.upper())
        linkedin_count = sum(1 for f in done_files if 'LINKEDIN' in f.name.upper())

        na = len(list(self.folders['needs_action'].glob('*.md')))
        pa = len(list(self.folders['pending_approval'].glob('*.md')))

        period_label = 'Today' if period == 'daily' else f"Past 7 Days"
        title = f"{'Daily' if period == 'daily' else 'Monday Morning'} CEO Briefing"

        content = f"""---
generated: {datetime.now().isoformat()}
period: {cutoff.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}
type: {period}_briefing
---

# {title}
**{datetime.now().strftime('%B %d, %Y')}**

---

## Executive Summary
{period_label}: **{len(done_files)} task(s) completed**, {email_count} emails handled,
{linkedin_count} LinkedIn posts published.

---

## Completed Tasks ({len(done_files)})
{chr(10).join(f'- `{f.name}`' for f in done_files[:20]) or '_None_'}

---

## Current Backlog
| Queue | Count |
|-------|-------|
| Needs Action | {na} |
| Pending Approval | {pa} |

---

## Communications Summary
- **Emails handled:** {email_count}
- **LinkedIn posts:** {linkedin_count}

---

## Proactive Suggestions
- {'Review the ' + str(pa) + ' item(s) pending approval.' if pa > 0 else 'No pending approvals — great!'}
- Ensure watchers are running (check `Logs/` for activity).
- Review `Plans/` folder for any stalled tasks.

---
*Generated by AI Employee v0.2 (Silver Tier)*
"""

        ts = datetime.now().strftime('%Y-%m-%d')
        filename = f"{ts}_{period.title()}_Briefing.md"
        filepath = self.folders['briefings'] / filename
        filepath.write_text(content, encoding='utf-8')
        self.logger.info(f"{period.title()} briefing generated: {filename}")
        return filepath

    # ------------------------------------------------------------------ #
    #  Audit log
    # ------------------------------------------------------------------ #

    def _write_audit_log(self, action: str, details: str, result: str):
        log_file = self.logs_path / f"{datetime.now().strftime('%Y-%m-%d')}.json"
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'details': details,
            'result': result,
        }
        entries = []
        if log_file.exists():
            try:
                entries = json.loads(log_file.read_text())
            except Exception:
                entries = []
        entries.append(entry)
        log_file.write_text(json.dumps(entries, indent=2))

    # ------------------------------------------------------------------ #
    #  Run modes
    # ------------------------------------------------------------------ #

    def run_once(self):
        """Execute one full orchestration cycle."""
        self.logger.info("── Orchestration cycle start ──────────────────")
        processed = self.process_needs_action()
        executed = self.process_approved()
        self.process_rejected()
        self.update_dashboard()
        self.logger.info(
            f"── Cycle complete — processed: {processed}, executed: {executed} ──"
        )

    def run_continuous(self, interval: int = 60):
        """Run orchestration cycles indefinitely."""
        self.logger.info(f"Continuous orchestration started (interval: {interval}s)")

        if schedule:
            schedule.every().day.at("07:00").do(self.generate_briefing, period='daily')
            schedule.every().sunday.at("22:00").do(self.generate_briefing, period='weekly')

        try:
            while True:
                self.run_once()
                if schedule:
                    schedule.run_pending()
                time.sleep(interval)
        except KeyboardInterrupt:
            self.logger.info("Orchestrator stopped.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='AI Employee Orchestrator')
    parser.add_argument('--vault', default='.', help='Vault path (default: current directory)')
    parser.add_argument('--watch', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=60, help='Cycle interval in seconds')
    parser.add_argument('--briefing', choices=['daily', 'weekly'], help='Generate a briefing now')
    args = parser.parse_args()

    orch = Orchestrator(vault_path=args.vault)

    if args.briefing:
        path = orch.generate_briefing(period=args.briefing)
        print(f"Briefing generated: {path}")
        return

    if args.watch:
        print(f"Orchestrator running continuously (interval: {args.interval}s).")
        print("Press Ctrl+C to stop.")
        orch.run_continuous(interval=args.interval)
    else:
        orch.run_once()


if __name__ == '__main__':
    main()
