"""
filesystem_watcher.py
Basic file system watcher for the AI Employee Hackathon Bronze Tier
Monitors a designated drop folder and creates action files in Needs_Action when new files appear.
"""

import time
import logging
from pathlib import Path
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class DropFolderHandler(FileSystemEventHandler):
    """Handles file system events in the monitored folder."""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / 'Needs_Action'
        self.inbox = self.vault_path / 'Inbox'
        self.setup_logging()

    def setup_logging(self):
        """Setup basic logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.vault_path / 'Logs' / 'watcher.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return

        source = Path(event.src_path)
        self.logger.info(f"New file detected: {source.name}")

        # Copy file to inbox
        dest = self.inbox / source.name
        try:
            shutil.copy2(source, dest)
            self.logger.info(f"Copied file to inbox: {dest}")

            # Create metadata file in Needs_Action
            self.create_metadata_file(source, dest)
        except Exception as e:
            self.logger.error(f"Error processing file {source}: {str(e)}")

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        source = Path(event.src_path)
        self.logger.info(f"File modified: {source.name}")

    def create_metadata_file(self, source: Path, dest: Path):
        """Create a metadata file in Needs_Action to trigger AI processing."""
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        meta_filename = f"FILE_DROP_{timestamp}_{source.name}.md"
        meta_path = self.needs_action / meta_filename

        metadata_content = f"""---
type: file_drop
original_name: {source.name}
destination_path: {dest}
size_bytes: {source.stat().st_size}
detected_at: {time.strftime('%Y-%m-%d %H:%M:%S')}
status: pending
priority: medium
---

# New File Dropped for Processing

## File Information
- **Original Name:** {source.name}
- **Size:** {source.stat().st_size} bytes
- **Detected At:** {time.strftime('%Y-%m-%d %H:%M:%S')}

## File Content Preview
```
{self.read_file_preview(source)}
```

## Suggested Actions
- [ ] Review file content
- [ ] Determine appropriate action
- [ ] Process or categorize file
- [ ] Update Dashboard.md

## Notes
This file was detected in the monitored folder and requires processing.
"""

        meta_path.write_text(metadata_content)
        self.logger.info(f"Created metadata file: {meta_path}")

    def read_file_preview(self, source: Path, max_lines=10):
        """Read a preview of the file content."""
        try:
            with open(source, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append("... (truncated)")
                        break
                    lines.append(line.rstrip())
                return "\\n".join(lines)
        except Exception:
            return "[Unable to read file content - may be binary]"


def start_watcher(watch_path: str, vault_path: str):
    """Start the file system watcher."""
    observer = Observer()
    handler = DropFolderHandler(vault_path)

    watch_path = Path(watch_path)
    observer.schedule(handler, str(watch_path), recursive=False)

    observer.start()
    print(f"File system watcher started. Monitoring: {watch_path}")
    print(f"Vault path: {vault_path}")
    print("Press Ctrl+C to stop...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\\nStopping file system watcher...")

    observer.join()


if __name__ == "__main__":
    import sys

    # Default paths - can be overridden via command line
    VAULT_PATH = "."
    WATCH_PATH = "./DropFolder"  # Create this folder separately

    # Create the drop folder if it doesn't exist
    drop_folder = Path(WATCH_PATH)
    drop_folder.mkdir(exist_ok=True)

    print(f"Creating drop folder: {drop_folder.absolute()}")

    # Start watching
    start_watcher(WATCH_PATH, VAULT_PATH)