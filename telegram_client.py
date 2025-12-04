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
    
    async def send_message(self, text: str, topic_id: Optional[int] = None, chat_id: Optional[int] = None) -> bool:
        """
        Send a message to Telegram chat/topic
        
        Args:
            text: Message text (supports HTML formatting)
            topic_id: Optional topic ID (overrides self.topic_id if provided)
            chat_id: Optional chat ID (overrides self.chat_id if provided, for DM replies)
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            payload = {
                "chat_id": chat_id or self.chat_id,
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
        prev_rate = alert.get("prevFundingRate")
        alert_type = alert.get("alertType", "change")
        funding_interval = alert.get("fundingInterval", "8h")
        prev_interval = alert.get("prevFundingInterval", funding_interval)
        settlement_time = alert.get("settlementTime", "")
        
        # Format rates as percentages with + for positive
        rate_pct = rate * 100
        
        def format_rate(r):
            return f"+{r:.4f}%" if r >= 0 else f"{r:.4f}%"
        
        # Determine color based on current rate
        if rate >= 0:
            color_emoji = "🟢"
        else:
            color_emoji = "🔴"
        
        # Handle PREDICTED alerts differently
        if alert_type == "predicted":
            if rate >= 0:
                bias_text = "Positive (Longs Pay Shorts)"
            else:
                bias_text = "Negative (Shorts Pay Longs)"
            
            header = f"⚡ <b>PREDICTED EXTREME RATE</b>\n\n{color_emoji} <b>{symbol}</b>"
            
            message = f"""{header}

• Bias: {bias_text}
• Predicted Rate: <b>{format_rate(rate_pct)}</b>
• Interval: {funding_interval}
• Settles: {settlement_time}

<i>This rate will settle at the next funding time</i>"""
            
            return message.strip()
        
        # For settlement alerts, we need prev_rate
        prev_rate_pct = (prev_rate or 0) * 100
        
        # Determine bias text based on sign change
        prev_positive = (prev_rate or 0) >= 0
        curr_positive = rate >= 0
        is_flip = False
        
        if prev_rate is not None:
            if prev_positive and not curr_positive:
                bias_text = "Flipped from Positive to Negative"
                color_emoji = "🔴"
                is_flip = True
            elif not prev_positive and curr_positive:
                bias_text = "Flipped from Negative to Positive"
                color_emoji = "🟢"
                is_flip = True
            elif curr_positive:
                bias_text = "Positive (Longs Pay Shorts)"
            else:
                bias_text = "Negative (Shorts Pay Longs)"
        else:
            if curr_positive:
                bias_text = "Positive (Longs Pay Shorts)"
            else:
                bias_text = "Negative (Shorts Pay Longs)"
        
        # Check for interval change
        interval_text = f"{funding_interval}"
        is_interval_change = prev_interval and prev_interval != funding_interval
        if is_interval_change:
            interval_text = f"{prev_interval} → {funding_interval}"
        
        # Build header based on alert type
        if alert_type == "extreme":
            header = f"⚠️ <b>EXTREME RATE</b>\n\n{color_emoji} <b>{symbol}</b>"
        elif is_flip:
            header = f"🔄 <b>BIAS FLIPPED</b>\n\n{color_emoji} <b>{symbol}</b>"
        elif is_interval_change:
            header = f"⏰ <b>INTERVAL CHANGED</b>\n\n{color_emoji} <b>{symbol}</b>"
        else:
            header = f"{color_emoji} <b>{symbol}</b>"
        
        # Clean format with only green/red dots and bullets
        if prev_rate is not None:
            rate_line = f"• Rate: <b>{format_rate(prev_rate_pct)}</b> → <b>{format_rate(rate_pct)}</b>"
        else:
            rate_line = f"• Rate: <b>{format_rate(rate_pct)}</b>"
        
        message = f"""{header}

• Bias: {bias_text}
{rate_line}
• Interval: {interval_text}
• Settled: {settlement_time}"""
        
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
• ⚡ Predicted extreme rates (before settlement)
• ⚠️ Extreme rates at settlement (≥0.1%)
• 🔄 Rate flips (+ ↔ -)

<i>Bot checks every 30 minutes.</i>
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
