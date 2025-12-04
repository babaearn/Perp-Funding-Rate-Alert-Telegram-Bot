#!/usr/bin/env python3
"""
Funding Rate Alert Monitor

This runs as a separate process and ONLY handles alert monitoring.
Commands are handled by command_handler.py
"""

import asyncio
import logging
import os
import sys
import signal
from datetime import datetime, timezone
from dotenv import load_dotenv

from config import config
from bybit_fetcher import BybitDataFetcher
from funding_monitor import FundingRateMonitor
from telegram_client import TelegramClient

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


class AlertMonitor:
    """Monitors funding rates and sends alerts - NO command handling"""
    
    def __init__(self):
        logger.info("Initializing Alert Monitor...")
        
        # Load credentials
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.telegram_topic_id = os.getenv("TELEGRAM_TOPIC_ID")
        
        if not self.telegram_token or not self.telegram_chat_id:
            logger.error("Missing Telegram credentials!")
            sys.exit(1)
        
        # Initialize components
        self.fetcher = BybitDataFetcher(config.BYBIT_BASE_URL)
        self.monitor = FundingRateMonitor(config)
        self.telegram = TelegramClient(
            self.telegram_token,
            self.telegram_chat_id,
            topic_id=int(self.telegram_topic_id) if self.telegram_topic_id else None
        )
        
        # Get symbols
        logger.info("Fetching ALL perpetual symbols from Bybit...")
        self.symbols_data = self.fetcher.get_all_perpetual_symbols_with_intervals()
        if not self.symbols_data:
            logger.error("Failed to fetch symbols!")
            sys.exit(1)
        
        self.symbols = list(self.symbols_data.keys())
        logger.info(f"Monitoring {len(self.symbols)} symbols")
        
        # State
        self.running = True
        self.last_symbol_refresh = datetime.now(timezone.utc)
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
    
    def _shutdown(self, signum, frame):
        logger.info("Shutting down...")
        self.running = False
    
    async def run(self):
        """Main monitoring loop"""
        logger.info(f"Starting monitoring loop (interval: {config.CHECK_INTERVAL}s)")
        
        while self.running:
            try:
                # Refresh symbols every 24 hours
                time_since_refresh = (datetime.now(timezone.utc) - self.last_symbol_refresh).total_seconds()
                if time_since_refresh >= 86400:
                    self._refresh_symbols()
                
                # Check for funding events
                await self._check_funding()
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            
            # Wait for next check
            await asyncio.sleep(config.CHECK_INTERVAL)
    
    def _refresh_symbols(self):
        """Refresh symbol list"""
        logger.info("Refreshing symbols...")
        new_data = self.fetcher.get_all_perpetual_symbols_with_intervals()
        if new_data:
            self.symbols_data = new_data
            self.symbols = list(new_data.keys())
            self.last_symbol_refresh = datetime.now(timezone.utc)
            logger.info(f"Now monitoring {len(self.symbols)} symbols")
    
    async def _check_funding(self):
        """Check for funding alerts"""
        # Fetch ticker data
        ticker_data = self.fetcher.get_tickers(self.symbols)
        if not ticker_data:
            return
        
        # Add interval info
        for symbol, data in ticker_data.items():
            if symbol in self.symbols_data:
                data["fundingIntervalHours"] = self.symbols_data[symbol].get("fundingIntervalHours", 8)
        
        # Fetch settlements
        settlements = self.fetcher.get_latest_settlements_batch(self.symbols)
        if not settlements:
            return
        
        # Check for settlement alerts
        alerts = self.monitor.check_settlements(settlements, ticker_data)
        
        # Clear predicted tracking for settled symbols
        for alert in alerts:
            self.monitor.clear_predicted_alerts_after_settlement(alert['symbol'])
        
        # Check predicted rates
        predicted_alerts = self.monitor.check_predicted_rates(ticker_data)
        
        # Limit to top 5 extreme
        if len(predicted_alerts) > 5:
            predicted_alerts = sorted(
                predicted_alerts,
                key=lambda x: abs(x.get('fundingRate', 0)),
                reverse=True
            )[:5]
        
        # Send alerts
        all_alerts = alerts + predicted_alerts
        for alert in all_alerts:
            success = await self.telegram.send_funding_alert(alert)
            if success:
                logger.info(f"Alert sent: {alert['symbol']} ({alert['alertType']})")
            await asyncio.sleep(0.3)


async def main():
    print("""
╔═══════════════════════════════════════════════════╗
║        Funding Rate Alert Monitor                 ║
╚═══════════════════════════════════════════════════╝
    """)
    
    monitor = AlertMonitor()
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
