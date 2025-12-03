# Perpetual Funding Rate Alert Bot# Perpetual Funding Rate Alert Bot 📊



A Telegram bot that monitors perpetual futures funding rates and sends real-time alerts.A Telegram bot that monitors perpetual futures funding rates and sends real-time alerts when significant changes occur.



## FeaturesCurrently supports: **Bybit** (550+ USDT perpetuals)



- **Real-time Alerts** - Get notified when funding rates change## Features

- **Extreme Rate Alerts** - Special alerts when rates exceed 0.1%

- **Flip Detection** - Alerts when funding rate changes sign (positive ↔ negative)- 🔔 **Real-time Alerts**: Get notified when funding rates change significantly

- **On-demand Lookup** - Check any symbol's funding rate via command- ⚠️ **Extreme Rate Alerts**: Special alerts when rates exceed 0.1%

- **Multi-Interval Support** - Handles 1h, 2h, 4h, and 8h funding intervals- 🔄 **Flip Detection**: Alerts when funding rate changes from positive to negative (or vice versa)

- 📱 **Topic Support**: Send alerts to a specific Telegram topic in supergroups

## Alert Rules- 📊 **Rate Summary**: Command to view current funding rates on demand

- 🛡️ **Rate Limiting**: Built-in protection against alert spam

- **BTCUSDT**: All rate changes, flips, and extreme rates- ⏰ **Multi-Interval Support**: Handles 1h, 2h, 4h, and 8h funding intervals

- **Other symbols**: Only extreme rates (>0.1%)

## How Funding Rates Work

## Quick Start

Funding rates are periodic payments between long and short traders on perpetual futures:

### 1. Setup- **Positive rate** → Longs pay shorts (bullish sentiment)

- **Negative rate** → Shorts pay longs (bearish sentiment)

```bash

cd perp-funding-rate-botFunding settlements occur at various intervals (1h, 2h, 4h, 8h depending on the symbol).

pip install -r requirements.txt

```## Quick Start



%0A# Perpetual Funding Rate Alert Bot%0A%0AA clean, focused Telegram bot to monitor perpetual futures funding rates and send settlement-based alerts.%0A%0A## Key points%0A%0A- Monitors USDT perpetuals (currently configured for Bybit).%0A- Settlement-based alerts (no spam from predicted rates).%0A- Alert rules: `BTCUSDT` receives all alerts; other symbols receive extreme-rate alerts only (>|0.1%|).%0A- Supports funding intervals: 1h, 2h, 4h, 8h.%0A%0A## Quick start%0A%0A1) Install dependencies%0A



Create `.env` file:```bash

```cd perp-funding-rate-bot

TELEGRAM_BOT_TOKEN=your_bot_tokenpython3 -m venv venv

TELEGRAM_CHAT_ID=your_chat_idsource venv/bin/activate  # On Windows: venv\Scripts\activate

```pip install -r requirements.txt

```

### 3. Run

### 2. Configure Environment

```bash

python3 funding_rate_bot.py```bash

```cp .env.example .env

```


Edit `.env` with your credentials:

| Command | Description |- `TELEGRAM_BOT_TOKEN`: Get from [@BotFather](https://t.me/BotFather)

|---------|-------------|- `TELEGRAM_CHAT_ID`: Your group/chat ID

| `/fundingrate <symbol>` | Get funding rate for a symbol |- `TELEGRAM_TOPIC_ID`: (Optional) Specific topic ID

| `/rates` | Show funding rates summary |

| `/status` | Show bot status |### 3. Run the Bot

| `/help` | Show help message |

```bash

## Alert Formatpython funding_rate_bot.py

```

### Regular Alert

```## Telegram Commands

🟢 BTCUSDT

| Command | Description |

• Bias: Positive (Longs Pay Shorts)|---------|-------------|

• Rate: +0.0100% → +0.0250%| `/rates` | Show current funding rates for monitored symbols |

• Interval: 8h| `/funding` | Same as `/rates` |

• Settled: 04 Dec 2025, 01:30 PM IST| `/status` | Show bot status and configuration |

```| `/help` | Show help message |



### Bias Flipped## Configuration

```

🔄 BIAS FLIPPEDEdit `config.py` to customize:



🔴 ETHUSDT```python

# Symbols to monitor

• Bias: Flipped from Positive to NegativeSYMBOLS = [

• Rate: +0.0050% → -0.0120%    "BTCUSDT",

• Interval: 8h    "ETHUSDT",

• Settled: 04 Dec 2025, 01:30 PM IST    "SOLUSDT",


### Extreme Rate

```# Check interval (seconds)

⚠️ EXTREME RATECHECK_INTERVAL = 1800  # 30 minutes



🔴 DOGEUSDT# Minimum rate change to trigger alert (0.0001 = 0.01%)

MIN_RATE_CHANGE_THRESHOLD = 0.0001

• Bias: Negative (Shorts Pay Longs)

• Rate: -0.0800% → -0.1500%# Extreme rate threshold (0.001 = 0.1%)

• Interval: 8hEXTREME_RATE_THRESHOLD = 0.001

• Settled: 04 Dec 2025, 01:30 AM IST

```# Alert on sign change (positive ↔ negative)

ALERT_ON_SIGN_CHANGE = True

## Project Structure```



```

perp-funding-rate-bot/## Alert Examples

├── funding_rate_bot.py   # Main bot

├── config.py             # Configuration### Positive Funding Rate (Longs Pay)

├── bybit_fetcher.py      # API client```

├── funding_monitor.py    # Rate detection🟢 BTCUSDT

├── telegram_client.py    # Telegram messaging

├── requirements.txt      # Dependencies📈 Bias: Positive (Longs Pay Shorts)

└── .env                  # Credentials (not tracked)📊 Rate: +0.0100% → +0.0250%

```⏰ Interval: 8h

🕐 Settled: 03 Dec 2025, 01:30 PM IST

## License```



MIT License### Negative Funding Rate (Shorts Pay)

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
