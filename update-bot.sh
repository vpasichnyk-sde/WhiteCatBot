#!/bin/bash

# WhiteCat Bot Update Script
# This script pulls the latest changes from git and restarts the bot

set -e  # Exit on any error

echo "🐱 WhiteCat Bot Update Script"
echo "================================"

# Check if we're in the right directory
if [ ! -f "bot.py" ]; then
    echo "❌ Error: bot.py not found. Are you in the correct directory?"
    exit 1
fi

# Stop the bot
echo "⏸️  Stopping bot..."
docker compose stop

# Pull latest changes from git
echo "📥 Pulling latest changes from git..."
git pull

# Check if there were any changes
CHANGED_FILES=$(git diff --name-only HEAD@{1} HEAD 2>/dev/null || echo "")

if [ -n "$CHANGED_FILES" ]; then
    echo "🔨 Detected changes, rebuilding Docker image..."
    echo "Changed files:"
    echo "$CHANGED_FILES" | sed 's/^/  - /'
    docker compose up -d --build
else
    echo "✅ No changes detected, just restarting..."
    docker compose up -d
fi

# Wait a moment for the bot to start
sleep 3

# Check status
echo ""
echo "📊 Container status:"
docker compose ps

echo ""
echo "📋 Recent logs:"
docker compose logs --tail=20

echo ""
echo "✅ Update complete!"
echo ""
echo "Useful commands:"
echo "  View logs:     docker compose logs -f"
echo "  Stop bot:      docker compose stop"
echo "  Start bot:     docker compose start"
echo "  Restart bot:   docker compose restart"
