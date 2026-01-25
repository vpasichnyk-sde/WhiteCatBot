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

# Check if requirements.txt or Dockerfile changed
CHANGED_FILES=$(git diff --name-only HEAD@{1} HEAD 2>/dev/null || echo "")

if echo "$CHANGED_FILES" | grep -qE "requirements.txt|Dockerfile"; then
    echo "🔨 Detected changes in requirements.txt or Dockerfile"
    echo "🔨 Rebuilding Docker image..."
    docker compose up -d --build
else
    echo "✅ No rebuild needed, just restarting..."
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
