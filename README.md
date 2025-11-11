# 🧠 AI Productivity Tracker

Un piccolo **agent Python** che registra in background le tue attività al computer (finestra attiva, utilizzo CPU, ecc.) e sincronizza automaticamente i dati su **MongoDB Atlas**.

L’obiettivo è raccogliere dati reali sui tuoi pattern di lavoro per analizzarli e creare un sistema di produttività personalizzato.

---

## 🚀 Funzionalità

- Rileva finestra e processo attivo ogni 10 secondi
- Registra l’uso della CPU
- Salva i dati in locale su **SQLite** (`~/activity.db`)
- Sincronizza periodicamente (ogni 5 minuti) con **MongoDB Atlas**
- Funziona in background

---

## 🧩 Requisiti

- Python ≥ 3.8
- Accesso a un cluster **MongoDB Atlas**
- Sistema operativo: macOS, Linux o Windows
- Git (opzionale, se cloni il repo)

---

## ⚙️ Setup

1. **Clona il progetto**

   ```bash
   git clone https://github.com/tuo-user/ai-productivity-tracker.git
   cd ai-productivity-tracker
   ```

2. **Lancia l’installazione automatica**

```bash
chmod +x install.sh
./install.sh
```

3. **Avvio manuale**

```bash
source .venv/bin/activate
python agent_tracker.py
```

In background (Linux/macOS):

```bash
nohup python agent_tracker.py &
```

Ferma con `Ctrl + C` o cercando il processo:

```bash
pkill -f agent_tracker.py
```

4. **SQLite (locale)**
   File: `~/activity.db`

5. **Generazione eseguibile**

```bash
pip install pyinstaller
pyinstaller -w -F --add-data ".env:." --name "AgentTracker" agent_tracker.py
```

Questo genera un binario in:

- dist/agent_tracker (macOS/Linux)
- dist/agent_tracker.exe (Windows)

🧠 Su Windows usa ; invece di : per separare percorsi:

```csharp
--add-data ".env;."
```

⚙️ **Test rapido**

```bash
./dist/agent_tracker
```
