# Netease Mail Daily Report Agent

Daily Email Intelligence System:

Netease IMAP -> Parse & Filter -> LLM Summary -> Feishu Push

## 1. Features
- Read new emails from the last 24 hours via IMAP.
- Parse sender/subject/time/body preview.
- Filter emails by configurable rules (`config/rules.yaml`).
- Generate daily summary with OpenAI-compatible API or Ollama.
- Push report to Feishu group bot webhook.
- Persist processed message IDs to avoid duplicate summaries.
- Support Windows Task Scheduler with PowerShell scripts.

## 2. Project Structure

```text
netease-mail-agent/
├── config/rules.yaml
├── logs/
├── scripts/install.ps1
├── scripts/run_daily.ps1
├── src/
│   ├── main.py
│   ├── llm/
│   │   ├── prompt.py
│   │   └── summarizer.py
│   ├── mail/
│   │   ├── filter.py
│   │   ├── imap_client.py
│   │   └── parser.py
│   ├── notify/feishu.py
│   └── storage/
│       ├── database.py
│       └── state.json
├── .env.example
├── .gitignore
└── requirements.txt
```

## 3. Quick Start

1) Create virtual environment and install dependencies:

```powershell
./scripts/install.ps1
```

2) Copy `.env.example` to `.env`, then fill real secrets.

3) Update `config/rules.yaml` if needed.

4) Run once manually:

```powershell
python src/main.py
```

Dry-run mode (no Feishu sending):

```powershell
python src/main.py --dry-run
```

## 4. Environment Variables

Required:
- `MAIL_USER`
- `MAIL_PASS` (Netease app password)
- `FEISHU_WEBHOOK`

IMAP/SMTP (defaults provided):
- `IMAP_HOST=imap.163.com`
- `IMAP_PORT=993`

LLM OpenAI-compatible:
- `LLM_PROVIDER=openai`
- `LLM_API_KEY`
- `LLM_API_BASE`
- `LLM_MODEL`

LLM Ollama:
- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
- `LLM_MODEL`

Optional:
- `MAIL_LOOKBACK_HOURS=24`
- `MAIL_FETCH_LIMIT=100`
- `LOG_LEVEL=INFO`

## 5. Windows Task Scheduler

Create a daily task to run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File E:\Projects\netease-mail-agent\scripts\run_daily.ps1
```

Suggested trigger: every day at 08:30.

## 6. Security

- Never commit `.env`.
- `src/storage/state.json` stores only processed email IDs.
- Logs are written to `logs/`.
