#!/usr/bin/env python3
"""
Lightweight Command Handler for Funding Rate Bot

This runs as a separate process and handles Telegram commands instantly.
It does NOT do heavy monitoring - just responds to /funding and /status commands.

Commands:
- /funding - Show top 10 extreme funding rates
- /funding <SYMBOL> - Show current funding rate for a symbol
- /funding <SYMBOL> <DDMMYY> - Show historical funding rates for a symbol on a specific date
- /funding <SYMBOL> <DDMMYY> <HH:MM:SS> - Show funding rate for specific time (or next settlement)
"""

import asyncio
import aiohttp
import logging
import os
import sys
import signal
import html
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
TOPIC_ID = os.getenv("TELEGRAM_TOPIC_ID")
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
        message_thread_id = message.get("message_thread_id")
        
        # Debug log all messages
        if text:
            logger.info(f"Received: '{text}' from chat {chat_id} ({chat_type}) topic {message_thread_id}")
        
        # Handle DMs
        if chat_type == "private":
            await self.send_message(
                chat_id,
                """This is a <b>Mudrex</b> service.

To receive funding rate alerts, please join our group.

For support, contact @DecentralizedJM"""
            )
            return
        
        # Only respond to commands from the configured topic
        if TOPIC_ID and str(message_thread_id) != str(TOPIC_ID):
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
                
                # Check if date is provided (DDMMYY format)
                if len(parts) > 2:
                    date_str = parts[2]
                    if len(date_str) == 6 and date_str.isdigit():
                        # Check if time is also provided (HH:MM:SS format)
                        time_str = None
                        if len(parts) > 3:
                            time_str = parts[3]
                        await self.send_historical_funding(chat_id, symbol, date_str, time_str)
                    else:
                        await self.send_message(chat_id, "❌ Invalid date format. Use DDMMYY (e.g., 010126 for 01 Jan 2026)")
                else:
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
            
            # Add topic ID if configured
            if TOPIC_ID:
                payload["message_thread_id"] = int(TOPIC_ID)
            
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"Send message failed: {error}")
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
        
        # Escape symbol for HTML safety
        safe_symbol = html.escape(symbol)
        
        if not data:
            await self.send_message(chat_id, f"❌ Symbol <b>{safe_symbol}</b> not found on Mudrex.")
            return
        
        rate = data["fundingRate"]
        rate_pct = rate * 100
        next_funding = data["nextFundingTime"]
        
        # Format rate
        rate_str = f"+{rate_pct:.4f}%" if rate >= 0 else f"{rate_pct:.4f}%"
        color = "🟢" if rate >= 0 else "🔴"
        bias = "Positive (Longs Pay Shorts)" if rate >= 0 else "Negative (Shorts Pay Longs)"
        
        # Format next funding time in IST (DD/MM/YY H:M:S format)
        if next_funding:
            dt = datetime.fromtimestamp(next_funding / 1000, tz=timezone.utc)
            dt_ist = dt + timedelta(hours=5, minutes=30)
            next_time_str = dt_ist.strftime('%d/%m/%y %H:%M:%S')
        else:
            next_time_str = "Unknown"
        
        message = f"""{color} <b>{safe_symbol}</b>

• Bias: {bias}
• Live Rate: <b>{rate_str}</b>
• Next Settlement: {next_time_str}

<i>💡 Tip: Use /funding {safe_symbol.replace('USDT', '')} DDMMYY for historical rates</i>"""
        
        await self.send_message(chat_id, message)
    
    async def send_historical_funding(self, chat_id: int, symbol: str, date_str: str, time_str: str = None):
        """Send historical funding rates for a specific symbol and date (optionally filtered by time)"""
        # Escape symbol for HTML safety
        safe_symbol = html.escape(symbol)

        try:
            # Parse and validate date (DDMMYY format)
            day = int(date_str[0:2])
            month = int(date_str[2:4])
            year = int(date_str[4:6]) + 2000  # Convert YY to YYYY
            
            target_date = datetime(year, month, day, tzinfo=timezone.utc)
            date_display = target_date.strftime('%d/%m/%y')
            
            # Check if date is in the future
            if target_date.date() > datetime.now(timezone.utc).date():
                await self.send_message(chat_id, f"❌ Cannot fetch historical data for future date: {date_display}")
                return
            
        except (ValueError, IndexError):
            await self.send_message(chat_id, "❌ Invalid date format. Use DDMMYY (e.g., 010126 for 01 Jan 2026)")
            return
        
        # Parse time if provided (HH:MM:SS format)
        target_time_ist = None
        target_timestamp = None
        if time_str:
            try:
                # Parse HH:MM:SS format
                time_parts = time_str.split(':')
                if len(time_parts) >= 2:
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    second = int(time_parts[2]) if len(time_parts) > 2 else 0
                    
                    # Create target datetime in IST
                    target_time_ist = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
                    # Convert IST to UTC (subtract 5:30)
                    target_time_utc = target_time_ist - timedelta(hours=5, minutes=30)
                    target_timestamp = int(target_time_utc.timestamp() * 1000)
                else:
                    await self.send_message(chat_id, "❌ Invalid time format. Use HH:MM:SS (e.g., 18:30:00)")
                    return
            except (ValueError, IndexError):
                await self.send_message(chat_id, "❌ Invalid time format. Use HH:MM:SS (e.g., 18:30:00)")
                return
        
        try:
            # Calculate start and end timestamps for the date (UTC)
            start_dt = datetime(year, month, day, 0, 0, 0, tzinfo=timezone.utc)
            end_dt = start_dt + timedelta(days=1) - timedelta(milliseconds=1)
            
            start_time = int(start_dt.timestamp() * 1000)
            end_time = int(end_dt.timestamp() * 1000)
            
            # Fetch historical funding rates from Bybit API
            url = f"{BYBIT_BASE_URL}/v5/market/funding/history"
            params = {
                "category": "linear",
                "symbol": symbol,
                "startTime": start_time,
                "endTime": end_time,
                "limit": 200
            }
            
            logger.info(f"Fetching historical funding for {symbol} on {date_display}" + (f" at {time_str}" if time_str else ""))
            
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    await self.send_message(chat_id, f"❌ Failed to fetch historical data for <b>{safe_symbol}</b>")
                    return
                
                data = await resp.json()
                
                if data.get("retCode") != 0:
                    error_msg = data.get('retMsg', 'Unknown error')
                    logger.error(f"Bybit API error: {error_msg}")
                    await self.send_message(chat_id, f"❌ API Error: {error_msg}")
                    return
                
                records = data.get("result", {}).get("list", [])
                
                if not records:
                    await self.send_message(chat_id, f"❌ No funding rate data found for <b>{safe_symbol}</b> on {date_display}")
                    return
                
                # Sort by timestamp ascending (oldest first)
                records.sort(key=lambda x: int(x.get("fundingRateTimestamp", 0)))
                
                # If time is provided, find the closest settlement at or after the given time
                if target_time_ist and target_timestamp:
                    matching_record = None
                    
                    for record in records:
                        record_timestamp = int(record.get("fundingRateTimestamp", 0))
                        if record_timestamp >= target_timestamp:
                            matching_record = record
                            break
                    
                    # If no record found at or after the time, get the last one before it
                    if not matching_record:
                        for record in reversed(records):
                            record_timestamp = int(record.get("fundingRateTimestamp", 0))
                            if record_timestamp <= target_timestamp:
                                matching_record = record
                                break
                    
                    if not matching_record:
                        await self.send_message(chat_id, f"❌ No funding rate found for <b>{safe_symbol}</b> at {time_str} on {date_display}")
                        return
                    
                    # Format single record response
                    rate = float(matching_record.get("fundingRate", 0))
                    rate_pct = rate * 100
                    timestamp = int(matching_record.get("fundingRateTimestamp", 0))
                    
                    # Format time in IST
                    dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                    dt_ist = dt + timedelta(hours=5, minutes=30)
                    settlement_time_str = dt_ist.strftime('%d/%m/%y %H:%M:%S')
                    
                    emoji = "🟢" if rate >= 0 else "🔴"
                    rate_str = f"+{rate_pct:.4f}%" if rate >= 0 else f"{rate_pct:.4f}%"
                    bias = "Positive (Longs Pay Shorts)" if rate >= 0 else "Negative (Shorts Pay Longs)"
                    
                    message = f"""📊 <b>{safe_symbol}</b> Funding Rate

🕐 Requested: {date_display} {time_str}
⏰ Settlement: {settlement_time_str}

{emoji} Rate: <b>{rate_str}</b>
• Bias: {bias}

<i>A Mudrex service</i>"""
                    
                    await self.send_message(chat_id, message)
                    logger.info(f"Sent single funding rate for {symbol} at {settlement_time_str}")
                    
                else:
                    # Build full day message
                    lines = [f"📊 <b>{safe_symbol}</b> Historical Funding Rates", f"📅 Date: {date_display}\n"]
                    
                    total_rate = 0
                    for record in records:
                        rate = float(record.get("fundingRate", 0))
                        rate_pct = rate * 100
                        total_rate += rate
                        timestamp = int(record.get("fundingRateTimestamp", 0))
                        
                        # Format time in IST (DD/MM/YY H:M:S format)
                        dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                        dt_ist = dt + timedelta(hours=5, minutes=30)
                        time_display = dt_ist.strftime('%d/%m/%y %H:%M:%S')
                        
                        # Emoji based on rate
                        emoji = "🟢" if rate >= 0 else "🔴"
                        rate_str = f"+{rate_pct:.4f}%" if rate >= 0 else f"{rate_pct:.4f}%"
                        
                        lines.append(f"{emoji} {time_display}: <b>{rate_str}</b>")
                    
                    # Add daily total
                    total_pct = total_rate * 100
                    total_emoji = "🟢" if total_rate >= 0 else "🔴"
                    total_str = f"+{total_pct:.4f}%" if total_rate >= 0 else f"{total_pct:.4f}%"
                    lines.append(f"\n{total_emoji} <b>Daily Total: {total_str}</b>")
                    lines.append(f"📈 Settlements: {len(records)}")
                    
                    await self.send_message(chat_id, "\n".join(lines))
                    logger.info(f"Sent historical funding for {symbol} on {date_display}: {len(records)} records")
                
        except Exception as e:
            logger.error(f"Error fetching historical funding for {symbol}: {e}")
            await self.send_message(chat_id, f"❌ Error fetching historical data for {symbol}")
    
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
        lines.append("<i>💡 Use /funding SYMBOL DDMMYY [HH:MM:SS]</i>")
        
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

<b>Commands:</b>
• /funding - Top 10 extreme rates
• /funding SYMBOL - Current rate for symbol
• /funding SYMBOL DDMMYY - Full day historical rates
• /funding SYMBOL DDMMYY HH:MM:SS - Specific time rate

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
