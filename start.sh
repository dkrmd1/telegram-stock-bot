#!/bin/bash

echo "🚀 Starting Telegram Stock Bot..."

# Check if required environment variables are set
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ Error: TELEGRAM_BOT_TOKEN environment variable is required"
    echo "Set it in Railway dashboard: Variables tab"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY environment variable is required"
    echo "Set it in Railway dashboard: Variables tab"
    exit 1
fi

echo "✅ Environment variables validated"
echo "🤖 Starting bot..."

# Start the bot
python stock_bot.py