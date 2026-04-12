"""
base_watcher.py - Shared base class for all AI Employee watchers.

All watchers (Gmail, LinkedIn, WhatsApp, Filesystem) inherit from BaseWatcher.
"""

import time
import logging
from pathlib import Path
from abc import ABC, abstractmethod


class BaseWatcher(ABC):
    """
    Base class that every watcher must subclass.
    Provides the run loop, logging setup, and folder creation.
    """

    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / 'Needs_Action'
        self.check_interval = check_interval

        # Ensure Needs_Action folder exists
        self.needs_action.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def check_for_updates(self) -> list:
        """Return a list of new items to process."""
        pass

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """Create a .md action file in Needs_Action/ for a given item."""
        pass

    def run(self):
        """Blocking run loop — checks for updates every check_interval seconds."""
        self.logger.info(f"{self.__class__.__name__} started (interval: {self.check_interval}s)")
        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.logger.error(f"Error in {self.__class__.__name__}: {e}")
            time.sleep(self.check_interval)
