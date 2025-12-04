#!/usr/bin/env python3
"""
Unified starter for Railway deployment.
Runs both command_handler and alert_monitor in the same process using asyncio.
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Setup logging
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def run_command_handler():
    """Run the command handler"""
    from command_handler import CommandHandler
    handler = CommandHandler()
    await handler.start()


async def run_alert_monitor():
    """Run the alert monitor"""
    from alert_monitor import AlertMonitor
    monitor = AlertMonitor()
    await monitor.run()


async def main():
    print("""
╔═══════════════════════════════════════════════════╗
║     Perpetual Funding Rate Alert Bot              ║
║     Powered by Mudrex Market Intelligence         ║
╚═══════════════════════════════════════════════════╝
    """)
    
    logger.info("Starting both Command Handler and Alert Monitor...")
    
    # Run both concurrently
    await asyncio.gather(
        run_command_handler(),
        run_alert_monitor()
    )


if __name__ == "__main__":
    asyncio.run(main())
