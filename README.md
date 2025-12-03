# Perpetual Funding Rate Alert Bot 📊

A Telegram bot that monitors perpetual futures funding rates and sends real-time alerts when significant changes occur.

Currently supports: **Bybit** (550+ USDT perpetuals)

## Features

- 🔔 **Real-time Alerts**: Get notified when funding rates change significantly
- ⚠️ **Extreme Rate Alerts**: Special alerts when rates exceed 0.1%
- 🔄 **Flip Detection**: Alerts when funding rate changes from positive to negative (or vice versa)
- 📱 **Topic Support**: Send alerts to a specific Telegram topic in supergroups
- 📊 **Rate Summary**: Command to view current funding rates on demand
- 🛡️ **Rate Limiting**: Built-in protection against alert spam
- ⏰ **Multi-Interval Support**: Handles 1h, 2h, 4h, and 8h funding intervals

## How Funding Rates Work

Funding rates are periodic payments between long and short traders on perpetual futures:
- **Positive rate** → Longs pay shorts (bullish sentiment)
- **Negative rate** → Shorts pay longs (bearish sentiment)

Funding settlements occur at various intervals (1h, 2h, 4h, 8h depending on the symbol).

## Quick Start

### 1. Clone and Setup

```bash
cd perp-funding-rate-bot
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:
- `TELEGRAM_BOT_TOKEN`: Get from [@BotFather](https://t.me/BotFather)
- `TELEGRAM_CHAT_ID`: Your group/chat ID
- `TELEGRAM_TOPIC_ID`: (Optional) Specific topic ID

### 3. Run the Bot

```bash
python funding_rate_bot.py
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/rates` | Show current funding rates for monitored symbols |
| `/funding` | Same as `/rates` |
| `/status` | Show bot status and configuration |
| `/help` | Show help message |

## Configuration

Edit `config.py` to customize:

```python
# Symbols to monitor
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    # Add more symbols...
]

# Check interval (seconds)
CHECK_INTERVAL = 1800  # 30 minutes

# Minimum rate change to trigger alert (0.0001 = 0.01%)
MIN_RATE_CHANGE_THRESHOLD = 0.0001

# Extreme rate threshold (0.001 = 0.1%)
EXTREME_RATE_THRESHOLD = 0.001

# Alert on sign change (positive ↔ negative)
ALERT_ON_SIGN_CHANGE = True
```


## Alert Examples

### Positive Funding Rate (Longs Pay)
```
🟢 BTCUSDT

📈 Bias: Positive (Longs Pay Shorts)
📊 Rate: +0.0100% → +0.0250%
⏰ Interval: 8h
🕐 Settled: 03 Dec 2025, 01:30 PM IST
```

### Negative Funding Rate (Shorts Pay)
```
🔴 ETHUSDT

📉 Bias: Negative (Shorts Pay Longs)
📊 Rate: -0.0050% → -0.0120%
⏰ Interval: 4h
🕐 Settled: 03 Dec 2025, 05:30 PM IST
```

### Flipped Positive → Negative
```
🔴 SOLUSDT

🔄 Bias: Flipped from Positive to Negative
📊 Rate: +0.0080% → -0.0095%
⏰ Interval: 8h
🕐 Settled: 03 Dec 2025, 09:30 PM IST
```

### Flipped Negative → Positive
```
🟢 ARBUSDT

🔄 Bias: Flipped from Negative to Positive
📊 Rate: -0.0050% → +0.0120%
⏰ Interval: 4h
🕐 Settled: 03 Dec 2025, 11:30 PM IST
```

### Interval Change Alert
```
🟢 AVAXUSDT

📈 Bias: Positive (Longs Pay Shorts)
📊 Rate: +0.0080% → +0.0095%
⏰ Interval: 4h → 8h ⚠️
🕐 Settled: 03 Dec 2025, 09:30 PM IST
```

### Extreme Rate Alert
```
⚠️ EXTREME RATE ⚠️

🔴 DOGEUSDT

📉 Bias: Negative (Shorts Pay Longs)
📊 Rate: -0.0800% → -0.1500%
⏰ Interval: 8h
🕐 Settled: 03 Dec 2025, 01:30 AM IST
```

# Build image
docker build -t funding-rate-bot .

# Run container
docker run -d --name funding-bot --env-file .env funding-rate-bot
```

## Project Structure

```
perp-funding-rate-bot/
├── funding_rate_bot.py   # Main bot entry point
├── config.py             # Configuration settings
├── bybit_fetcher.py      # Exchange API client (Bybit)
├── funding_monitor.py    # Rate change detection logic
├── telegram_client.py    # Telegram messaging
├── requirements.txt      # Python dependencies
├── .env.example          # Environment template
├── Dockerfile            # Docker configuration
└── README.md             # This file
```

## Getting Telegram IDs

### Chat ID
1. Add [@userinfobot](https://t.me/userinfobot) to your group
2. It will reply with the chat ID
3. Group IDs are negative numbers (e.g., `-1001234567890`)

### Topic ID (for Supergroups)
1. Right-click on a topic in your group
2. Copy the message link
3. The number after the last `/` is the topic ID

## License

MIT License - feel free to modify and use as needed!

## Troubleshooting

### Bot not sending alerts?
- Check `.env` file has correct credentials
- Verify bot is added to the group with admin rights
- Check `logs/funding_alerts.log` for errors

### Rate limit errors?
- The bot checks every 30 minutes by default
- Increase `CHECK_INTERVAL` if needed

### Topic not working?
- Ensure group has Topics enabled
- Bot needs permission to post in topics
- Verify `TELEGRAM_TOPIC_ID` is correct
