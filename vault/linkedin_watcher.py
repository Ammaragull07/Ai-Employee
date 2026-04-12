"""
linkedin_watcher.py - LinkedIn Watcher for AI Employee Silver Tier

Two responsibilities:
  1. WATCHER  – Polls the vault's Pending_Social_Posts/ folder for draft posts
               and creates action files requesting approval before publishing.
  2. POSTER   – After approval, posts content to LinkedIn via the API.

SETUP:
  1. Create a LinkedIn Developer App at https://www.linkedin.com/developers/
  2. Add the following OAuth 2.0 scopes: openid, profile, w_member_social
  3. Generate an access token (LinkedIn OAuth 2.0 or use the Token Generator tool
     in the Developer portal for testing)
  4. Copy .env.example to .env and fill in LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN

USAGE:
  python linkedin_watcher.py                 # Continuous monitoring
  python linkedin_watcher.py --once          # Single check and exit
  python linkedin_watcher.py --post "text"   # Post directly to LinkedIn

ENVIRONMENT VARIABLES (in .env or exported):
  LINKEDIN_ACCESS_TOKEN   – OAuth 2.0 access token
  LINKEDIN_PERSON_URN     – Your LinkedIn person URN, e.g. urn:li:person:ABC123
  LINKEDIN_ORG_URN        – (optional) Company page URN for org posts
"""

import time
import logging
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    print("Missing 'requests'. Run: pip install requests")
    sys.exit(1)

# Load .env file if it exists (simple parser, no external dependency)
def _load_dotenv(env_path: Path):
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(Path(__file__).parent / '.env')


LINKEDIN_API_BASE = 'https://api.linkedin.com/v2'


class LinkedInAPI:
    """Thin wrapper around LinkedIn UGC Posts API."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
        })
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_profile(self) -> Optional[Dict]:
        """Fetch basic profile info to verify the token is valid."""
        try:
            resp = self.session.get(f'{LINKEDIN_API_BASE}/me')
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"Could not fetch LinkedIn profile: {e}")
            return None

    def post_text(self, author_urn: str, text: str, visibility: str = 'PUBLIC') -> Optional[Dict]:
        """
        Publish a plain-text post via LinkedIn UGC Posts API.

        author_urn : e.g. "urn:li:person:ABC123" or "urn:li:organization:456"
        text       : Post body (max 3000 chars recommended)
        visibility : 'PUBLIC' | 'CONNECTIONS'
        """
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": visibility
            }
        }

        try:
            resp = self.session.post(f'{LINKEDIN_API_BASE}/ugcPosts', json=payload)
            resp.raise_for_status()
            post_id = resp.headers.get('x-restli-id', resp.json().get('id', 'unknown'))
            self.logger.info(f"LinkedIn post published. ID: {post_id}")
            return {'success': True, 'post_id': post_id}
        except requests.HTTPError as e:
            self.logger.error(f"LinkedIn API error ({resp.status_code}): {resp.text}")
            return {'success': False, 'error': str(e), 'response': resp.text}
        except Exception as e:
            self.logger.error(f"Unexpected error posting to LinkedIn: {e}")
            return {'success': False, 'error': str(e)}


class LinkedInWatcher:
    """
    Monitors the vault for scheduled LinkedIn posts and manages the
    approval → post → log workflow.
    """

    def __init__(self, vault_path: str, check_interval: int = 300):
        self.vault_path = Path(vault_path)
        self.check_interval = check_interval

        # Key vault folders
        self.needs_action = self.vault_path / 'Needs_Action'
        self.pending_posts = self.vault_path / 'Pending_Social_Posts'
        self.approved = self.vault_path / 'Approved'
        self.posted = self.vault_path / 'Posted_Updates'
        self.rejected = self.vault_path / 'Rejected'
        self.logs_path = self.vault_path / 'Logs'

        for d in [self.needs_action, self.pending_posts, self.approved,
                  self.posted, self.rejected, self.logs_path]:
            d.mkdir(parents=True, exist_ok=True)

        self._setup_logging()

        # LinkedIn credentials from environment
        self.access_token = os.getenv('LINKEDIN_ACCESS_TOKEN', '')
        self.person_urn = os.getenv('LINKEDIN_PERSON_URN', '')
        self.org_urn = os.getenv('LINKEDIN_ORG_URN', '')

        self._api: Optional[LinkedInAPI] = None
        self.processed_files: set = set()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.logs_path / 'linkedin_watcher.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def api(self) -> Optional[LinkedInAPI]:
        """Return a LinkedIn API client if credentials are available."""
        if self._api is None and self.access_token:
            self._api = LinkedInAPI(self.access_token)
        return self._api

    def is_configured(self) -> bool:
        """Check if LinkedIn credentials are present."""
        return bool(self.access_token and self.person_urn)

    # ------------------------------------------------------------------ #
    #  Watcher logic
    # ------------------------------------------------------------------ #

    def check_for_updates(self) -> List[Dict]:
        """
        Scan Pending_Social_Posts/ for new .md files that haven't been
        queued for approval yet.
        """
        new_items = []
        for post_file in self.pending_posts.glob('*.md'):
            if str(post_file) not in self.processed_files:
                try:
                    content = post_file.read_text(encoding='utf-8')
                    new_items.append({
                        'type': 'scheduled_post',
                        'file_path': post_file,
                        'content': content,
                        'timestamp': datetime.now().isoformat(),
                    })
                    self.processed_files.add(str(post_file))
                except Exception as e:
                    self.logger.error(f"Error reading {post_file}: {e}")

        if new_items:
            self.logger.info(f"Found {len(new_items)} new LinkedIn post(s) to queue for approval")
        return new_items

    def create_action_file(self, item: Dict) -> Path:
        """
        Create an approval-request action file so Claude / the human can
        review the post before it goes live.
        """
        post_file: Path = item['file_path']
        content = item['content']

        # Extract post text (skip YAML front-matter if present)
        post_text = self._strip_frontmatter(content)

        approval_content = f"""---
type: approval_request
action: linkedin_post
source_file: {post_file.name}
created_at: {datetime.now().isoformat()}
status: pending
---

# LinkedIn Post Approval Required

**Source file:** `{post_file.name}`
**Queued at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Post Content Preview

{post_text[:800]}{'...' if len(post_text) > 800 else ''}

---

## To Approve
Move this file to `/Approved` – the LinkedIn Watcher will publish it automatically.

## To Reject
Move this file to `/Rejected` – the post will not be published.

## To Edit
Edit the source file at `Pending_Social_Posts/{post_file.name}`, then move this
file back to `/Needs_Action`.
"""

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"LINKEDIN_APPROVAL_{timestamp}_{post_file.stem}.md"
        filepath = self.needs_action / filename
        filepath.write_text(approval_content, encoding='utf-8')

        self.logger.info(f"Approval request created: {filename}")
        return filepath

    # ------------------------------------------------------------------ #
    #  Approved-post processing
    # ------------------------------------------------------------------ #

    def process_approved_posts(self):
        """
        Check /Approved for LinkedIn approval files and publish them.
        """
        for approval_file in self.approved.glob('LINKEDIN_APPROVAL_*.md'):
            try:
                self._publish_approved_post(approval_file)
            except Exception as e:
                self.logger.error(f"Error publishing {approval_file.name}: {e}")

    def _publish_approved_post(self, approval_file: Path):
        """Read an approved file, find the source post, and publish to LinkedIn."""
        content = approval_file.read_text(encoding='utf-8')

        # Find source file name from frontmatter
        source_match = re.search(r'^source_file:\s*(.+)$', content, re.MULTILINE)
        source_filename = source_match.group(1).strip() if source_match else None

        post_text = None

        if source_filename:
            source_path = self.pending_posts / source_filename
            if source_path.exists():
                raw = source_path.read_text(encoding='utf-8')
                post_text = self._strip_frontmatter(raw).strip()

        # Fall back: extract preview text directly from the approval file
        if not post_text:
            preview_match = re.search(
                r'## Post Content Preview\n+(.+?)(?:\n---|\Z)', content, re.DOTALL
            )
            if preview_match:
                post_text = preview_match.group(1).strip().rstrip('...')

        if not post_text:
            self.logger.error(f"Could not extract post text from {approval_file.name}")
            self._archive_file(approval_file, self.rejected)
            return

        # Publish
        if self.is_configured() and self.api:
            author_urn = self.org_urn or self.person_urn
            result = self.api.post_text(author_urn=author_urn, text=post_text)

            if result and result.get('success'):
                self.logger.info(f"LinkedIn post published! ID: {result.get('post_id')}")
                self._write_post_log(post_text, result.get('post_id', 'unknown'))
                self._archive_file(approval_file, self.posted)
                if source_filename:
                    src = self.pending_posts / source_filename
                    if src.exists():
                        self._archive_file(src, self.posted)
            else:
                self.logger.error(f"LinkedIn post failed: {result}")
                # Leave the file in Approved so the user can retry
        else:
            # Dry-run mode: no credentials configured
            self.logger.warning("LinkedIn credentials not configured — simulating post.")
            self._write_post_log(post_text, post_id='DRY_RUN', dry_run=True)
            self._archive_file(approval_file, self.posted)

    def _write_post_log(self, text: str, post_id: str, dry_run: bool = False):
        """Write a record of the published post to Posted_Updates/."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"LINKEDIN_POST_{timestamp}.md"
        filepath = self.posted / filename

        log_content = f"""---
posted_at: {datetime.now().isoformat()}
platform: linkedin
post_id: {post_id}
dry_run: {str(dry_run).lower()}
author_urn: {self.org_urn or self.person_urn or 'unknown'}
---

# LinkedIn Post {'(DRY RUN)' if dry_run else 'Published'}

**Post ID:** {post_id}
**Published:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{text}
"""
        filepath.write_text(log_content, encoding='utf-8')
        self.logger.info(f"Post log written: {filename}")

    def _archive_file(self, file_path: Path, destination: Path):
        """Move a file to the destination folder."""
        try:
            dest = destination / file_path.name
            file_path.rename(dest)
        except Exception as e:
            self.logger.warning(f"Could not move {file_path.name} to {destination}: {e}")

    @staticmethod
    def _strip_frontmatter(text: str) -> str:
        """Remove YAML front-matter (--- ... ---) from markdown text."""
        stripped = re.sub(r'^---\n.*?\n---\n?', '', text, count=1, flags=re.DOTALL)
        return stripped.strip()

    # ------------------------------------------------------------------ #
    #  Direct post helper
    # ------------------------------------------------------------------ #

    def post_now(self, text: str, visibility: str = 'PUBLIC') -> bool:
        """
        Immediately publish text to LinkedIn (no approval step).
        Returns True on success.
        """
        if not self.is_configured():
            self.logger.error(
                "LinkedIn credentials not set. Add LINKEDIN_ACCESS_TOKEN and "
                "LINKEDIN_PERSON_URN to .env"
            )
            return False

        author_urn = self.org_urn or self.person_urn
        result = self.api.post_text(author_urn=author_urn, text=text, visibility=visibility)

        if result and result.get('success'):
            self._write_post_log(text, result.get('post_id', 'unknown'))
            return True

        return False

    # ------------------------------------------------------------------ #
    #  Main loop
    # ------------------------------------------------------------------ #

    def run(self):
        """Continuously monitor for new posts and process approved ones."""
        self.logger.info(f"LinkedIn Watcher starting (interval: {self.check_interval}s)")

        if not self.is_configured():
            self.logger.warning(
                "LinkedIn credentials not configured. Running in APPROVAL-ONLY mode "
                "(posts will be queued but not published). "
                "Add LINKEDIN_ACCESS_TOKEN + LINKEDIN_PERSON_URN to .env to enable publishing."
            )

        while True:
            try:
                # Queue new posts for approval
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)

                # Publish approved posts
                self.process_approved_posts()

            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")

            time.sleep(self.check_interval)


# ------------------------------------------------------------------ #
#  Convenience: create a sample post file for testing
# ------------------------------------------------------------------ #

def create_sample_post(vault_path: str):
    """Write a sample post file into Pending_Social_Posts/ for testing."""
    posts_dir = Path(vault_path) / 'Pending_Social_Posts'
    posts_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"post_{timestamp}.md"
    filepath = posts_dir / filename

    sample = f"""---
title: Business Update
scheduled: {datetime.now().isoformat()}
visibility: PUBLIC
---

Excited to share what we've been working on this week! 🚀

We've been building an AI Employee system that automates routine tasks,
monitors communications, and generates weekly CEO briefings — all running
locally with Claude Code as the brain.

If you're interested in autonomous agent architecture, let's connect!

#AI #Automation #ClaudeCode #Innovation #TechStartup
"""
    filepath.write_text(sample, encoding='utf-8')
    print(f"Sample post created: {filepath}")
    return filepath


def main():
    import argparse

    parser = argparse.ArgumentParser(description='LinkedIn Watcher for AI Employee Silver Tier')
    parser.add_argument('--vault', default='.',
                        help='Path to Obsidian vault directory (default: current directory)')
    parser.add_argument('--interval', type=int, default=300,
                        help='Check interval in seconds (default: 300)')
    parser.add_argument('--once', action='store_true',
                        help='Run a single check cycle and exit')
    parser.add_argument('--post', metavar='TEXT',
                        help='Post TEXT directly to LinkedIn and exit')
    parser.add_argument('--sample', action='store_true',
                        help='Create a sample post file for testing and exit')
    args = parser.parse_args()

    # Logging for standalone use
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    watcher = LinkedInWatcher(vault_path=args.vault, check_interval=args.interval)

    if args.sample:
        create_sample_post(args.vault)
        return

    if args.post:
        success = watcher.post_now(args.post)
        print("Posted successfully." if success else "Post failed — check logs.")
        sys.exit(0 if success else 1)

    if args.once:
        items = watcher.check_for_updates()
        for item in items:
            watcher.create_action_file(item)
        watcher.process_approved_posts()
        print(f"Done. Queued {len(items)} post(s) for approval.")
        return

    print(f"LinkedIn Watcher")
    print(f"Vault    : {Path(args.vault).absolute()}")
    print(f"Interval : {args.interval}s")
    print(f"Credentials configured: {watcher.is_configured()}")
    print("Press Ctrl+C to stop.\n")

    try:
        watcher.run()
    except KeyboardInterrupt:
        print("\nLinkedIn Watcher stopped.")


if __name__ == "__main__":
    main()
