#!/bin/bash
# Quick ngrok setup for SalesBreachPro webhook testing

echo "Starting SalesBreachPro with Ngrok webhook..."
echo

# Default port
PORT=5000

# Check if custom port provided
if [ "$1" != "" ]; then
    PORT=$1
fi

echo "Using port: $PORT"
echo

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Run the ngrok setup script
python3 setup_ngrok_webhook.py $PORT

echo
echo "Setup complete! Keep this terminal open to maintain the ngrok tunnel."