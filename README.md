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
