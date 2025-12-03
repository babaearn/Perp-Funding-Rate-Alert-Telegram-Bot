#!/usr/bin/env python3
"""
Perpetual Funding Rate Alert Bot

Monitors perpetual funding rates and sends Telegram alerts when:
- Funding rate changes significantly
- Funding rate becomes extreme (>0.1%)
- Funding rate flips from positive to negative (or vice versa)

Currently supports: Bybit

Usage:
    python funding_rate_bot.py

Environment variables required:
    TELEGRAM_BOT_TOKEN - Your Telegram bot token from @BotFather
    TELEGRAM_CHAT_ID - Your Telegram chat/group ID
    TELEGRAM_TOPIC_ID - (Optional) Topic ID for supergroups with topics enabled
"""

import asyncio
import logging
import os
import sys
import signal
from datetime import datetime, timezone
from dotenv import load_dotenv

from config import FundingRateConfig, config
from bybit_fetcher import BybitDataFetcher
from funding_monitor import FundingRateMonitor
from telegram_client import TelegramClient

# Load environment variables
load_dotenv()

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FundingRateBot:
    """Main Perpetual Funding Rate Alert Bot"""
    
    def __init__(self):
        """Initialize bot components"""
        logger.info("Initializing Bybit Funding Rate Bot...")
        
        # Load credentials
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.telegram_topic_id = os.getenv("TELEGRAM_TOPIC_ID")
        
        if not self.telegram_token or not self.telegram_chat_id:
            logger.error("Missing Telegram credentials!")
            logger.error("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file")
            sys.exit(1)
        
        # Configuration
        self.config = config
        
        # Initialize components
        self.fetcher = BybitDataFetcher(self.config.BYBIT_BASE_URL)
        self.monitor = FundingRateMonitor(self.config)
        self.telegram = TelegramClient(
            self.telegram_token,
            self.telegram_chat_id,
            topic_id=int(self.telegram_topic_id) if self.telegram_topic_id else None
        )
        
        # Get symbols and their funding intervals
        if self.config.MONITOR_ALL_SYMBOLS:
            logger.info("Fetching ALL perpetual symbols from Bybit...")
            self.symbols_data = self.fetcher.get_all_perpetual_symbols_with_intervals()
            if not self.symbols_data:
                logger.error("Failed to fetch symbols from Bybit!")
                sys.exit(1)
            self.symbols = list(self.symbols_data.keys())
            
            # Count by interval
            self.interval_counts = {}
            for data in self.symbols_data.values():
                interval = str(data.get("fundingIntervalHours", 8))
                self.interval_counts[interval] = self.interval_counts.get(interval, 0) + 1
            
            logger.info(f"Funding intervals: {self.interval_counts}")
        else:
            self.symbols = self.config.SYMBOLS or []
            self.symbols_data = {}
            self.interval_counts = {}
        
        # Bot state
        self.running = True
        self.last_check = None
        
        logger.info(f"Bot initialized. Monitoring {len(self.symbols)} symbols")
        logger.info(f"Symbols: {', '.join(self.symbols[:10])}{'...' if len(self.symbols) > 10 else ''}")
    
    async def run(self):
        """Main bot loop"""
        logger.info("Starting Bybit Funding Rate Bot...")
        
        # Send startup message with interval info
        await self.telegram.send_startup_message(self.symbols, self.interval_counts)
        
        # Setup signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_shutdown)
        
        try:
            await asyncio.gather(
                self.monitoring_loop(),
                self.command_listener(),
                return_exceptions=True
            )
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise
        finally:
            logger.info("Bot shutting down...")
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    async def monitoring_loop(self):
        """Main monitoring loop - checks for new funding settlements"""
        logger.info(f"Starting monitoring loop (interval: {self.config.CHECK_INTERVAL}s = {self.config.CHECK_INTERVAL // 60} min)")
        logger.info("Checking for funding SETTLEMENTS (not predicted rates)")
        
        while self.running:
            try:
                await self.check_funding_settlements()
                self.last_check = datetime.now(timezone.utc)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            
            # Wait for next check
            await asyncio.sleep(self.config.CHECK_INTERVAL)
    
    async def check_funding_settlements(self):
        """Fetch latest settlements and send alerts for new ones"""
        logger.debug("Checking for new funding settlements...")
        
        # Fetch current ticker data (for prices, intervals, etc.)
        ticker_data = self.fetcher.get_tickers(self.symbols)
        
        if not ticker_data:
            logger.warning("No ticker data received from Bybit")
            return
        
        # Add funding interval info to ticker data
        for symbol, data in ticker_data.items():
            if symbol in self.symbols_data:
                data["fundingIntervalHours"] = self.symbols_data[symbol].get("fundingIntervalHours", 8)
        
        # Fetch latest settlement for each symbol
        # This is rate-limited internally
        logger.debug(f"Fetching settlement history for {len(self.symbols)} symbols...")
        settlements = self.fetcher.get_latest_settlements_batch(self.symbols)
        
        if not settlements:
            logger.warning("No settlement data received")
            return
        
        logger.debug(f"Fetched settlements for {len(settlements)} symbols")
        
        # Check for new settlements and generate alerts
        alerts = self.monitor.check_settlements(settlements, ticker_data)
        
        # Send alerts
        for alert in alerts:
            success = await self.telegram.send_funding_alert(alert)
            if success:
                logger.info(f"Alert sent for {alert['symbol']}: {alert['alertType']}")
            else:
                logger.error(f"Failed to send alert for {alert['symbol']}")
            
            # Small delay between alerts to avoid rate limits
            await asyncio.sleep(0.5)
    
    async def command_listener(self):
        """Listen for Telegram commands"""
        import requests
        
        logger.info("Starting command listener...")
        last_update_id = 0
        
        while self.running:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/getUpdates"
                params = {
                    "offset": last_update_id + 1,
                    "timeout": 30
                }
                
                response = requests.get(url, params=params, timeout=35)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("ok"):
                        for update in data.get("result", []):
                            last_update_id = update.get("update_id", last_update_id)
                            await self.handle_command(update)
                
            except requests.exceptions.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error in command listener: {e}")
                await asyncio.sleep(5)
    
    async def handle_command(self, update: dict):
        """Handle incoming Telegram commands"""
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        if not text.startswith("/"):
            return
        
        command = text.split()[0].lower()
        
        if command == "/rates" or command == "/funding":
            # Send current funding rates summary
            rates = self.fetcher.get_tickers(self.symbols)
            await self.telegram.send_summary(rates)
        
        elif command == "/status":
            status_msg = f"""
🤖 <b>Bot Status</b>

<b>Status:</b> {'Running ✅' if self.running else 'Stopped ❌'}
<b>Symbols:</b> {len(self.symbols)}
<b>Last Check:</b> {self.last_check.strftime('%H:%M:%S UTC') if self.last_check else 'Never'}
<b>Check Interval:</b> {self.config.CHECK_INTERVAL}s

<b>Thresholds:</b>
• Min Change: {self.config.MIN_RATE_CHANGE_THRESHOLD * 100:.2f}%
• Extreme Rate: {self.config.EXTREME_RATE_THRESHOLD * 100:.2f}%
"""
            await self.telegram.send_message(status_msg.strip())
        
        elif command == "/help":
            help_msg = """
🤖 <b>Bybit Funding Rate Bot</b>

<b>Commands:</b>
/rates - Show current funding rates
/funding - Same as /rates
/status - Show bot status
/help - Show this message

<b>Alerts:</b>
The bot monitors funding rates and alerts when:
• Rate changes significantly
• Rate becomes extreme (>0.1%)
• Rate flips positive ↔ negative

<i>Funding rates update at 1h/2h/4h/8h intervals</i>
"""
            await self.telegram.send_message(help_msg.strip())


async def main():
    """Main entry point"""
    print("""
╔═══════════════════════════════════════════════════╗
║     Perpetual Funding Rate Alert Bot              ║
║     Monitors perpetual funding rates              ║
╚═══════════════════════════════════════════════════╝
    """)
    
    bot = FundingRateBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
