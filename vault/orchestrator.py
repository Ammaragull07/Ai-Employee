"""
orchestrator.py
Simple orchestrator for the AI Employee Bronze Tier
Manages the flow between watchers, Claude processing, and actions.
"""

import time
import os
from pathlib import Path
import logging
from datetime import datetime


class AI_Employee_Orchestrator:
    """Main orchestrator for the AI Employee system."""

    def __init__(self, vault_path="."):
        self.vault_path = Path(vault_path)
        self.setup_logging()
        self.setup_folders()

    def setup_logging(self):
        """Setup logging for the orchestrator."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.vault_path / 'Logs' / 'orchestrator.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    def setup_folders(self):
        """Ensure all required folders exist."""
        folders = ['Inbox', 'Needs_Action', 'Done', 'Plans', 'Pending_Approval', 'Logs']
        for folder in folders:
            path = self.vault_path / folder
            path.mkdir(exist_ok=True)
            self.logger.info(f"Ensured folder exists: {path}")

    def check_needs_action(self):
        """Check for files in Needs_Action folder."""
        needs_action_dir = self.vault_path / 'Needs_Action'
        files = list(needs_action_dir.glob('*.md'))
        self.logger.info(f"Found {len(files)} files in Needs_Action")
        return files

    def process_needs_action_files(self):
        """Process files in the Needs_Action folder."""
        files = self.check_needs_action()

        for file_path in files:
            self.logger.info(f"Processing: {file_path.name}")

            # Read the file content
            content = file_path.read_text()
            self.logger.info(f"File content preview: {content[:200]}...")

            # Determine what action is needed based on file content
            action_taken = self.determine_and_perform_action(file_path, content)

            if action_taken:
                # Move file to Done folder after processing
                done_path = self.vault_path / 'Done' / file_path.name
                file_path.rename(done_path)
                self.logger.info(f"Moved {file_path.name} to Done folder")

                # Update dashboard
                self.update_dashboard(f"Processed: {file_path.name}")

    def determine_and_perform_action(self, file_path, content):
        """Determine what action to perform based on file content."""
        # This is where Claude Code would normally do the reasoning
        # For Bronze Tier, we'll implement basic logic

        if 'email' in content.lower():
            self.logger.info(f"Identified email-related task in {file_path.name}")
            return self.handle_email_task(file_path, content)
        elif 'file_drop' in content.lower():
            self.logger.info(f"Identified file drop task in {file_path.name}")
            return self.handle_file_task(file_path, content)
        else:
            self.logger.info(f"Generic task in {file_path.name}")
            return self.handle_generic_task(file_path, content)

    def handle_email_task(self, file_path, content):
        """Handle email-related tasks."""
        # In a real implementation, this would interface with an email MCP
        self.logger.info(f"Handling email task from {file_path.name}")
        return True

    def handle_file_task(self, file_path, content):
        """Handle file-related tasks."""
        self.logger.info(f"Handling file task from {file_path.name}")
        return True

    def handle_generic_task(self, file_path, content):
        """Handle generic tasks."""
        self.logger.info(f"Handling generic task from {file_path.name}")
        return True

    def update_dashboard(self, action_description):
        """Update the dashboard with the latest action."""
        dashboard_path = self.vault_path / 'Dashboard.md'

        if dashboard_path.exists():
            content = dashboard_path.read_text()
        else:
            content = "# Dashboard.md\\n\\n## AI Employee Dashboard\\n\\n"

        # Find and update stats
        lines = content.split('\\n')
        updated_lines = []
        for line in lines:
            if line.startswith('- **Tasks Processed:**'):
                # Extract current count and increment
                try:
                    current_count = int(line.split(': ')[1])
                    updated_lines.append(f'- **Tasks Processed:** {current_count + 1}')
                except:
                    updated_lines.append(f'- **Tasks Processed:** 1')
            elif line.startswith('- **Date:**'):
                updated_lines.append(f'- **Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            elif line.startswith('### Recent Activity'):
                updated_lines.append('### Recent Activity')
                updated_lines.append(f'- {datetime.now().strftime("%H:%M")} - {action_description}')
            else:
                updated_lines.append(line)

        # Write updated content
        dashboard_path.write_text('\\n'.join(updated_lines))
        self.logger.info("Dashboard updated")

    def run_once(self):
        """Run one cycle of processing."""
        self.logger.info("Starting processing cycle")
        self.process_needs_action_files()
        self.logger.info("Completed processing cycle")

    def run_continuous(self, interval=30):
        """Run continuously with specified interval."""
        self.logger.info(f"Starting continuous operation (checking every {interval}s)")
        try:
            while True:
                self.run_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            self.logger.info("Shutting down orchestrator")


def main():
    """Main function to run the orchestrator."""
    print("Initializing AI Employee Orchestrator...")
    orchestrator = AI_Employee_Orchestrator()

    # For Bronze Tier, we'll just run one cycle to demonstrate functionality
    orchestrator.run_once()
    print("Orchestrator completed one cycle. Bronze Tier functionality demonstrated.")


if __name__ == "__main__":
    main()