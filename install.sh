#!/usr/bin/env bash
set -e

echo "🚀 Installazione AI Productivity Tracker..."

# crea ambiente virtuale
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "✅ Ambiente virtuale creato."
fi

# attiva venv
source .venv/bin/activate

# installa dipendenze
pip install --upgrade pip
pip install -r requirements.txt
echo "📦 Dipendenze installate."

# crea config se non esiste
CONFIG_FILE=".env"
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Inserisci la tua stringa MongoDB Atlas URI:"
  read -r MONGO_URI
  cat > "$CONFIG_FILE" <<EOF
  MONGO_URI="$MONGO_URI"
  DB_PATH="~/activity.db"
  MONGO_DB="agent_sessions"
  SYNC_INTERVAL=60
  TRACKING_INTERVAL=5
EOF
  echo "✅ Config salvata in $CONFIG_FILE"
else
  echo "⚙️  Config già presente."
fi

echo ""
echo "✅ Installazione completata!"
echo "Per avviare l'agent:"
echo ""
echo "  source .venv/bin/activate"
echo "  python main.py"
echo ""
