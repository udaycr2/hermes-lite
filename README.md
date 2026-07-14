# Hermes Lite - Lightweight AI Agent

A minimal, efficient AI agent optimized for weak hardware. Built by stripping down Hermes to essentials: 6 tools, native function calling, streaming responses, and full Telegram integration.

---

## Quick Start

```bash
cd /home/ubuntu/hermes-lite
source venv/bin/activate

# CLI mode
python3 cli.py

# Single query
python3 cli.py -q "Search for Python asyncio"

# Telegram bot (requires credentials)
export TELEGRAM_BOT_TOKEN='your_token'
export TELEGRAM_ADMIN_ID='your_user_id'
python3 telegram_bot.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Hermes Lite                             │
├─────────────────────────────────────────────────────────────┤
│  Telegram Bot (telegram_bot.py)                             │
│  ├─ Streaming responses                                     │
│  ├─ Persistent config/  Config via slash commands                                 │
│  └─ Admin-only access (optional)                           │
├─────────────────────────────────────────────────────────────┤
│  Agent Core (agent/agent_core.py)                           │
│  ├─ Native OpenAI-compatible function calling              │
│  ├─ Context trimming (max 5 turns)                         │
│  ├─ Tool timeout: configurable (default 300s)              │
│  └─ Personality system (technical/concise/helpful)         │
├─────────────────────────────────────────────────────────────┤
│  Tools (6 total)                                            │
│  ├─ terminal      - Shell commands                          │
│  ├─ web_search    - DuckDuckGo via DDGS                    │
│  ├─ file          - Read/write/list/delete                 │
│  ├─ cronjob       - Schedule recurring tasks               │
│  ├─ session_search- Search conversation history            │
│  └─ memory        - Persistent key-value store             │
├─────────────────────────────────────────────────────────────┤
│  Ollama (granite4.1:3b)                                     │
│  └─ Native function calling API                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
/home/ubuntu/hermes-lite/
├── agent/
│   └── agent_core.py          # Main agent implementation
├── config/
│   ├── config.yaml            # Base agent config
│   └── telegram_config.json   # Telegram bot settings (auto-saved)
├── memory/
│   └── agent_memory.json      # Persistent key-value memory
├── sessions/
│   └── *.json                 # Conversation history
├── cron/
│   └── jobs.json              # Scheduled cron jobs
├── logs/
│   └── hermes-lite.log        # Application logs
├── scripts/
│   ├── cron_manager.py        # Cron management utilities
│   └── session_search.py      # Session search utilities
├── bin/
│   └── hermes-lite            # CLI wrapper script
├── telegram_bot.py            # Telegram bot with streaming
├── cli.py                     # CLI entry point
├── requirements.txt           # Python dependencies
├── SOUL.md                    # Agent identity/personality
└── venv/                      # Python virtual environment
```

---

## Configuration

### Base Config (`config/config.yaml`)

```yaml
model:
  default: "granite4.1:3b"
  provider: "ollama"
  base_url: "http://localhost:11434/v1"
  context_length: 4096
  max_tokens: 1024
  temperature: 0.3
  top_p: 0.9
  reasoning_effort: false

agent:
  max_turns: 10
  max_context_tokens: 2048
  max_turns_history: 5
  max_tool_calls_per_turn: 3
  timeout_seconds: 60
  personality: "technical"

tools:
  enabled:
    - terminal
    - web_search
    - file
    - cronjob
    - session_search
    - memory

performance:
  max_context_tokens: 2048
  max_turns: 10
  max_tool_calls_per_turn: 3
  timeout_seconds: 60
  max_tokens_per_response: 1024
```

### Telegram Config (`config/telegram_config.json`)

Auto-saved when changed via slash commands:

```json
{
  "model": "granite4.1:3b",
  "provider": "ollama",
  "base_url": "http://localhost:11434/v1",
  "max_tokens": 1024,
  "temperature": 0.3,
  "top_p": 0.9,
  "max_context_tokens": 2048,
  "max_turns": 10,
  "max_tool_calls_per_turn": 3,
  "tool_timeout_seconds": 300,
  "streaming_enabled": true,
  "personality": "technical"
}
```

---

## Tools Reference

### 1. Terminal
Execute shell commands on host system.

```json
{
  "command": "string",
  "timeout": 60,
  "cwd": "."
}
```

**Examples:**
- `Run df -h /`
- `Execute: ls -la /home`
- `Run hostname`

### 2. Web Search
Search web via DuckDuckGo (DDGS).

```json
{
  "query": "string",
  "max_results": 5
}
```

**Examples:**
- `Search for Python asyncio tutorial`
- `Find Ampere CPU specifications`

### 3. File
Read, write, list, delete files.

```json
{
  "action": "read|write|list|delete",
  "path": "string",
  "content": "string"
}
```

**Examples:**
- `Write hello to /tmp/test.txt`
- `Read /etc/hostname`
- `List /home/ubuntu`

### 4. Cronjob
Manage scheduled jobs.

```json
{
  "action": "add|remove|list|run",
  "schedule": "0 * * * *",
  "command": "string",
  "name": "string",
  "job_id": "string"
}
```

**Examples:**
- `Create cron: echo hello every hour`
- `List cron jobs`
- `Remove cron job abc123`

### 5. Session Search
Search conversation history.

```json
{
  "action": "search|list",
  "query": "string",
  "limit": 5
}
```

**Examples:**
- `Search sessions for hello`
- `List recent sessions`

### 6. Memory
Persistent key-value store.

```json
{
  "action": "get|set|delete|list|clear",
  "key": "string",
  "value": "string"
}
```

**Examples:**
- `Set memory key foo to bar`
- `Get memory key foo`
- `List memory`

---

## Telegram Bot Commands

### Basic Commands
| Command | Description |
|---------|-------------|
| `/start` | Welcome message with current config |
| `/help` | Full help text |
| `/tools` | List available tools |
| `/status` | Show agent status |
| `/config` | Show current configuration |
| `/clear` | Reset conversation session |

### Configuration Commands
| Command | Description | Example |
|---------|-------------|---------|
| `/model` | Change Ollama model | `/model` → reply `granite4.1:8b` |
| `/context` | Change context length | `/context` → reply `4096` |
| `/persona` | Change personality | `/persona` → reply `concise` |
| `/tooltimeout` | Change tool timeout (s) | `/tooltimeout` → reply `600` |
| `/stream` | Toggle streaming | `/stream` |

### Available Models
- `granite4.1:3b` (default, fast, 2.1GB)
- `granite4.1:8b` (better quality, 5.3GB)
- `granite4:1b` (small, 3.3GB)
- `granite4:350m-h` (tiny, 366MB)

### Personalities
- `technical` - Linux admin, concise, direct (default)
- `concise` - Brief, to the point
- `helpful` - Friendly, explanatory

### Context Length Range
- Minimum: 512 tokens
- Maximum: 8192 tokens
- Default: 2048 tokens

### Tool Timeout Range
- Minimum: 30 seconds
- Maximum: 1800 seconds (30 minutes)
- Default: 300 seconds (5 minutes)

---

## Systemd Service

### Service File: `/etc/systemd/system/hermes-lite-telegram.service`

```ini
[Unit]
Description=Hermes Lite Telegram Bot
After=network.target ollama.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/hermes-lite
Environment=TELEGRAM_BOT_TOKEN=***
Environment=TELEGRAM_ADMIN_ID=***
ExecStart=/home/ubuntu/hermes-lite/venv/bin/python telegram_bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Service Management
```bash
# Start/stop/restart
sudo systemctl start hermes-lite-telegram
sudo systemctl stop hermes-lite-telegram
sudo systemctl restart hermes-lite-telegram

# Enable auto-start
sudo systemctl enable hermes-lite-telegram

# View logs
sudo journalctl -u hermes-lite-telegram -f
sudo journalctl -u hermes-lite-telegram -n 50
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather |
| `TELEGRAM_ADMIN_ID` | No | Your Telegram user ID (restricts access) |

---

## Ollama Setup

Ensure Ollama is running with the model:

```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Pull model if needed
ollama pull granite4.1:3b

# Start Ollama (if not running)
ollama serve
```

---

## Usage Examples

### CLI Mode
```bash
cd /home/ubuntu/hermes-lite
source venv/bin/activate

# Interactive
python3 cli.py

# Single queries
python3 cli.py -q "Run df -h /"
python3 cli.py -q "Search for Linux kernel 6.10"
python3 cli.py -q "Create cron: echo hello every 5 minutes"
python3 cli.py -q "Write test to /tmp/test.txt"
python3 cli.py -q "Set memory key api_key to secret123"
```

### Telegram Mode
Just message the bot naturally:
- "Search for Python asyncio best practices"
- "Run uname -a in terminal"
- "Create a cron job that runs date every hour"
- "Write hello world to /home/user/test.txt"
- "Set memory key server_ip to 192.168.1.100"
- "Search sessions for cron"

---

## Performance Tuning

### For Weaker Hardware
- Reduce `max_context_tokens` to 1024
- Reduce `max_turns` to 5
- Use `granite4:350m-h` model
- Disable streaming: `/stream`

### For Better Quality
- Increase `max_context_tokens` to 4096
- Use `granite4.1:8b` model
- Increase `max_tokens` to 2048

---

## Troubleshooting

### Bot not responding
```bash
# Check service status
sudo systemctl status hermes-lite-telegram

# View logs
sudo journalctl -u hermes-lite-telegram -n 50
```

### Ollama connection failed
```bash
# Verify Ollama running
curl http://localhost:11434/api/tags

# Check model available
ollama list
```

### Tool timeout
Increase timeout via Telegram: `/tooltimeout 600`

### Memory issues
Clear session: `/clear`
Check memory file size: `ls -lh memory/agent_memory.json`

---

## Files to Backup

```bash
# Configuration
config/config.yaml
config/telegram_config.json

# Data
memory/agent_memory.json
cron/jobs.json
sessions/*.json

# Systemd
/etc/systemd/system/hermes-lite-telegram.service
```

---

## License
MIT License - Built as lightweight derivative of Hermes Agent (Nous Research)
