# Perpetual Funding Rate Alert Bot

Real-time funding rate alerts for perpetual futures. A **Mudrex** service.

## Features

- Settlement-based alerts (no spam from live rate fluctuations)
- Extreme rate detection (alerts when rates ≥ ±1%)
- Bias flip detection (alerts when funding flips positive ↔ negative)
- Multi-interval support (1h, 2h, 4h, 8h)
- Auto-refresh symbol list every 24 hours
- **Historical funding rate lookup** by date

## Alert Rules

| Symbol | Alert Trigger |
|--------|---------------|
| BTCUSDT | All rate changes, flips, extreme rates |
| Others | Extreme rates only (≥1%) |

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
| `/funding` | Show top 10 extreme funding rates |
| `/funding <SYMBOL>` | Show current funding rate for a symbol (e.g., `/funding BTC` or `/funding BTCUSDT`) |
| `/funding <SYMBOL> <DDMMYY>` | Show historical funding rates for a symbol on a specific date (e.g., `/funding BTC 010126` for 01 Jan 2026) |
| `/status` | Show bot status |

## Historical Funding Rate

You can query historical funding rates for any symbol on a specific date using the DDMMYY format:

**Example:** `/funding BTCUSDT 251225` - Shows all funding settlements for BTCUSDT on 25 Dec 2025

**Output:**
```
📊 BTCUSDT Historical Funding Rates
📅 Date: 25 Dec 2025

🟢 05:30 AM IST: +0.0100%
🟢 01:30 PM IST: +0.0085%
🔴 09:30 PM IST: -0.0050%

🟢 Daily Total: +0.0135%
📈 Settlements: 3
```

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
• Rate: -0.4000% → -1.1000%
• Interval: 8h
• Settled: 04 Dec 2025, 01:30 AM IST
```

## Project Structure

```
perp-funding-rate-bot/
├── funding_rate_bot.py
├── command_handler.py   # Lightweight command handler
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
