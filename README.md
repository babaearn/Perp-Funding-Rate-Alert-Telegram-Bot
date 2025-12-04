# Perpetual Funding Rate Alert Bot

Real-time funding rate alerts for perpetual futures. A **Mudrex** service.

## Features

- Settlement-based alerts (no spam from predicted rates)
- Extreme rate detection (alerts when rates ≥ ±0.5%)
- Bias flip detection (alerts when funding flips positive ↔ negative)
- Multi-interval support (1h, 2h, 4h, 8h)
- Auto-refresh symbol list every 24 hours

## Alert Rules

| Symbol | Alert Trigger |
|--------|---------------|
| BTCUSDT | All rate changes, flips, extreme rates |
| Others | Extreme rates only (≥0.5%) |

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
• Rate: -0.4000% → -0.5500%
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

[MIT License](LICENSE)
