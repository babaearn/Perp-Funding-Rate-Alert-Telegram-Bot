# Perpetual Funding Rate Alert Bot

Real-time funding rate alerts for perpetual futures. A **Mudrex** service.

## Features

- Settlement-based alerts (no spam from predicted rates)
- Extreme rate detection (alerts when rates exceed ±0.1%)
- Bias flip detection (alerts when funding flips positive ↔ negative)
- Multi-interval support (1h, 2h, 4h, 8h)
- Auto-refresh symbol list every 24 hours

## Alert Rules

| Symbol | Alert Trigger |
|--------|---------------|
| BTCUSDT | All rate changes, flips, extreme rates |
| Others | Extreme rates only (>0.1%) |

## Setup

```bash
cd perp-funding-rate-bot
pip install -r requirements.txt
```

Create `.env`:

```
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

Run:

```bash
python3 funding_rate_bot.py
```

## Commands

| Command | Description |
|---------|-------------|
| `/funding` | Show funding rates summary |
| `/status` | Show bot status |

## Alert Examples

**Regular:**
```
🟢 BTCUSDT

• Bias: Positive (Longs Pay Shorts)
• Rate: +0.0100% → +0.0250%
• Interval: 8h
• Settled: 04 Dec 2025, 01:30 PM IST
```

**Bias Flipped:**
```
🔄 BIAS FLIPPED

🔴 ETHUSDT

• Bias: Flipped from Positive to Negative
• Rate: +0.0050% → -0.0120%
• Interval: 8h
• Settled: 04 Dec 2025, 01:30 PM IST
```

**Extreme Rate:**
```
⚠️ EXTREME RATE

🔴 DOGEUSDT

• Bias: Negative (Shorts Pay Longs)
• Rate: -0.0800% → -0.1500%
• Interval: 8h
• Settled: 04 Dec 2025, 01:30 AM IST
```

## Project Structure

```
perp-funding-rate-bot/
├── funding_rate_bot.py
├── config.py
├── bybit_fetcher.py
├── funding_monitor.py
├── telegram_client.py
├── requirements.txt
└── .env (not tracked)
```

## Support

Contact: [@DecentralizedJM](https://t.me/DecentralizedJM)

GitHub: [DecentralizedJM](https://github.com/DecentralizedJM)

## License

MIT License

Copyright (c) 2025 DecentralizedJM

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
