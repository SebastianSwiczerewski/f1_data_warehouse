#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

open_browser() {
  URL="http://localhost:3000"

  if [[ "$OSTYPE" == "darwin"* ]]; then
    open "$URL"
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open "$URL"
  elif [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]]; then
    start "$URL"
  else
    echo "⚠️ Please open $URL manually in your browser."
  fi
}

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

echo "Checking CLI dependencies..."
if ! python -c "import rich" &> /dev/null; then
  echo "📦 Installing CLI dependencies..."
  pip install -r requirements.txt > /dev/null 2>&1
fi

echo "Launching dashboard..."

sleep 2

clear
python -m cli.pipeline_cli

echo ""
echo "✅ Pipeline finished successfully!"
echo "🌐 Opening Metabase dashboard..."
echo "Metabase available at: http://localhost:3000"
sleep 2

open_browser