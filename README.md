# UV Sync

## Installation

### 1. Install Node.js dependencies

```bash
cd js
npm init
cd ..
```

### 2. Activate Python virtual environment

**For Windows (PowerShell):**
```powershell
.\.venv\Scripts\activate.ps1
```

**For Bash (Linux/macOS):**
```bash
source .venv/bin/activate
```

## How to Run

### Server environment (headless / without GUI)

**Terminal 1:**
```bash
xvfb-run -a node js/server.js
```

**Terminal 2:**
```bash
python3 main.py
```

### Local environment (with GUI access)

**Terminal 1:**
```bash
node js/server.js
```

**Terminal 2:**
```bash
python3 main.py
```

## Project Architecture 
```bash
├── main.py                     # Entry point
├── .env                        # Configuration 
├── recordings/                 # Saved session data
│   ├── audio/                  # .webm audio chunks
│   ├── transcripts/            # Text transcripts and speaker data
│   └── full/                   # Merged outputs (text, audio, JSON)
├── js/                          
│   ├── meet_record.js          # Main automation script (logs in, joins Meet, streams audio + speaker data)
│   ├── first_login.js          # Separate login flow with 2FA handling
│   └── server.js               # Express.js API server for controlling the bot
├── src/
│   └── backend/
│       ├── core/
│       │   └── facade.py               # Orchestrates the entire flow
│       ├── audio/
│       │   ├── audio_server.py         # WebSocket server for audio input
│       │   ├── chunk_handler.py        # Handles buffering and chunk finalization
│       │   ├── transcript_manager.py   # Sends audio to Whisper and saves results
│       │   └── speaker_tracker.py      # Tracks active speakers
│       ├── llm/
│       │   └── transcriber.py          # OpenAI Whisper API wrapper
│       ├── api/
│       │   └── js_plagin_api.py        # HTTP client for Node.js server
│       └── utils/
│           └── logger.py               # Custom logger
```