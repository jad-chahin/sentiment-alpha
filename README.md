# sentiment-alpha

Pulls data (e.g., from Reddit), processes it, and produces sentiment/report outputs.

## Prerequisites

- **Python 3.10+** (3.11 works great too)
- `pip` (comes with Python)

## Quickstart (Windows / macOS / Linux)

### 1) Clone and enter the project
```bash
git clone https://github.com/jad-chahin/sentiment-alpha.git
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

### 5) Run
```bash
python main.py

--shortcut flag: identify key financial terms before AI analysis to save time and tokens
--validate flag: verify all tickers at the end using Yahoo Finance information
```

***You will need to create a reddit client [here](https://www.reddit.com/prefs/apps)***
***You NEED OpenAI API access as of v1.0 but that is changing in the next version***
