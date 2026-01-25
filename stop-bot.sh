#!/bin/bash

# Stop WhiteCat Bot

echo "🐱 Stopping WhiteCat Bot..."
docker compose stop

echo ""
echo "📊 Container status:"
docker compose ps

echo ""
echo "✅ Bot stopped!"
