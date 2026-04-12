# Claude API Setup for AI Employee Auto-Responses

Your AI Employee can now auto-respond to emails using Claude AI!

## ⚙️ Setup Steps

### Step 1: Get Your API Key
1. Go to **https://console.anthropic.com/account/keys**
2. Click **"Create Key"**
3. Copy your new API key (starts with `sk-ant-`)
4. **Keep it secret!** (Never commit to git)

### Step 2: Install Anthropic SDK

Run this command:
```bash
pip install anthropic
```

### Step 3: Set Environment Variable

**Option A: Windows (Command Prompt)**
```cmd
setx ANTHROPIC_API_KEY "your_key_here"
```

**Option B: Windows (PowerShell)**
```powershell
$env:ANTHROPIC_API_KEY = "your_key_here"
```

**Option C: Linux/Mac**
```bash
export ANTHROPIC_API_KEY="your_key_here"
```

### Step 4: Verify Setup

Run this test command:
```bash
cd vault
python -c "import anthropic; print('SUCCESS: Anthropic SDK is installed')"
```

---

## 🚀 How It Works

When you send an email to your inbox:

1. **Gmail Watcher** captures the email
2. **Orchestrator** processes it
3. **Claude AI** generates a smart response
4. **Gmail API** sends the reply automatically
5. **System logs** the exchange for your review

### Email Types It Responds To:
- ✅ Personal emails from friends/family
- ✅ Business inquiries and messages
- ❌ Skips: Auto-replies, notifications, promotions, system alerts
- ❌ Skips: LinkedIn, Google, Amazon, marketing emails

---

## 🧪 Test It

### Send a Test Email

Send yourself a test email from another account with subject like:
```
Hi Ammara, how are you doing?
```

### Run the Test

```bash
cd vault
python test_gmail.py
```

Then run the orchestrator:
```bash
python orchestrator.py
```

You should see:
```
[INFO] Response generated for: Your test email subject
[INFO] Response sent to: your.email@example.com
[INFO] Original email archived to Done
```

---

## 📊 Check Sent Responses

All auto-responses are logged in `Sent_Responses/` folder:

```
Sent_Responses/
├── RESPONSE_20260412_160000_mahrooh.md
├── RESPONSE_20260412_160030_john.md
└── ...
```

Each file contains:
- The original email
- The AI-generated response
- Timestamp and status

---

## ⚙️ Configuration

Edit the email_responder.py to customize:

- **Skip keywords** (line 83-93): Add more senders to skip
- **Response length** (line 123): max_tokens (currently 300)
- **Response tone** (line 118-130): Edit the prompt to change response style
- **Model** (line 35): Change `claude-3-5-sonnet-20241022` to a different model

---

## 🆘 Troubleshooting

### "anthropic module not found"
```bash
pip install anthropic
```

### "ANTHROPIC_API_KEY not set"
Make sure you've set the environment variable correctly. Restart your terminal after setting it.

### "Response not being sent"
Check `Logs/email_responder.log` for errors:
```bash
tail -f vault/Logs/email_responder.log
```

### "Email marked as notification (skipped)"
The system detected it as a notification (LinkedIn, Google, etc.) and skipped it. This is intentional!

---

## ✅ Silver Tier Requirement

Auto-responding to emails completes the "AI functionality" requirement for Silver Tier! ✨
