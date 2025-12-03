import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramClient:
    """Send alerts to Telegram with topic support"""
    
    def __init__(self, bot_token: str, chat_id, topic_id: Optional[int] = None):
        """
        Initialize Telegram client
        
        Args:
            bot_token: Telegram bot token from BotFather
            chat_id: Target chat ID for alerts
            topic_id: Optional Telegram topic ID (for supergroups with topics enabled)
        """
        self.bot_token = bot_token
        self.chat_id = int(chat_id) if isinstance(chat_id, str) else chat_id
        self.topic_id = topic_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        
        if not bot_token or not chat_id:
            logger.error("Telegram credentials missing. Check .env file.")
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required in .env")
        
        if self.topic_id:
            logger.info(f"✅ Telegram topic configured: Topic ID {self.topic_id}")
    
    async def send_message(self, text: str, topic_id: Optional[int] = None) -> bool:
        """
        Send a message to Telegram chat/topic
        
        Args:
            text: Message text (supports HTML formatting)
            topic_id: Optional topic ID (overrides self.topic_id if provided)
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            
            # Use provided topic_id, fall back to self.topic_id
            effective_topic_id = topic_id or self.topic_id
            if effective_topic_id:
                payload["message_thread_id"] = effective_topic_id
            
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.debug(f"Message sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error: {result.get('description')}")
                    return False
            else:
                logger.error(f"HTTP error {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Telegram request timed out")
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    async def send_funding_alert(self, alert: dict) -> bool:
        """
        Send a formatted funding rate alert
        
        Args:
            alert: Alert dictionary with funding rate info
        
        Returns:
            True if sent successfully
        """
        message = self._format_funding_alert(alert)
        return await self.send_message(message)
    
    def _format_funding_alert(self, alert: dict) -> str:
        """Format funding rate alert as Telegram message"""
        symbol = alert.get("symbol", "UNKNOWN")
        rate = alert.get("fundingRate", 0)
        prev_rate = alert.get("prevFundingRate", 0)
        rate_change = alert.get("rateChange", 0)
        alert_type = alert.get("alertType", "change")
        price = alert.get("lastPrice", 0)
        next_funding = alert.get("nextFundingTime", "")
        
        # Determine emoji based on rate
        if rate > 0:
            rate_emoji = "🔴"  # Longs pay shorts
            bias = "LONG PAYING"
        elif rate < 0:
            rate_emoji = "🟢"  # Shorts pay longs
            bias = "SHORT PAYING"
        else:
            rate_emoji = "⚪"
            bias = "NEUTRAL"
        
        # Alert type specific formatting
        if alert_type == "extreme":
            header = f"⚠️ <b>EXTREME FUNDING RATE</b> ⚠️"
        elif alert_type == "sign_change":
            header = f"🔄 <b>FUNDING RATE FLIP</b> 🔄"
        else:
            header = f"📊 <b>FUNDING RATE CHANGE</b>"
        
        # Format rates as percentages
        rate_pct = rate * 100
        prev_rate_pct = prev_rate * 100
        change_pct = rate_change * 100
        
        # Change direction emoji
        if rate_change > 0:
            change_emoji = "📈"
        elif rate_change < 0:
            change_emoji = "📉"
        else:
            change_emoji = "➡️"
        
        # Get settlement time or next funding time
        settlement_time = alert.get("settlementTime", "")
        funding_interval = alert.get("fundingInterval", "8h")
        
        message = f"""
{header}

{rate_emoji} <b>{symbol}</b> ({funding_interval})

<b>Settled Rate:</b> {rate_pct:+.4f}%
<b>Previous Rate:</b> {prev_rate_pct:+.4f}%
<b>Change:</b> {change_emoji} {change_pct:+.4f}%

<b>Bias:</b> {bias}
<b>Price:</b> ${price:,.2f}

<b>Settlement:</b> {settlement_time}

<i>Perpetual Futures</i>
"""
        return message.strip()
    
    async def send_startup_message(self, symbols: list, intervals: dict = None) -> bool:
        """Send bot startup notification"""
        
        # Count by interval if provided
        interval_info = ""
        if intervals:
            interval_info = f"""
<b>Funding Intervals:</b>
• 1-hour: {intervals.get('1', 0)} symbols
• 2-hour: {intervals.get('2', 0)} symbols
• 4-hour: {intervals.get('4', 0)} symbols
• 8-hour: {intervals.get('8', 0)} symbols
"""
        
        message = f"""
🚀 <b>Funding Rate Bot Started</b>

Monitoring <b>{len(symbols)}</b> symbols for funding rate changes.
{interval_info}
<b>Alert Types:</b>
• 📊 Rate changes at settlement
• ⚠️ Extreme rates (≥0.1%)
• 🔄 Rate flips (+ ↔ -)

<i>Bot checks every 30 minutes to catch all settlement times.</i>
"""
        return await self.send_message(message.strip())
    
    async def send_startup_message_old(self, symbols: list) -> bool:
        """Send bot startup notification"""
        message = f"""
🚀 <b>Bybit Funding Rate Bot Started</b>

Monitoring {len(symbols)} symbols for funding rate changes:
{', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}

Alerts will be sent when:
• Funding rate changes significantly
• Rate becomes extreme (>0.1%)
• Rate flips (positive ↔ negative)

<i>Bot is now active!</i>
"""
        return await self.send_message(message.strip())
    
    async def send_summary(self, rates: dict) -> bool:
        """Send a summary of current funding rates"""
        if not rates:
            return await self.send_message("No funding rate data available.")
        
        # Sort by absolute funding rate (most extreme first)
        sorted_rates = sorted(
            rates.items(),
            key=lambda x: abs(x[1].get("fundingRate", 0)),
            reverse=True
        )
        
        lines = ["📊 <b>Current Funding Rates (Top 10)</b>\n"]
        
        for symbol, data in sorted_rates[:10]:
            rate = data.get("fundingRate", 0)
            rate_pct = rate * 100
            
            if rate > 0.0005:
                emoji = "🔴"  # High positive (longs pay)
            elif rate > 0:
                emoji = "🟠"  # Positive
            elif rate < -0.0005:
                emoji = "🟢"  # High negative (shorts pay)
            elif rate < 0:
                emoji = "🔵"  # Negative
            else:
                emoji = "⚪"
            
            lines.append(f"{emoji} <b>{symbol}</b>: {rate_pct:+.4f}%")
        
        lines.append("\n<i>🔴 Longs pay | 🟢 Shorts pay</i>")
        
        return await self.send_message("\n".join(lines))
