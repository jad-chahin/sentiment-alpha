# sentiment-alpha

Pulls data (e.g., from Reddit), processes it, and produces sentiment/report outputs.

## Prerequisites

- **Python 3.10+** (3.11 works great too)
- `pip` (comes with Python)

## Quickstart (Windows / macOS / Linux)

### 1) Clone and enter the project
```bash
git clone <YOUR_REPO_URL>
cd sentiment-alpha
```

### 2) Create a virtual environment (recommended)
```bash
python -m venv .venv
```

### 3) Activate the virtual environment

**Windows (Command Prompt):**
```bat
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux (bash/zsh):**
```bash
source .venv/bin/activate
```

### 4) Install dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> If your repo doesn’t have a `requirements.txt` yet, add one (see “Maintainer notes” below).

### 5) Configure credentials (required)

This project needs API credentials to run. Set them as environment variables.

Common ones (update to match your project):
- `OPENAI_API_KEY`
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`
- (Optional, if your Reddit auth requires it) `REDDIT_USERNAME`, `REDDIT_PASSWORD`

#### Set environment variables

**Windows (Command Prompt):**
```bat
set OPENAI_API_KEY=your_key_here
set REDDIT_CLIENT_ID=your_id_here
set REDDIT_CLIENT_SECRET=your_secret_here
set REDDIT_USER_AGENT=sentiment-alpha/1.0 by yourname
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="your_key_here"
$env:REDDIT_CLIENT_ID="your_id_here"
$env:REDDIT_CLIENT_SECRET="your_secret_here"
$env:REDDIT_USER_AGENT="sentiment-alpha/1.0 by yourname"
```

**macOS / Linux:**
```bash
export OPENAI_API_KEY="your_key_here"
export REDDIT_CLIENT_ID="your_id_here"
export REDDIT_CLIENT_SECRET="your_secret_here"
export REDDIT_USER_AGENT="sentiment-alpha/1.0 by yourname"
```

### 6) Run
```bash
python main.py
```

## What gets created / where output goes

- This repo includes a SQLite database file (`reddit_miner.db`). Depending on your settings, the app may create/update it during runs.
- Any generated reports/logs will be written wherever `report.py` / `pipeline.py` is configured to write them.

## Troubleshooting

### “pip not found” / wrong Python
Try:
```bash
python -m pip install -r requirements.txt
```

### PowerShell activation is blocked (Windows)
If activation fails in PowerShell, run:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
Then try activating again.

### Missing credentials / auth errors
Double-check your environment variables are set in the **same terminal session** where you run:
```bash
python main.py
```

## Maintainer notes (highly recommended)

### Add a `requirements.txt`
From a clean venv with everything installed:
```bash
pip freeze > requirements.txt
```

### Add `.gitignore` entries
Make sure you’re not committing secrets. Common ignores:
- `.venv/`
- `.env`
- `__pycache__/`
