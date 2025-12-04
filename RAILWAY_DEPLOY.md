# Railway Deployment Guide

## Quick Deploy

1. Connect your GitHub repo to Railway
2. Set environment variables in Railway dashboard:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `TELEGRAM_TOPIC_ID` (optional)

3. Deploy!

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | ✅ | Target group/chat ID |
| `TELEGRAM_TOPIC_ID` | ❌ | Topic ID for forum groups |

## Files Added for Railway

- `railway.json` - Railway configuration
- `railway.toml` - Alternative Railway config
- `.python-version` - Python version (3.11)
- `start_bot.py` - Unified starter (runs command_handler + alert_monitor)

## Architecture

The bot runs two concurrent tasks:
1. **Command Handler** - Responds to /funding, /status commands instantly
2. **Alert Monitor** - Monitors 550 perpetuals and sends funding rate alerts

## Notes

- Bot runs continuously with auto-restart on failure
- Logs available in Railway dashboard
- No ports exposed (bot uses polling, not webhooks)
- Monitors all 550 Bybit USDT perpetuals
