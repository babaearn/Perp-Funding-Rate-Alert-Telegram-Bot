#!/usr/bin/env python3
"""
Lightweight Command Handler for Funding Rate Bot

This runs as a separate process and handles Telegram commands instantly.
It does NOT do heavy monitoring - just responds to /funding and /status commands.
"""

import asyncio
import aiohttp
import logging
import os
import sys
import signal
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/command_handler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Telegram config
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BOT_USERNAME = "mudrex_funding_rate_bot"  # lowercase for comparison

# Bybit API
BYBIT_BASE_URL = "https://api.bybit.com"


class CommandHandler:
    def __init__(self):
        self.running = True
        self.session = None
        self.symbols_cache = {}
        self.symbols_cache_time = None
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
    
    def _shutdown(self, signum, frame):
        logger.info(f"Shutting down command handler...")
        self.running = False
    
    async def start(self):
        """Start the command handler"""
        logger.info("Starting Command Handler...")
        
        async with aiohttp.ClientSession() as session:
            self.session = session
            
            # Pre-cache symbols
            await self.refresh_symbols_cache()
            
            logger.info("Command Handler ready - listening for commands")
            
            last_update_id = 0
            while self.running:
                try:
                    # Poll for updates with short timeout
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
                    params = {"offset": last_update_id + 1, "timeout": 2}
                    
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("ok"):
                                for update in data.get("result", []):
                                    last_update_id = update.get("update_id", last_update_id)
                                    await self.handle_update(update)
                
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error: {e}")
                    await asyncio.sleep(1)
    
    async def handle_update(self, update: dict):
        """Handle a Telegram update"""
        message = update.get("message", {})
        text = message.get("text", "")
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type", "private")
        
        # Debug log all messages
        if text:
            logger.info(f"Received: '{text}' from chat {chat_id} ({chat_type})")
        
        # Handle DMs
        if chat_type == "private":
            await self.send_message(
                chat_id,
                """This is a <b>Mudrex</b> service.

To receive funding rate alerts, please join our group.

For support, contact @DecentralizedJM"""
            )
            return
        
        if not text.startswith("/"):
            return
        
        parts = text.split()
        command_full = parts[0].lower()
        command = command_full.split('@')[0]
        
        # Check if command mentions this bot (in command or as second word)
        text_lower = text.lower()
        has_mention = BOT_USERNAME in text_lower
        
        # For /status, require @mention somewhere in the message
        # For /funding, no mention required
        
        # Handle /funding command
        if command == "/funding":
            if len(parts) > 1:
                symbol = parts[1].upper()
                if not symbol.endswith("USDT"):
                    symbol += "USDT"
                await self.send_symbol_funding(chat_id, symbol)
            else:
                await self.send_top_funding(chat_id)
        
        # Handle /status command (requires @mention)
        elif command == "/status" and has_mention:
            logger.info(f"Processing /status command")
            await self.send_status(chat_id)
    
    async def send_message(self, chat_id: int, text: str):
        """Send a message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return False
    
    async def refresh_symbols_cache(self):
        """Refresh the symbols cache from Bybit"""
        try:
            url = f"{BYBIT_BASE_URL}/v5/market/tickers?category=linear"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("retCode") == 0:
                        symbols = {}
                        for item in data.get("result", {}).get("list", []):
                            symbol = item.get("symbol", "")
                            if symbol.endswith("USDT"):
                                symbols[symbol] = {
                                    "fundingRate": float(item.get("fundingRate", 0)),
                                    "nextFundingTime": int(item.get("nextFundingTime", 0)),
                                    "lastPrice": item.get("lastPrice", "0"),
                                }
                        self.symbols_cache = symbols
                        self.symbols_cache_time = datetime.now(timezone.utc)
                        logger.info(f"Cached {len(symbols)} symbols")
        except Exception as e:
            logger.error(f"Cache refresh error: {e}")
    
    async def get_symbol_data(self, symbol: str) -> dict:
        """Get data for a specific symbol"""
        # Refresh cache if older than 30 seconds
        if not self.symbols_cache_time or \
           (datetime.now(timezone.utc) - self.symbols_cache_time).total_seconds() > 30:
            await self.refresh_symbols_cache()
        
        return self.symbols_cache.get(symbol)
    
    async def send_symbol_funding(self, chat_id: int, symbol: str):
        """Send funding rate for a specific symbol"""
        data = await self.get_symbol_data(symbol)
        
        if not data:
            await self.send_message(chat_id, f"❌ Symbol <b>{symbol}</b> not found on Bybit.")
            return
        
        rate = data["fundingRate"]
        rate_pct = rate * 100
        next_funding = data["nextFundingTime"]
        
        # Format rate
        rate_str = f"+{rate_pct:.4f}%" if rate >= 0 else f"{rate_pct:.4f}%"
        color = "🟢" if rate >= 0 else "🔴"
        bias = "Positive (Longs Pay Shorts)" if rate >= 0 else "Negative (Shorts Pay Longs)"
        
        # Format next funding time in IST
        if next_funding:
            dt = datetime.fromtimestamp(next_funding / 1000, tz=timezone.utc)
            dt_ist = dt + timedelta(hours=5, minutes=30)
            next_time_str = dt_ist.strftime('%d %b, %I:%M %p IST')
        else:
            next_time_str = "Unknown"
        
        message = f"""{color} <b>{symbol}</b>

• Bias: {bias}
• Predicted Rate: <b>{rate_str}</b>
• Next Settlement: {next_time_str}"""
        
        await self.send_message(chat_id, message)
    
    async def send_top_funding(self, chat_id: int):
        """Send top 10 most extreme funding rates"""
        # Refresh cache
        await self.refresh_symbols_cache()
        
        if not self.symbols_cache:
            await self.send_message(chat_id, "❌ No funding rate data available.")
            return
        
        # Sort by absolute rate
        sorted_rates = sorted(
            self.symbols_cache.items(),
            key=lambda x: abs(x[1]["fundingRate"]),
            reverse=True
        )[:10]
        
        lines = ["📊 <b>Top 10 Extreme Funding Rates</b>\n"]
        
        for symbol, data in sorted_rates:
            rate = data["fundingRate"]
            rate_pct = rate * 100
            
            if rate > 0.0005:
                emoji = "🔴"
            elif rate > 0:
                emoji = "🟠"
            elif rate < -0.0005:
                emoji = "🟢"
            elif rate < 0:
                emoji = "🔵"
            else:
                emoji = "⚪"
            
            lines.append(f"{emoji} <b>{symbol}</b>: {rate_pct:+.4f}%")
        
        lines.append("\n<i>🔴 Longs pay | 🟢 Shorts pay</i>")
        
        await self.send_message(chat_id, "\n".join(lines))
    
    async def send_status(self, chat_id: int):
        """Send bot status"""
        cache_age = ""
        if self.symbols_cache_time:
            age_secs = (datetime.now(timezone.utc) - self.symbols_cache_time).total_seconds()
            cache_age = f"{int(age_secs)}s ago"
        
        message = f"""<b>Funding Rate Bot Status</b>

• Status: Running
• Symbols Cached: {len(self.symbols_cache)}
• Cache Updated: {cache_age or 'Never'}

<i>A Mudrex service</i>"""
        
        await self.send_message(chat_id, message)


async def main():
    print("""
╔═══════════════════════════════════════════════════╗
║     Funding Rate Command Handler (Lightweight)    ║
╚═══════════════════════════════════════════════════╝
    """)
    
    handler = CommandHandler()
    await handler.start()


if __name__ == "__main__":
    asyncio.run(main())
