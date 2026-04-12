{
  "version": "1.1",
  "name": "ai_employee_silver_tier",
  "description": "AI Employee Silver Tier — skills for Gmail monitoring, LinkedIn posting, approval workflows, planning, briefings, and vault management.",
  "skills": [

    {
      "name": "check_gmail",
      "description": "Run a single Gmail check cycle: fetch new unread emails and create action files in Needs_Action/",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["gmail_watcher.py", "--once"]
      }
    },

    {
      "name": "setup_gmail",
      "description": "Open browser to authorize Gmail access (one-time OAuth2 setup)",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["gmail_watcher.py", "--setup"]
      }
    },

    {
      "name": "post_linkedin",
      "description": "Post TEXT directly to LinkedIn without an approval step",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["linkedin_watcher.py", "--post", "{content}"]
      },
      "arguments": [
        {
          "name": "content",
          "type": "string",
          "description": "The text to post on LinkedIn (max 3000 characters)"
        }
      ]
    },

    {
      "name": "queue_linkedin_post",
      "description": "Create a draft LinkedIn post in Pending_Social_Posts/ for approval before publishing",
      "type": "command",
      "definition": {
        "command": "python",
        "args": [
          "-c",
          "import sys, os; from datetime import datetime; from pathlib import Path; content = sys.argv[1]; title = sys.argv[2] if len(sys.argv) > 2 else 'Business Update'; vault = Path('.'); posts_dir = vault / 'Pending_Social_Posts'; posts_dir.mkdir(exist_ok=True); ts = datetime.now().strftime('%Y%m%d_%H%M%S'); fp = posts_dir / f'post_{ts}.md'; fp.write_text(f'---\\ntitle: {title}\\nscheduled: {datetime.now().isoformat()}\\nvisibility: PUBLIC\\n---\\n\\n{content}\\n'); print(f'Post queued for approval: {fp.name}')"
        ]
      },
      "arguments": [
        {
          "name": "content",
          "type": "string",
          "description": "LinkedIn post text (include hashtags for reach)"
        },
        {
          "name": "title",
          "type": "string",
          "description": "Internal title for the post file"
        }
      ]
    },

    {
      "name": "check_linkedin",
      "description": "Run a single LinkedIn watcher cycle: queue new posts and publish approved ones",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["linkedin_watcher.py", "--once"]
      }
    },

    {
      "name": "process_needs_action",
      "description": "Run one orchestrator cycle: process Needs_Action/, execute Approved/, update Dashboard.md",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["orchestrator.py"]
      }
    },

    {
      "name": "send_email",
      "description": "Send an email immediately via the Gmail API (use draft_email for external contacts)",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["email_mcp_server.py", "--test-send", "--to", "{to}", "--subject", "{subject}", "--body", "{body}"]
      },
      "arguments": [
        {"name": "to",      "type": "string", "description": "Recipient email address"},
        {"name": "subject", "type": "string", "description": "Email subject line"},
        {"name": "body",    "type": "string", "description": "Email body text"}
      ]
    },

    {
      "name": "draft_email",
      "description": "Create an email draft in Pending_Approval/ for human review before sending",
      "type": "command",
      "definition": {
        "command": "python",
        "args": [
          "-c",
          "import sys; from email_mcp_server import EmailMCPServer; s = EmailMCPServer(); r = s.draft_email({'to': sys.argv[1], 'subject': sys.argv[2], 'body': sys.argv[3], 'reason': sys.argv[4] if len(sys.argv) > 4 else 'Outgoing email'}); print(r['message'])"
        ]
      },
      "arguments": [
        {"name": "to",      "type": "string", "description": "Recipient email address"},
        {"name": "subject", "type": "string", "description": "Email subject line"},
        {"name": "body",    "type": "string", "description": "Email body text"},
        {"name": "reason",  "type": "string", "description": "Why this email needs to be sent"}
      ]
    },

    {
      "name": "create_approval_request",
      "description": "Create an approval request file in Pending_Approval/ for any sensitive action",
      "type": "command",
      "definition": {
        "command": "python",
        "args": [
          "-c",
          "import sys; from datetime import datetime; from pathlib import Path; action = sys.argv[1]; details = sys.argv[2]; reason = sys.argv[3] if len(sys.argv) > 3 else 'Action requires review'; ts = datetime.now().strftime('%Y%m%d_%H%M%S'); fp = Path('Pending_Approval') / f'APPROVAL_REQUIRED_{action.upper()}_{ts}.md'; Path('Pending_Approval').mkdir(exist_ok=True); fp.write_text(f'---\\ntype: approval_request\\naction: {action}\\nreason: {reason}\\ncreated: {datetime.now().isoformat()}\\nstatus: pending\\n---\\n\\n# Approval Required: {action.title()}\\n\\n## Details\\n{details}\\n\\n## Reason\\n{reason}\\n\\n**To approve:** Move to `/Approved`\\n**To reject:** Move to `/Rejected`'); print(f'Approval request created: {fp.name}')"
        ]
      },
      "arguments": [
        {"name": "action",  "type": "string", "description": "Action type (e.g. payment, email_send, social_post)"},
        {"name": "details", "type": "string", "description": "Full details of the action"},
        {"name": "reason",  "type": "string", "description": "Why approval is required"}
      ]
    },

    {
      "name": "create_plan",
      "description": "Create a Plan.md in Plans/ for a multi-step task",
      "type": "command",
      "definition": {
        "command": "python",
        "args": [
          "-c",
          "import sys; from datetime import datetime; from pathlib import Path; name = sys.argv[1]; obj = sys.argv[2]; steps = [s.strip() for s in sys.argv[3].split('|')] if len(sys.argv) > 3 else ['Step 1']; ts = datetime.now().strftime('%Y%m%d_%H%M%S'); fp = Path('Plans') / f'PLAN_{name.upper()}_{ts}.md'; Path('Plans').mkdir(exist_ok=True); steps_md = chr(10).join(f'- [ ] {s}' for s in steps); fp.write_text(f'---\\ncreated: {datetime.now().isoformat()}\\nstatus: in_progress\\n---\\n\\n# Plan: {name}\\n\\n## Objective\\n{obj}\\n\\n## Steps\\n{steps_md}\\n'); print(f'Plan created: {fp.name}')"
        ]
      },
      "arguments": [
        {"name": "name",      "type": "string", "description": "Short plan name (used in filename)"},
        {"name": "objective", "type": "string", "description": "What this plan should achieve"},
        {"name": "steps",     "type": "string", "description": "Steps separated by '|' — e.g. 'Draft reply|Get approval|Send email'"}
      ]
    },

    {
      "name": "generate_briefing",
      "description": "Generate a CEO briefing (daily or weekly) and save to Briefings/",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["orchestrator.py", "--briefing", "{period}"]
      },
      "arguments": [
        {
          "name": "period",
          "type": "string",
          "description": "Briefing period: 'daily' or 'weekly'"
        }
      ]
    },

    {
      "name": "update_dashboard",
      "description": "Refresh Dashboard.md with current vault status",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["-c", "from orchestrator import Orchestrator; Orchestrator().update_dashboard(); print('Dashboard updated.')"]
      }
    },

    {
      "name": "check_approval_status",
      "description": "Show counts of pending, approved, and rejected items",
      "type": "command",
      "definition": {
        "command": "python",
        "args": [
          "-c",
          "from pathlib import Path; folders = {'Pending': 'Pending_Approval', 'Approved': 'Approved', 'Rejected': 'Rejected'}; [print(f'{label}: {len(list(Path(d).glob(\"*.md\") if Path(d).exists() else []))}') for label, d in folders.items()]"
        ]
      }
    },

    {
      "name": "start_all_watchers",
      "description": "Launch all watchers and the orchestrator as background processes",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["run_all.py"]
      }
    },

    {
      "name": "stop_all_watchers",
      "description": "Stop all running watcher processes",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["run_all.py", "--stop"]
      }
    },

    {
      "name": "watcher_status",
      "description": "Show status of all running watcher processes",
      "type": "command",
      "definition": {
        "command": "python",
        "args": ["run_all.py", "--status"]
      }
    }

  ]
}
