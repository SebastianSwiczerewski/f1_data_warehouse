#!/usr/bin/env bash
set -e
set -x

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

clear
echo "🚀 Starting F1 Data Warehouse..."


# .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo "⚠️  .env file not found. Creating from .env.example..."
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
fi

echo "Building images..."
docker compose \
  --env-file "$PROJECT_DIR/.env" \
  -f "$PROJECT_DIR/docker/docker-compose.yml" \
  build 

echo "Starting containers..."
docker compose \
  --env-file "$PROJECT_DIR/.env" \
  -f "$PROJECT_DIR/docker/docker-compose.yml" \
  up -d 
# temporarly removed for development> /dev/null 2>&1

echo "Launching dashboard..."
python -m cli.pipeline_cli