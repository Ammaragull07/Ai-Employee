"""
WhatsApp Watcher for AI Employee - Silver Tier

Monitors WhatsApp for messages and creates action files for the AI Employee to process.
Uses Playwright for WhatsApp Web automation.
"""

import time
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime
import json
from typing import Dict, List, Optional
import os


class BaseWatcher(ABC):
    """Base class for all watchers"""

    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / 'Needs_Action'
        self.check_interval = check_interval
        self.logger = logging.getLogger(self.__class__.__name__)

        # Create necessary directories if they don't exist
        self.needs_action.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def check_for_updates(self) -> list:
        """Return list of new items to process"""
        pass

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """Create .md file in Needs_Action folder"""
        pass

    def run(self):
        """Main run loop for the watcher"""
        self.logger.info(f'Starting {self.__class__.__name__}')
        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)
            except Exception as e:
                self.logger.error(f'Error: {e}')
            time.sleep(self.check_interval)


class WhatsAppWatcher(BaseWatcher):
    """
    WhatsApp Watcher that monitors for new messages using Playwright
    Note: This uses WhatsApp Web automation. Be aware of WhatsApp's terms of service.
    """

    def __init__(self, vault_path: str, session_path: str = None):
        super().__init__(vault_path, check_interval=30)  # Check every 30 seconds
        self.session_path = Path(session_path) if session_path else Path.home() / '.whatsapp_session'
        self.keywords = ['urgent', 'asap', 'invoice', 'payment', 'help', 'need', 'now', 'important']
        self.processed_messages = set()

        # Create session directory
        self.session_path.mkdir(parents=True, exist_ok=True)

    def check_for_updates(self) -> List[Dict]:
        """
        Check WhatsApp Web for new messages
        This is a simulated implementation - in production, you'd use Playwright to automate WhatsApp Web
        """
        # For simulation, check if there are any WhatsApp-related files in a DropFolder
        # that might indicate new WhatsApp activity

        new_items = []

        # Check for files in a drop folder that might indicate WhatsApp activity
        drop_folder = self.vault_path / 'DropFolder'
        if drop_folder.exists():
            for file_path in drop_folder.glob('*whatsapp*'):
                if file_path.suffix.lower() in ['.txt', '.md'] and str(file_path) not in self.processed_messages:
                    content = file_path.read_text()
                    new_items.append({
                        'type': 'whatsapp_message',
                        'sender': 'Unknown',
                        'content': content[:200] + '...' if len(content) > 200 else content,
                        'timestamp': datetime.now().isoformat(),
                        'file_path': str(file_path)
                    })
                    self.processed_messages.add(str(file_path))

        # Simulate detecting WhatsApp keywords in any new text files
        for text_file in self.vault_path.glob('**/*.txt'):
            if text_file != self.session_path and str(text_file) not in self.processed_messages:
                content = text_file.read_text().lower()
                if any(keyword in content for keyword in self.keywords):
                    new_items.append({
                        'type': 'whatsapp_keyword_detected',
                        'sender': 'Keyword Detection',
                        'content': content[:200] + '...' if len(content) > 200 else content,
                        'timestamp': datetime.now().isoformat(),
                        'file_path': str(text_file),
                        'keyword': next((kw for kw in self.keywords if kw in content), 'unknown')
                    })
                    self.processed_messages.add(str(text_file))

        return new_items

    def create_action_file(self, item: Dict) -> Path:
        """Create action file for WhatsApp message"""
        content = f"""---
type: whatsapp_alert
message_type: {item['type']}
from: {item['sender']}
received: {item['timestamp']}
priority: high
status: pending
keywords: [{item.get('keyword', 'general')}]
---

# WhatsApp Message Alert

## Sender
{item['sender']}

## Content Preview
{item['content']}

## Original File
{item['file_path']}

## Suggested Actions
- [ ] Review full message content
- [ ] Respond appropriately
- [ ] Flag for priority handling if urgent

"""
        filepath = self.needs_action / f"WHATSAPP_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(item['content']) % 10000}.md"
        filepath.write_text(content)
        return filepath


def simulate_whatsapp_message(vault_path: str, sender: str, message: str):
    """
    Helper function to simulate receiving a WhatsApp message for testing
    """
    vault = Path(vault_path)
    drop_folder = vault / 'DropFolder'
    drop_folder.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"whatsapp_sim_{timestamp}_{hash(message) % 10000}.txt"
    filepath = drop_folder / filename

    content = f"FROM: {sender}\nMESSAGE: {message}\nTIMESTAMP: {datetime.now().isoformat()}"
    filepath.write_text(content)

    print(f"Simulated WhatsApp message saved: {filepath}")


def main():
    """Main function to run the WhatsApp watcher"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize the WhatsApp watcher
    vault_path = Path(__file__).parent  # Assuming script is in the vault directory
    watcher = WhatsAppWatcher(str(vault_path))

    print(f"WhatsApp Watcher initialized. Checking every {watcher.check_interval} seconds.")
    print("Press Ctrl+C to stop.")

    try:
        # For demonstration, we'll just run once
        # In a real implementation, you'd call watcher.run() for continuous monitoring
        items = watcher.check_for_updates()
        for item in items:
            watcher.create_action_file(item)
        print(f"Checked for WhatsApp updates, found {len(items)} items.")

        # Simulate a WhatsApp message for testing
        print("\nSimulating a WhatsApp message...")
        simulate_whatsapp_message(str(vault_path), "Client A", "Hi, can you send me the invoice for our project asap?")

    except KeyboardInterrupt:
        print("\nWhatsApp Watcher stopped by user.")


if __name__ == "__main__":
    main()