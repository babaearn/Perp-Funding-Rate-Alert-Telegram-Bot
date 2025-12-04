#!/bin/bash
# Start both command handler and alert monitor

cd /Users/jm/staging/perp-funding-rate-bot

# Kill any existing processes
pkill -9 -f "command_handler.py" 2>/dev/null
pkill -9 -f "alert_monitor.py" 2>/dev/null
sleep 2

echo "Starting Funding Rate Bot..."
echo ""

# Start command handler (fast response to /funding commands)
caffeinate -i python3 command_handler.py &
CMD_PID=$!
echo "✅ Command Handler started (PID: $CMD_PID)"

# Wait for command handler to initialize
sleep 3

# Start alert monitor (funding rate alerts)
caffeinate -i python3 alert_monitor.py &
ALERT_PID=$!
echo "✅ Alert Monitor started (PID: $ALERT_PID)"

echo ""
echo "Both processes running!"
echo "Command Handler PID: $CMD_PID"
echo "Alert Monitor PID: $ALERT_PID"
echo ""
echo "To stop: pkill -f 'command_handler.py' && pkill -f 'alert_monitor.py'"
