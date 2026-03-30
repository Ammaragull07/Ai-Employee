# AI Employee - Bronze Tier Implementation

This project implements the Bronze Tier requirements for the Personal AI Employee Hackathon.

## Features Implemented

1. **Obsidian Vault Structure**
   - Dashboard.md - Main dashboard with status information
   - Company_Handbook.md - Rules and guidelines for the AI Employee
   - Basic folder structure: Inbox, Needs_Action, Done, Plans, Pending_Approval, Logs

2. **File System Watcher**
   - Monitors a designated folder for new files
   - Creates action files in Needs_Action when new files are detected
   - Generates metadata for each detected file

3. **Orchestrator**
   - Processes files in the Needs_Action folder
   - Updates the Dashboard with current status
   - Moves processed files to the Done folder

4. **Agent Skills**
   - Demonstrates AI functionality through command-line skills
   - Shows how the AI reads from and writes to the vault

## Setup Instructions

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create a drop folder for the file watcher:
   ```
   mkdir DropFolder
   ```

3. Run the file system watcher:
   ```
   python filesystem_watcher.py
   ```

4. Run the orchestrator to process actions:
   ```
   python orchestrator.py
   ```

## Bronze Tier Requirements Met

✅ Obsidian vault with Dashboard.md and Company_Handbook.md
✅ One working Watcher script (File System Monitor)
✅ Claude Code successfully reading from and writing to the vault
✅ Basic folder structure: /Inbox, /Needs_Action, /Done
✅ All AI functionality implemented as Agent Skills (demonstrated)