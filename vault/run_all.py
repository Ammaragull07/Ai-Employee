"""
run_all.py - Master Launcher for AI Employee Silver Tier

Starts all watchers and the orchestrator as separate background processes,
monitors their health, and restarts them if they crash.

USAGE:
    python run_all.py           # Start everything
    python run_all.py --status  # Show running processes
    python run_all.py --stop    # Stop all processes

All processes write to Logs/ so you can monitor them in Obsidian.
"""

import subprocess
import sys
import time
import json
import signal
import os
from pathlib import Path
from datetime import datetime

VAULT_PATH = Path(__file__).parent
LOGS_PATH = VAULT_PATH / 'Logs'
PID_FILE = LOGS_PATH / 'running_processes.json'

PYTHON = sys.executable  # Use the same Python that launched this script

# ── Process definitions ──────────────────────────────────────────────────────
PROCESSES = {
    'orchestrator': {
        'cmd': [PYTHON, 'orchestrator.py', '--watch', '--interval', '60'],
        'description': 'Master coordinator — processes Needs_Action, executes approvals',
        'restart_delay': 5,
    },
    'gmail_watcher': {
        'cmd': [PYTHON, 'gmail_watcher.py', '--interval', '120'],
        'description': 'Gmail monitor — checks inbox every 2 minutes',
        'restart_delay': 10,
    },
    'linkedin_watcher': {
        'cmd': [PYTHON, 'linkedin_watcher.py', '--interval', '300'],
        'description': 'LinkedIn monitor — checks Pending_Social_Posts every 5 minutes',
        'restart_delay': 10,
    },
    'filesystem_watcher': {
        'cmd': [PYTHON, 'filesystem_watcher.py'],
        'description': 'File system monitor — watches DropFolder in real time',
        'restart_delay': 3,
    },
}

running: dict[str, subprocess.Popen] = {}


def log(msg: str):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}")


def start_process(name: str) -> subprocess.Popen:
    """Start a named process and return its Popen handle."""
    cfg = PROCESSES[name]
    log_file = open(LOGS_PATH / f"{name}.log", 'a')
    proc = subprocess.Popen(
        cfg['cmd'],
        cwd=str(VAULT_PATH),
        stdout=log_file,
        stderr=log_file,
    )
    log(f"  Started {name} (PID {proc.pid}) — {cfg['description']}")
    return proc


def save_pids():
    pids = {name: proc.pid for name, proc in running.items()}
    PID_FILE.write_text(json.dumps(pids, indent=2))


def stop_all():
    """Terminate all running processes."""
    log("Stopping all processes...")
    for name, proc in list(running.items()):
        try:
            proc.terminate()
            proc.wait(timeout=5)
            log(f"  Stopped {name} (PID {proc.pid})")
        except Exception as e:
            log(f"  Could not stop {name}: {e}")
            try:
                proc.kill()
            except Exception:
                pass
    running.clear()
    if PID_FILE.exists():
        PID_FILE.unlink()


def show_status():
    """Print current process status."""
    if not PID_FILE.exists():
        print("No running processes found.")
        return
    pids = json.loads(PID_FILE.read_text())
    print(f"\nAI Employee — Process Status ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("-" * 60)
    for name, pid in pids.items():
        # Check if process is alive
        try:
            os.kill(pid, 0)
            status = f"RUNNING (PID {pid})"
        except (ProcessLookupError, PermissionError):
            status = f"STOPPED (was PID {pid})"
        print(f"  {name:<25} {status}")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='AI Employee Master Launcher')
    parser.add_argument('--status', action='store_true', help='Show process status')
    parser.add_argument('--stop', action='store_true', help='Stop all processes')
    parser.add_argument('--no-whatsapp', action='store_true',
                        help='Skip WhatsApp watcher (requires Playwright session setup)')
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.stop:
        # Try to stop via saved PIDs
        if PID_FILE.exists():
            pids = json.loads(PID_FILE.read_text())
            for name, pid in pids.items():
                try:
                    os.kill(pid, signal.SIGTERM)
                    log(f"Sent SIGTERM to {name} (PID {pid})")
                except Exception as e:
                    log(f"Could not stop {name}: {e}")
            PID_FILE.unlink(missing_ok=True)
        else:
            log("No PID file found — nothing to stop.")
        return

    # ── Startup ──────────────────────────────────────────────────────────────
    LOGS_PATH.mkdir(exist_ok=True)

    print("=" * 60)
    print("  AI Employee — Silver Tier")
    print(f"  Vault: {VAULT_PATH.absolute()}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # Check Gmail token before starting
    token_file = VAULT_PATH / 'token.json'
    if not token_file.exists():
        print("WARNING: Gmail not authorized yet.")
        print("  Run first: python gmail_watcher.py --setup")
        print("  (Gmail watcher will skip silently until authorized)")
        print()

    # Check LinkedIn credentials
    env_file = VAULT_PATH / '.env'
    if not env_file.exists():
        print("WARNING: .env file not found.")
        print("  Copy .env.example to .env and add your LinkedIn credentials.")
        print("  (LinkedIn watcher will run in approval-only mode)")
        print()

    # Register signal handlers for clean shutdown
    def _handle_signal(sig, frame):
        print("\nShutdown signal received...")
        stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Start all processes
    processes_to_start = list(PROCESSES.keys())
    if args.no_whatsapp and 'whatsapp_watcher' in processes_to_start:
        processes_to_start.remove('whatsapp_watcher')

    print("Starting processes:")
    for name in processes_to_start:
        running[name] = start_process(name)
        time.sleep(0.5)  # stagger starts

    save_pids()
    print()
    print("All processes started. Logs → vault/Logs/")
    print("Press Ctrl+C to stop all.\n")

    # ── Watchdog loop ────────────────────────────────────────────────────────
    while True:
        time.sleep(15)
        for name in list(running.keys()):
            proc = running[name]
            if proc.poll() is not None:  # Process exited
                delay = PROCESSES[name]['restart_delay']
                log(f"RESTART: {name} exited (code {proc.returncode}). Restarting in {delay}s...")
                time.sleep(delay)
                running[name] = start_process(name)
                save_pids()


if __name__ == '__main__':
    main()
