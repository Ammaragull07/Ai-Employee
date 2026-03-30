{
  "version": "1.0",
  "name": "ai_employee_bronze_tier",
  "description": "Basic AI Employee functionality for Bronze Tier",
  "skills": [
    {
      "name": "process_needs_action",
      "description": "Process files in the Needs_Action folder",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["-c", "import os; import glob; files = glob.glob('./Needs_Action/*.md'); print(f'Found {len(files)} files needing action'); [print(f'- {os.path.basename(f)}') for f in files]"]
      }
    },
    {
      "name": "update_dashboard",
      "description": "Update the dashboard with current status",
      "type": "command",
      "definition": {
        "command": "python",
        "args": [
          "-c",
          "import datetime; import os; from pathlib import Path; dashboard_path = Path('Dashboard.md'); content = dashboard_path.read_text(); lines = content.split('\\n'); updated_lines = []; for line in lines: updated_lines.append('# Updated: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') if line.startswith('# Updated:') else line); Path('Dashboard.md').write_text('\\n'.join(updated_lines)); print('Dashboard updated')"
        ]
      }
    }
  ]
}