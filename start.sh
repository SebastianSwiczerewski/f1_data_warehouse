#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

clear
echo ""
echo "🚀 Starting F1 Data Warehouse"
echo ""

# .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo "⚠️  .env file not found. Creating from .env.example..."
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
fi

echo "Building images..."
docker compose \
  --env-file "$PROJECT_DIR/.env" \
  -f "$PROJECT_DIR/docker/docker-compose.yml" \
  build > /dev/null 2>&1

echo "Starting containers..."
docker compose \
  --env-file "$PROJECT_DIR/.env" \
  -f "$PROJECT_DIR/docker/docker-compose.yml" \
  up -d > /dev/null 2>&1

echo "Launching dashboard..."

sleep 1

clear
python -m cli.pipeline_cli