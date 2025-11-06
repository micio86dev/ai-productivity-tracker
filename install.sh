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
  echo "MONGO_URI=\"$MONGO_URI\"" > "$CONFIG_FILE"
  echo "✅ Config salvata in $CONFIG_FILE"
else
  echo "⚙️  Config già presente."
fi

echo ""
echo "✅ Installazione completata!"
echo "Per avviare l'agent:"
echo ""
echo "  source .venv/bin/activate"
echo "  python agent_tracker.py"
echo ""
