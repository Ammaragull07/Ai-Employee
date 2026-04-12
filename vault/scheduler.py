"""
Cron-like scheduler for AI Employee - Silver Tier

This script implements basic scheduling functionality for the AI Employee.
It runs scheduled tasks at specified intervals.
"""

import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path
import schedule  # pip install schedule
import logging


def setup_logging():
    """Setup logging for the scheduler"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Path.home() / 'ai_employee_scheduler.log'),
            logging.StreamHandler()
        ]
    )


def run_orchestrator():
    """Run the orchestrator script"""
    try:
        result = subprocess.run(['python', 'orchestrator.py'],
                              capture_output=True, text=True, cwd='.')
        logging.info(f"Orchestrator completed with return code: {result.returncode}")
        if result.stdout:
            logging.info(f"Orchestrator output: {result.stdout}")
        if result.stderr:
            logging.error(f"Orchestrator error: {result.stderr}")
    except Exception as e:
        logging.error(f"Error running orchestrator: {e}")


def run_daily_tasks():
    """Run daily tasks"""
    logging.info("Running daily tasks")
    run_orchestrator()


def run_weekly_tasks():
    """Run weekly tasks"""
    logging.info("Running weekly tasks")
    # Generate weekly briefing
    try:
        # Call the orchestrator to generate weekly briefing
        result = subprocess.run(['python', '-c',
                                'from orchestrator import Orchestrator; o = Orchestrator(); o.generate_weekly_briefing()'],
                               capture_output=True, text=True, cwd='.')
        logging.info(f"Weekly briefing generation completed: {result.returncode}")
    except Exception as e:
        logging.error(f"Error generating weekly briefing: {e}")


def main():
    """Main function to run the scheduler"""
    setup_logging()
    logging.info("Starting AI Employee Scheduler")

    # Schedule tasks
    schedule.every().minute.do(run_orchestrator)  # For testing
    # schedule.every().hour.do(run_orchestrator)  # Uncomment for production
    schedule.every().day.at("07:00").do(run_daily_tasks)
    schedule.every().sunday.at("22:00").do(run_weekly_tasks)

    logging.info("Scheduler started. Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        logging.info("Scheduler stopped by user")


if __name__ == "__main__":
    main()