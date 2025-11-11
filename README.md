# Activity Tracker

Monitora l'attività dell'utente e sincronizza con MongoDB.

## Installazione

```bash
# Crea virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# Installa dipendenze
pip install -r requirements.txt

# Configura .env
cp .env.example .env
# Modifica .env con le tue credenziali
```

## Configurazione

Crea file `.env` nella root:

```env
DB_PATH=~/activity.db
MONGO_URI=mongodb://localhost:27017
MONGO_DB=productivity
SYNC_INTERVAL=5
TRACKING_INTERVAL=60
```

## Utilizzo

```bash
python main.py
```

## Struttura

- `config/` - Configurazione
- `core/` - Logica business
- `gui/` - Interfaccia grafica
- `utils/` - Utilities
- `tests/` - Test unitari

## Build

```bash
pyinstaller -w -F --add-data ".env:." --name "AgentTracker" main.py
```
