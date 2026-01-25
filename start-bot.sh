#!/bin/bash

# Start WhiteCat Bot

echo "🐱 Starting WhiteCat Bot..."
docker compose up -d

echo ""
echo "📊 Container status:"
docker compose ps

echo ""
echo "📋 Recent logs:"
docker compose logs --tail=20

echo ""
echo "✅ Bot started!"
echo "   View logs: docker compose logs -f"
