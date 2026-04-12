# AI Employee - Silver Tier Implementation

This project implements the Silver Tier requirements for the Personal AI Employee Hackathon. The AI Employee is designed to act as a digital full-time equivalent employee, operating 24/7 to manage personal and business affairs.

## Silver Tier Features

The Silver Tier includes all Bronze Tier features plus:

1. **Multiple Watcher Scripts**:
   - Gmail Watcher (existing from Bronze)
   - WhatsApp Watcher (new)
   - LinkedIn Watcher (new)
   - File System Watcher (existing from Bronze)

2. **Automatic LinkedIn Posting**:
   - Automatically generates and posts business updates to LinkedIn
   - Implements approval workflow for social media posts

3. **Claude Reasoning Loop**:
   - Creates Plan.md files for multi-step tasks
   - Implements sophisticated reasoning patterns

4. **MCP Server Integration**:
   - Email MCP server for sending emails
   - Standardized interface for Claude Code to interact with external systems

5. **Human-in-the-Loop Approval**:
   - Approval workflow for sensitive actions
   - File-based approval system (Pending_Approval, Approved, Rejected folders)

6. **Scheduling**:
   - Basic scheduling via cron-like functionality
   - Daily and weekly briefing generation

7. **Agent Skills**:
   - All AI functionality implemented as reusable skills
   - Enhanced SKILL.md with silver tier capabilities

## Architecture

The system follows the architecture outlined in the hackathon document:

```
┌─────────────────────────────────────────────────────────────────┐  
│                    EXTERNAL SOURCES                           │  
├─────────────────┬─────────────────┬─────────────────────────────┤  
│     Gmail       │    WhatsApp     │     Bank APIs    │  Files   │  
└────────┬────────┴────────┬────────┴─────────┬────────┴────┬─────┘  
         │                 │                  │             │        
         ▼                 ▼                  ▼             ▼        
┌─────────────────────────────────────────────────────────────────┐  
│                    PERCEPTION LAYER                             │  
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │  
│  │ Gmail Watcher│ │WhatsApp Watch│ │Finance Watcher│            │  
│  │  (Python)    │ │ (Playwright) │ │   (Python)   │            │  
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘            │  
└─────────┼────────────────┼────────────────┼────────────────────┘  
          │                │                │                        
          ▼                ▼                ▼                        
┌─────────────────────────────────────────────────────────────────┐  
│                    OBSIDIAN VAULT (Local)                       │  
│  ┌──────────────────────────────────────────────────────────┐  │  
│  │ /Needs_Action/  │ /Plans/  │ /Done/  │ /Logs/            │  │  
│  ├──────────────────────────────────────────────────────────┤  │  
│  │ Dashboard.md    │ Company_Handbook.md │ Business_Goals.md│  │  
│  ├──────────────────────────────────────────────────────────┤  │  
│  │ /Pending_Approval/  │  /Approved/  │  /Rejected/         │  │  
│  └──────────────────────────────────────────────────────────┘  │  
└────────────────────────────────┬────────────────────────────────┘  
                                 │                                   
                                 ▼                                   
┌─────────────────────────────────────────────────────────────────┐  
│                    REASONING LAYER                              │  
│  ┌───────────────────────────────────────────────────────────┐ │  
│  │                      CLAUDE CODE                          │ │  
│  │   Read → Think → Plan → Write → Request Approval          │ │  
│  └───────────────────────────────────────────────────────────┘ │  
└────────────────────────────────┬────────────────────────────────┘  
                                 │                                   
              ┌──────────────────┴───────────────────┐               
              ▼                                      ▼               
┌────────────────────────────┐    ┌────────────────────────────────┐  
│    HUMAN-IN-THE-LOOP       │    │         ACTION LAYER           │  
│  ┌──────────────────────┐  │    │  ┌─────────────────────────┐   │  
│  │ Review Approval Files│──┼───▶│  │    MCP SERVERS          │   │  
│  │ Move to /Approved    │  │    │  │  ┌──────┐ ┌──────────┐  │   │  
│  └──────────────────────┘  │    │  │  │Email │ │ Browser  │  │   │  
│                            │    │  │  │ MCP  │ │   MCP    │  │   │  
└────────────────────────────┘    │  │  └──┬───┘ └────┬─────┘  │   │  
                                  │  └─────┼──────────┼────────┘   │  
                                  └────────┼──────────┼────────────┘  
                                           │          │               
                                           ▼          ▼               
                                  ┌────────────────────────────────┐  
                                  │     EXTERNAL ACTIONS           │  
                                  │  Send Email │ Make Payment     │  
                                  │  Post Social│ Update Calendar  │  
                                  └────────────────────────────────┘
```

## Setup

1. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure your vault directory with proper folder structure

3. Set up your MCP servers as needed

4. Run the orchestrator:
   ```bash
   python orchestrator.py --continuous
   ```

## Files and Directories

- `SKILL.md`: Defines all available skills for the AI Employee
- `orchestrator.py`: Main orchestrator that manages the workflow
- `scheduler.py`: Handles scheduled tasks
- `linkedin_watcher.py`: Monitors and posts to LinkedIn
- `whatsapp_watcher.py`: Monitors WhatsApp messages
- `email_mcp_server.py`: MCP server for email functionality
- `Company_Handbook.md`: Rules and guidelines for the AI Employee
- `Business_Goals.md`: Business objectives and metrics
- `Dashboard.md`: Current status dashboard

## Usage

The AI Employee operates automatically by monitoring the `/Needs_Action` folder for new tasks. When a task is detected, it processes the task according to the rules in `Company_Handbook.md`. For sensitive actions, it creates approval requests in the `/Pending_Approval` folder which must be moved to `/Approved` or `/Rejected` by a human operator.

## Silver Tier Requirements Met

✅ All Bronze requirements  
✅ Two or more Watcher scripts (Gmail, WhatsApp, LinkedIn, File System)  
✅ Automatic LinkedIn posting for business generation  
✅ Claude reasoning loop that creates Plan.md files  
✅ One working MCP server (Email MCP)  
✅ Human-in-the-loop approval workflow  
✅ Basic scheduling via cron/scheduler  
✅ All AI functionality implemented as Agent Skills