# JobBot — Automated Job Application Platform

A fully local, AI-powered job application bot. Scrapes every job portal every minute, auto-applies using a local LLM (Ollama), and connects to you via Telegram.

## Features

- **Telegram Integration** — Send any job link to your Telegram bot and it applies instantly with top priority
- **100% Local LLM** — Uses Ollama (Llama 3, Mistral, Phi, etc.) — no API keys, no external calls
- **Scrapes All Job Portals** — LinkedIn, Indeed, Glassdoor, ZipRecruiter, Dice, Monster, and any career page
- **Scrapes Every Minute** — Never miss a fresh posting
- **Human-like Automation** — Playwright browser with stealth mode, random delays, mouse simulation
- **Smart Form Filling** — LLM generates cover letters, answers screening questions, fills every form field
- **Rich Filter System** — Location, years of experience, field, domain, skills, salary, work authorization, visa sponsorship
- **Priority Queue** — Telegram jobs always applied first
- **Stuck Handling** — If blocked, asks you via Telegram with Skip / Retry / Manual buttons
- **Applications Dashboard** — Real-time tracking of every application attempt

## Requirements

| Dependency | Version | Install |
|-----------|---------|---------|
| Python    | 3.10+   | [python.org](https://python.org) |
| Node.js   | 18+     | [nodejs.org](https://nodejs.org) |
| Ollama    | Latest  | [ollama.ai](https://ollama.ai) |

## Installation

### Windows
```bat
install.bat
```

### macOS / Linux
```bash
chmod +x install.sh start.sh
./install.sh
```

## Starting JobBot

### Windows
```bat
start.bat
```

### macOS / Linux
```bash
./start.sh
```

Then open **http://localhost:8000** in your browser.

## Quick Start

1. **Set up your profile** → Go to *My Profile* and fill in all your details + upload your resume
2. **Configure filters** → Go to *Filters* and set location, experience, domains, skills
3. **Set up Telegram** → Go to *Telegram* and connect your bot (get token from @BotFather)
4. **Choose your LLM** → Go to *Settings*, check Ollama is running, pick a model
5. **Start scraping** → Dashboard shows live stats; use "Scrape Now" or wait for auto-scrape

## Telegram Commands

| Command | Description |
|---------|-------------|
| (send job URL) | Apply to that job immediately with priority |
| `/status` | View application stats |
| `/pause` | Pause auto-apply |
| `/resume` | Resume auto-apply |
| `/help` | Show help |

## Supported Job Portals

- LinkedIn (Easy Apply + external)
- Indeed
- Glassdoor
- ZipRecruiter
- Dice
- Monster
- Any company career page (generic scraper)
- ATS platforms: Lever, Greenhouse, Workday, iCIMS, Taleo, SmartRecruiters, Jobvite

## Local LLM Models (via Ollama)

```bash
ollama pull llama3       # Best quality (8B)
ollama pull mistral      # Fast and capable (7B)
ollama pull phi3         # Lightweight (3.8B)
ollama pull gemma        # Google's model (7B)
```

## Project Structure

```
jobbot/
├── backend/
│   ├── main.py                  # FastAPI app + WebSocket
│   ├── config.py                # Settings
│   ├── database.py              # SQLite + SQLAlchemy
│   ├── models/                  # Database models
│   ├── schemas/                 # Pydantic schemas
│   ├── api/v1/                  # REST API endpoints
│   ├── services/
│   │   ├── scraper/             # Portal scrapers (Playwright)
│   │   ├── applier/             # Auto-apply engine
│   │   ├── llm/                 # Ollama LLM integration
│   │   ├── telegram/            # Telegram bot
│   │   ├── scheduler/           # APScheduler
│   │   └── filters/             # Job scoring engine
│   └── workers/                 # Scrape + apply workers
└── frontend/
    └── src/
        ├── pages/               # Dashboard, Jobs, Profile, etc.
        ├── components/          # Reusable UI components
        ├── api/                 # API client functions
        └── hooks/               # WebSocket hook
```

## Environment Variables (.env)

```env
TELEGRAM_BOT_TOKEN=your_token    # From @BotFather
TELEGRAM_CHAT_ID=your_chat_id   # From @userinfobot
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3
HEADLESS=true                    # Set false to watch browser
SCRAPE_INTERVAL_MINUTES=1
AUTO_APPLY=true
```

## Privacy

All data stays on your machine:
- SQLite database at `data/jobbot.db`
- Resumes at `data/resumes/`
- Screenshots at `data/screenshots/`
- No data sent to any external service except job portals and your Telegram bot
