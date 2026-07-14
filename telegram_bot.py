#!/usr/bin/env python3
"""
Lightweight Telegram Bot for Hermes Lite - Streaming Version
Supports: streaming, configurable timeouts, model/context/persona via slash commands
"""

import os
import asyncio
import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

import sys
sys.path.insert(0, str(Path(__file__).parent / "agent"))

from agent.agent_core import HermesLiteAgent, Config, Message

# ─── Configuration ──────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "config" / "telegram_config.json"

@dataclass
class BotConfig:
    """Persistent bot configuration"""
    model: str = "granite4.1:3b"
    provider: str = "ollama"
    base_url: str = "http://localhost:11434/v1"
    max_tokens: int = 1024
    temperature: float = 0.3
    top_p: float = 0.9
    max_context_tokens: int = 2048
    max_turns: int = 10
    max_tool_calls_per_turn: int = 3
    tool_timeout_seconds: int = 300  # 5 minutes for tool calls
    streaming_enabled: bool = True
    personality: str = "technical"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BotConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

def load_bot_config() -> BotConfig:
    if CONFIG_FILE.exists():
        try:
            return BotConfig.from_dict(json.loads(CONFIG_FILE.read_text()))
        except:
            pass
    return BotConfig()

def save_bot_config(cfg: BotConfig):
    CONFIG_FILE.parent.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg.to_dict(), indent=2))

# ─── Global State ──────────────────────────────────────────────────────
bot_config = load_bot_config()
agent: Optional[HermesLiteAgent] = None
AUTHORIZED_USERS = set()
ADMIN_USER_ID = None

# Conversation states
MODEL_CHOICE, CONTEXT_LENGTH, PERSONALITY_NAME, TOOL_TIMEOUT = range(4)

# ─── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Agent Factory ─────────────────────────────────────────────────────
def create_agent() -> HermesLiteAgent:
    """Create agent with current bot config"""
    cfg = Config(
        model=bot_config.model,
        provider=bot_config.provider,
        base_url=bot_config.base_url,
        context_length=bot_config.max_context_tokens,
        max_tokens=bot_config.max_tokens,
        temperature=bot_config.temperature,
        top_p=bot_config.top_p,
        max_turns=bot_config.max_turns,
        max_context_tokens=bot_config.max_context_tokens,
        max_turns_history=bot_config.max_turns,
        max_tool_calls_per_turn=bot_config.max_tool_calls_per_turn,
        timeout_seconds=bot_config.tool_timeout_seconds,
        personality=bot_config.personality,
    )
    return HermesLiteAgent(cfg)

def reload_agent():
    """Reload agent with updated config"""
    global agent
    agent = create_agent()
    logger.info(f"Agent reloaded: model={bot_config.model}, timeout={bot_config.tool_timeout_seconds}s")

# ─── Streaming Helper ──────────────────────────────────────────────────
async def stream_model_response(messages: List[Dict], tools: List[Dict] = None) -> str:
    """Stream response from model and return full text"""
    import httpx
    
    payload = {
        "model": bot_config.model,
        "messages": messages,
        "max_tokens": bot_config.max_tokens,
        "temperature": bot_config.temperature,
        "top_p": bot_config.top_p,
        "stream": bot_config.streaming_enabled,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    
    full_response = ""
    async with httpx.AsyncClient(timeout=bot_config.tool_timeout_seconds) as client:
        async with client.stream(
            "POST",
            f"{bot_config.base_url}/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            full_response += delta["content"]
                    except:
                        pass
    return full_response

# ─── Slash Commands ────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if AUTHORIZED_USERS and user.id not in AUTHORIZED_USERS:
        await update.message.reply_text("Unauthorized.")
        return
    await update.message.reply_text(
        f"🤖 Hermes Lite Ready\n"
        f"Model: {bot_config.model}\n"
        f"Context: {bot_config.max_context_tokens} tokens\n"
        f"Timeout: {bot_config.tool_timeout_seconds}s\n"
        f"Streaming: {'On' if bot_config.streaming_enabled else 'Off'}\n"
        f"Personality: {bot_config.personality}\n\n"
        f"Commands:\n"
        f"/help - Help\n"
        f"/tools - Tools\n"
        f"/config - Current settings\n"
        f"/model - Change model\n"
        f"/context - Change context length\n"
        f"/personality - Change personality\n"
        f"/timeout - Change tool timeout\n"
        f"/stream - Toggle streaming\n"
        f"/clear - Clear session\n"
        f"/status - Full status"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Hermes Lite Commands\n\n"
        "Just send messages naturally.\n\n"
        "Examples:\n"
        "• Search for Python asyncio\n"
        "• Run df -h / in terminal\n"
        "• Create cron: echo hello every hour\n"
        "• Write hello to /tmp/test.txt\n"
        "• Set memory key foo to bar\n\n"
        "Config Commands:\n"
        "/model - Change model\n"
        "/context - Change context (512-8192)\n"
        "/personality - technical/concise/helpful\n"
        "/timeout - Tool timeout in seconds\n"
        "/stream - Toggle streaming\n"
        "/clear - Reset session\n"
        "/status - Show all settings"
    )

async def tools_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tool_list = agent.get_tool_list()
    text = "🔧 Available Tools:\n\n"
    for t in tool_list:
        text += f"• {t['name']}: {t['description']}\n"
    await update.message.reply_text(text)

async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"⚙️ Current Configuration\n\n"
        f"Model: {bot_config.model}\n"
        f"Provider: {bot_config.provider}\n"
        f"Base URL: {bot_config.base_url}\n"
        f"Max Tokens: {bot_config.max_tokens}\n"
        f"Temperature: {bot_config.temperature}\n"
        f"Top-p: {bot_config.top_p}\n"
        f"Max Context: {bot_config.max_context_tokens}\n"
        f"Max Turns: {bot_config.max_turns}\n"
        f"Max Tool Calls/Turn: {bot_config.max_tool_calls_per_turn}\n"
        f"Tool Timeout: {bot_config.tool_timeout_seconds}s\n"
        f"Streaming: {'Enabled' if bot_config.streaming_enabled else 'Disabled'}\n"
        f"Personality: {bot_config.personality}\n\n"
        f"Session: {agent.session_id}"
    )
    await update.message.reply_text(text)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import json
    memory_file = Path(__file__).parent / "memory" / "agent_memory.json"
    sessions_dir = Path(__file__).parent / "sessions"
    cron_dir = Path(__file__).parent / "cron"
    
    memory_count = 0
    if memory_file.exists():
        try:
            memory_count = len(json.loads(memory_file.read_text()).get("entries", {}))
        except: pass
    
    text = (
        f"📊 Hermes Lite Status\n\n"
        f"Model: {bot_config.model}\n"
        f"Context: {bot_config.max_context_tokens} tokens\n"
        f"Tool Timeout: {bot_config.tool_timeout_seconds}s\n"
        f"Streaming: {'On' if bot_config.streaming_enabled else 'Off'}\n"
        f"Personality: {bot_config.personality}\n\n"
        f"Memory entries: {memory_count}\n"
        f"Sessions: {len(list(sessions_dir.glob('*.json')))}\n"
        f"Cron jobs: {len(json.loads((cron_dir / 'jobs.json').read_text()) if (cron_dir / 'jobs.json').exists() else {})}"
        f"Tools: {len(agent.tools)}\n"
        f"Current session: {agent.session_id}"
    )
    await update.message.reply_text(text)

async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global agent
    agent = create_agent()
    await update.message.reply_text("✅ Session cleared. New conversation started.")

# ─── Model Change ──────────────────────────────────────────────────────
async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 Select Model:\n\n"
        "Available:\n"
        "• granite4.1:3b (default, fast)\n"
        "• granite4.1:8b (better quality)\n"
        "• granite4:1b (small)\n"
        "• granite4:350m-h (tiny)\n\n"
        "Reply with model name or /cancel"
    )
    await update.message.reply_text(text)
    return MODEL_CHOICE

async def model_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    model = update.message.text.strip()
    valid_models = ["granite4.1:3b", "granite4.1:8b", "granite4:1b", "granite4:350m-h"]
    
    if model not in valid_models:
        await update.message.reply_text(f"❌ Invalid. Choose from: {', '.join(valid_models)}")
        return MODEL_CHOICE
    
    bot_config.model = model
    save_bot_config(bot_config)
    reload_agent()
    await update.message.reply_text(f"✅ Model changed to {model}")
    return ConversationHandler.END

# ─── Context Length ────────────────────────────────────────────────────
async def context_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📏 Current context: {bot_config.max_context_tokens} tokens\n\n"
        f"Enter new value (512-8192):"
    )
    return CONTEXT_LENGTH

async def context_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = int(update.message.text.strip())
        if not 512 <= val <= 8192:
            await update.message.reply_text("❌ Must be 512-8192")
            return CONTEXT_LENGTH
    except ValueError:
        await update.message.reply_text("❌ Invalid number")
        return CONTEXT_LENGTH
    
    bot_config.max_context_tokens = val
    bot_config.max_turns = min(bot_config.max_turns, val // 200)
    save_bot_config(bot_config)
    reload_agent()
    await update.message.reply_text(f"✅ Context length set to {val} tokens")
    return ConversationHandler.END

# ─── Personality ───────────────────────────────────────────────────────
async def personality_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"🎭 Current: {bot_config.personality}\n\n"
        "Choose:\n"
        "• technical - Linux admin, concise, direct\n"
        "• concise - Brief, to the point\n"
        "• helpful - Friendly, explanatory\n\n"
        "Reply with name or /cancel"
    )
    await update.message.reply_text(text)
    return PERSONALITY_NAME

async def personality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip().lower()
    valid = ["technical", "concise", "helpful"]
    
    if name not in valid:
        await update.message.reply_text(f"❌ Choose: {', '.join(valid)}")
        return PERSONALITY_NAME
    
    bot_config.personality = name
    save_bot_config(bot_config)
    reload_agent()
    await update.message.reply_text(f"✅ Personality: {name}")
    return ConversationHandler.END

# ─── Tool Timeout ──────────────────────────────────────────────────────
async def timeout_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⏱ Current tool timeout: {bot_config.tool_timeout_seconds}s\n\n"
        f"Enter seconds (30-1800):"
    )
    return TOOL_TIMEOUT

async def timeout_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = int(update.message.text.strip())
        if not 30 <= val <= 1800:
            await update.message.reply_text("❌ Must be 30-1800")
            return TOOL_TIMEOUT
    except ValueError:
        await update.message.reply_text("❌ Invalid number")
        return TOOL_TIMEOUT
    
    bot_config.tool_timeout_seconds = val
    save_bot_config(bot_config)
    reload_agent()
    await update.message.reply_text(f"✅ Tool timeout: {val}s")
    return ConversationHandler.END

# ─── Streaming Toggle ──────────────────────────────────────────────────
async def stream_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_config.streaming_enabled = not bot_config.streaming_enabled
    save_bot_config(bot_config)
    reload_agent()
    await update.message.reply_text(f"✅ Streaming: {'Enabled' if bot_config.streaming_enabled else 'Disabled'}")

# ─── Cancel ────────────────────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled")
    return ConversationHandler.END

# ─── Message Handler with Streaming ────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if AUTHORIZED_USERS and user.id not in AUTHORIZED_USERS:
        await update.message.reply_text("Unauthorized.")
        return
    
    # Send persistent typing indicator
    typing_task = asyncio.create_task(send_typing(update, context))
    
    user_input = update.message.text
    
    try:
        # Use agent's run method (handles tool calls internally)
        response = await agent.run(user_input)
        
        typing_task.cancel()
        
        # Send response (split if long)
        if len(response) <= 4096:
            await update.message.reply_text(response)
        else:
            for i in range(0, len(response), 4096):
                await update.message.reply_text(response[i:i+4096])
                
    except Exception as e:
        typing_task.cancel()
        logger.error(f"Agent error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def send_typing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Keep sending typing action until cancelled"""
    try:
        while True:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action="typing"
            )
            await asyncio.sleep(4)  # Telegram typing lasts ~5s
    except asyncio.CancelledError:
        pass

# ─── Error Handler ─────────────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# ─── Main ──────────────────────────────────────────────────────────────
def main():
    global agent, ADMIN_USER_ID, AUTHORIZED_USERS
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not set")
        print("   export TELEGRAM_BOT_TOKEN='your_token'")
        return 1
    
    admin_id = os.environ.get("TELEGRAM_ADMIN_ID")
    if admin_id:
        ADMIN_USER_ID = int(admin_id)
        AUTHORIZED_USERS.add(ADMIN_USER_ID)
        print(f"🔒 Admin: {ADMIN_USER_ID}")
    
    # Initialize agent
    agent = create_agent()
    
    print(f"🤖 Starting Hermes Lite Telegram Bot")
    print(f"   Model: {bot_config.model}")
    print(f"   Context: {bot_config.max_context_tokens}")
    print(f"   Timeout: {bot_config.tool_timeout_seconds}s")
    print(f"   Streaming: {bot_config.streaming_enabled}")
    print(f"   Personality: {bot_config.personality}")
    print(f"   Tools: {list(agent.tools.keys())}")
    
    # Build application
    application = Application.builder().token(bot_token).build()
    
    # Conversation handlers for config
    model_conv = ConversationHandler(
        entry_points=[CommandHandler("model", model_cmd)],
        states={MODEL_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_choice)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    context_conv = ConversationHandler(
        entry_points=[CommandHandler("context", context_cmd)],
        states={CONTEXT_LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, context_choice)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    personality_conv = ConversationHandler(
        entry_points=[CommandHandler("personality", personality_cmd)],
        states={PERSONALITY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, personality_choice)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    timeout_conv = ConversationHandler(
        entry_points=[CommandHandler("timeout", timeout_cmd)],
        states={TOOL_TIMEOUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, timeout_choice)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("tools", tools_cmd))
    application.add_handler(CommandHandler("config", config_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("clear", clear_cmd))
    application.add_handler(CommandHandler("stream", stream_cmd))
    application.add_handler(model_conv)
    application.add_handler(context_conv)
    application.add_handler(personality_conv)
    application.add_handler(timeout_conv)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    print("✅ Bot running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
