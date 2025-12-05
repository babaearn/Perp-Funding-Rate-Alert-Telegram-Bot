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
        logger.info("Initializing Funding Rate Bot...")
        
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
        self.last_symbol_refresh = datetime.now(timezone.utc)
        self.symbol_refresh_interval = 86400  # 24 hours in seconds
        
        logger.info(f"Bot initialized. Monitoring {len(self.symbols)} symbols")
        logger.info(f"Symbols: {', '.join(self.symbols[:10])}{'...' if len(self.symbols) > 10 else ''}")
    
    def refresh_symbols(self):
        """Refresh the list of symbols from the exchange (for new listings/delistings)"""
        if not self.config.MONITOR_ALL_SYMBOLS:
            return
        
        logger.info("Refreshing symbol list from Bybit...")
        new_symbols_data = self.fetcher.get_all_perpetual_symbols_with_intervals()
        
        if not new_symbols_data:
            logger.warning("Failed to refresh symbols, keeping existing list")
            return
        
        old_count = len(self.symbols)
        old_symbols = set(self.symbols)
        new_symbols = set(new_symbols_data.keys())
        
        # Detect changes
        added = new_symbols - old_symbols
        removed = old_symbols - new_symbols
        
        if added:
            logger.info(f"New listings detected: {', '.join(sorted(added))}")
        if removed:
            logger.info(f"Delistings detected: {', '.join(sorted(removed))}")
        
        # Update
        self.symbols_data = new_symbols_data
        self.symbols = list(new_symbols_data.keys())
        
        # Update interval counts
        self.interval_counts = {}
        for data in self.symbols_data.values():
            interval = str(data.get("fundingIntervalHours", 8))
            self.interval_counts[interval] = self.interval_counts.get(interval, 0) + 1
        
        self.last_symbol_refresh = datetime.now(timezone.utc)
        logger.info(f"Symbol refresh complete. Now monitoring {len(self.symbols)} symbols (was {old_count})")
    
    async def run(self):
        """Main bot loop"""
        logger.info("Starting Funding Rate Bot...")
        
        # Send startup message with interval info
        await self.telegram.send_startup_message(self.symbols, self.interval_counts)
        
        # Setup signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_shutdown)
        
        # Start command listener IMMEDIATELY (don't wait for first check)
        logger.info("Starting command listener...")
        
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
        logger.info(f"Symbol list will refresh every {self.symbol_refresh_interval // 3600} hours")
        
        while self.running:
            try:
                # Check if we need to refresh the symbol list (every 24 hours)
                time_since_refresh = (datetime.now(timezone.utc) - self.last_symbol_refresh).total_seconds()
                if time_since_refresh >= self.symbol_refresh_interval:
                    self.refresh_symbols()
                
                await self.check_funding_settlements()
                self.last_check = datetime.now(timezone.utc)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            
            # Wait for next check
            await asyncio.sleep(self.config.CHECK_INTERVAL)
    
    async def check_funding_settlements(self):
        """Fetch latest settlements and send alerts for new ones"""
        logger.debug("Checking for new funding settlements...")
        
        # Run blocking fetcher in thread pool to not block async loop
        loop = asyncio.get_event_loop()
        ticker_data = await loop.run_in_executor(None, self.fetcher.get_tickers, self.symbols)
        
        if not ticker_data:
            logger.warning("No ticker data received from Bybit")
            return
        
        # Add funding interval info to ticker data
        for symbol, data in ticker_data.items():
            if symbol in self.symbols_data:
                data["fundingIntervalHours"] = self.symbols_data[symbol].get("fundingIntervalHours", 8)
        
        # Fetch latest settlement for each symbol in thread pool
        logger.debug(f"Fetching settlement history for {len(self.symbols)} symbols...")
        settlements = await loop.run_in_executor(None, self.fetcher.get_latest_settlements_batch, self.symbols)
        
        if not settlements:
            logger.warning("No settlement data received")
            return
        
        logger.debug(f"Fetched settlements for {len(settlements)} symbols")
        
        # Check for new settlements and generate alerts
        alerts = self.monitor.check_settlements(settlements, ticker_data)
        
        # Clear predicted alert tracking for symbols that just settled
        for alert in alerts:
            self.monitor.clear_predicted_alerts_after_settlement(alert['symbol'])
        
        # Also check predicted (current) rates for extreme values
        predicted_alerts = self.monitor.check_predicted_rates(ticker_data)
        
        # Limit predicted alerts to top 5 most extreme to avoid spam
        if len(predicted_alerts) > 5:
            predicted_alerts = sorted(
                predicted_alerts, 
                key=lambda x: abs(x.get('fundingRate', 0)), 
                reverse=True
            )[:5]
            logger.info(f"Limited to top 5 most extreme predicted rates")
        
        # Combine alerts (settlements first, then predictions)
        all_alerts = alerts + predicted_alerts
        
        # Send alerts quickly (reduce delay)
        for alert in all_alerts:
            success = await self.telegram.send_funding_alert(alert)
            if success:
                logger.info(f"Alert sent for {alert['symbol']}: {alert['alertType']}")
            else:
                logger.error(f"Failed to send alert for {alert['symbol']}")
            
            # Minimal delay between alerts
            await asyncio.sleep(0.3)
    
    async def command_listener(self):
        """Listen for Telegram commands"""
        import aiohttp
        
        logger.info("Starting command listener...")
        last_update_id = 0
        
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    url = f"https://api.telegram.org/bot{self.telegram_token}/getUpdates"
                    params = {
                        "offset": last_update_id + 1,
                        "timeout": 5  # Short timeout for faster response
                    }
                    
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get("ok"):
                                for update in data.get("result", []):
                                    last_update_id = update.get("update_id", last_update_id)
                                    await self.handle_command(update)
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error in command listener: {e}")
                    await asyncio.sleep(1)
                await asyncio.sleep(5)
    
    async def handle_command(self, update: dict):
        """Handle incoming Telegram commands"""
        message = update.get("message", {})
        text = message.get("text", "")
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type", "private")
        
        # Handle DMs - ask user to join group
        if chat_type == "private":
            dm_response = """This is a <b>Mudrex</b> service.

To receive funding rate alerts, please join our group.

For support, contact @DecentralizedJM"""
            await self.telegram.send_message(dm_response, chat_id=chat_id)
            return
        
        if not text.startswith("/"):
            return
        
        parts = text.split()
        command_full = parts[0].lower()
        command = command_full.split('@')[0]  # Get command without @botname
        
        # Bot username for @mention check
        bot_username = "mudrex_funding_rate_bot"
        has_mention = "@" in command_full
        is_for_this_bot = bot_username in command_full if has_mention else True
        
        # /funding [SYMBOL] - send funding rates (works without @mention)
        if command == "/funding" and is_for_this_bot:
            if len(parts) > 1:
                # Specific symbol requested
                symbol = parts[1].upper()
                if not symbol.endswith("USDT"):
                    symbol = symbol + "USDT"
                await self.send_symbol_funding(symbol)
            else:
                # No symbol - show top 10 extremes
                rates = self.fetcher.get_tickers(self.symbols)
                await self.telegram.send_summary(rates)
        
        # /status - show bot status (REQUIRES @mention to avoid conflicts)
        elif command == "/status":
            # Only respond if explicitly mentioned
            if has_mention and is_for_this_bot:
                status_msg = f"""<b>Funding Rate Bot Status</b>

• Status: {'Running' if self.running else 'Stopped'}
• Symbols Monitored: {len(self.symbols)}
• Last Check: {self.last_check.strftime('%H:%M:%S UTC') if self.last_check else 'Starting...'}

<i>A Mudrex service</i>"""
                await self.telegram.send_message(status_msg)
    
    async def send_symbol_funding(self, symbol: str):
        """Send current and predicted funding rate for a specific symbol"""
        try:
            # Check if symbol exists
            if symbol not in self.symbols:
                await self.telegram.send_message(f"❌ Symbol <b>{symbol}</b> not found on Mudrex.")
                return
            
            # Fetch current ticker (has predicted rate)
            ticker_data = self.fetcher.get_tickers([symbol])
            
            # Fetch last settlement
            settlements = self.fetcher.get_latest_settlements_batch([symbol])
            
            if not ticker_data or symbol not in ticker_data:
                await self.telegram.send_message(f"❌ No data available for <b>{symbol}</b>.")
                return
            
            ticker = ticker_data.get(symbol, {})
            settlement = settlements.get(symbol, {}) if settlements else {}
            
            # Current (predicted) rate
            predicted_rate = float(ticker.get("fundingRate", 0))
            predicted_pct = predicted_rate * 100
            
            # Last settled rate
            settled_rate = float(settlement.get("fundingRate", 0)) if settlement else 0
            settled_pct = settled_rate * 100
            
            # Format rates
            def format_rate(r):
                return f"+{r:.4f}%" if r >= 0 else f"{r:.4f}%"
            
            # Color based on predicted rate
            color = "🟢" if predicted_rate >= 0 else "🔴"
            
            # Bias text
            if predicted_rate >= 0:
                bias = "Positive (Longs Pay Shorts)"
            else:
                bias = "Negative (Shorts Pay Longs)"
            
            # Get interval
            interval = 8
            if symbol in self.symbols_data:
                interval = self.symbols_data[symbol].get("fundingIntervalHours", 8)
            
            # Next funding time
            next_funding = int(ticker.get("nextFundingTime", 0))
            if next_funding:
                from datetime import datetime, timezone, timedelta
                dt = datetime.fromtimestamp(next_funding / 1000, tz=timezone.utc)
                ist_offset = timedelta(hours=5, minutes=30)
                dt_ist = dt + ist_offset
                next_time_str = dt_ist.strftime('%d %b, %I:%M %p IST')
            else:
                next_time_str = "Unknown"
            
            # Last settlement time
            last_settlement = int(settlement.get("fundingRateTimestamp", 0)) if settlement else 0
            if last_settlement:
                from datetime import datetime, timezone, timedelta
                dt = datetime.fromtimestamp(last_settlement / 1000, tz=timezone.utc)
                ist_offset = timedelta(hours=5, minutes=30)
                dt_ist = dt + ist_offset
                last_time_str = dt_ist.strftime('%d %b, %I:%M %p IST')
            else:
                last_time_str = "Unknown"
            
            message = f"""{color} <b>{symbol}</b>

• Bias: {bias}
• Predicted Rate: <b>{format_rate(predicted_pct)}</b>
• Last Settled Rate: {format_rate(settled_pct)}
• Interval: {interval}h
• Next Settlement: {next_time_str}
• Last Settlement: {last_time_str}"""
            
            await self.telegram.send_message(message.strip())
            
        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
            await self.telegram.send_message(f"❌ Error fetching data for {symbol}")

    async def get_symbol_funding_rate(self, symbol: str):
        """Get and send funding rate for a specific symbol"""
        try:
            # Fetch latest settlement for this symbol
            settlements = self.fetcher.get_latest_settlements_batch([symbol])
            ticker_data = self.fetcher.get_tickers([symbol])
            
            if not settlements or symbol not in settlements:
                await self.telegram.send_message(f"Symbol {symbol} not found or no data available.")
                return
            
            settlement = settlements[symbol]
            ticker = ticker_data.get(symbol, {})
            
            rate = settlement.get("fundingRate", 0)
            rate_pct = rate * 100
            timestamp = settlement.get("fundingRateTimestamp", 0)
            
            # Format rate with sign
            rate_str = f"+{rate_pct:.4f}%" if rate >= 0 else f"{rate_pct:.4f}%"
            
            # Color based on rate
            color = "🟢" if rate >= 0 else "🔴"
            
            # Bias text
            if rate >= 0:
                bias = "Positive (Longs Pay Shorts)"
            else:
                bias = "Negative (Shorts Pay Longs)"
            
            # Format settlement time in IST
            from datetime import timedelta
            if timestamp:
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                ist_offset = timedelta(hours=5, minutes=30)
                dt_ist = dt + ist_offset
                settlement_time = dt_ist.strftime('%d %b %Y, %I:%M %p IST')
            else:
                settlement_time = "Unknown"
            
            # Get interval
            interval = ticker.get("fundingIntervalHours", 8)
            if symbol in self.symbols_data:
                interval = self.symbols_data[symbol].get("fundingIntervalHours", interval)
            
            message = f"""{color} <b>{symbol}</b>

• Bias: {bias}
• Rate: <b>{rate_str}</b>
• Interval: {interval}h
• Last Settled: {settlement_time}"""
            
            await self.telegram.send_message(message.strip())
            
        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
            await self.telegram.send_message(f"Error fetching data for {symbol}")


async def main():
    """Main entry point"""
    print("""
╔═══════════════════════════════════════════════════╗
║        Perpetual Funding Rate Alert Bot           ║
╚═══════════════════════════════════════════════════╝
    """)
    
    bot = FundingRateBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
