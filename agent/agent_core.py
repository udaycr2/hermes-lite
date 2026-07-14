#!/usr/bin/env python3
"""
Hermes Lite - Lightweight Agent Core (Native Function Calling)
Minimal agent for weak hardware (Ampere instance)
Optimized for: web search, terminal, system analysis, cron, coding
"""

import os
import sys
import json
import yaml
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
import subprocess

# Setup paths
HERMES_LITE_HOME = Path(__file__).parent.parent
CONFIG_PATH = HERMES_LITE_HOME / "config" / "config.yaml"
LOGS_DIR = HERMES_LITE_HOME / "logs"
MEMORY_DIR = HERMES_LITE_HOME / "memory"
SESSIONS_DIR = HERMES_LITE_HOME / "sessions"
SCRIPTS_DIR = HERMES_LITE_HOME / "scripts"

for d in [LOGS_DIR, MEMORY_DIR, SESSIONS_DIR, SCRIPTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "hermes-lite.log"),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("hermes-lite")


@dataclass
class Config:
    """Minimal configuration"""
    model: str = "granite4.1:3b"
    provider: str = "ollama"
    base_url: str = "http://localhost:11434/v1"
    context_length: int = 4096
    max_tokens: int = 1024
    temperature: float = 0.3
    top_p: float = 0.9
    reasoning_effort: bool = False
    max_turns: int = 10
    max_context_tokens: int = 2048
    max_turns_history: int = 5
    max_tool_calls_per_turn: int = 3
    timeout_seconds: int = 60
    enabled_tools: List[str] = field(default_factory=lambda: [
        "terminal", "web_search", "file", "cronjob", "session_search", "memory"
    ])
    personality: str = "technical"
    verbose: bool = False
    
    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f)
                if data:
                    model_cfg = data.get("model", {})
                    agent_cfg = data.get("agent", {})
                    tools_cfg = data.get("tools", {})
                    perf_cfg = data.get("performance", {})
                    return cls(
                        model=model_cfg.get("default", "granite4.1:3b"),
                        provider=model_cfg.get("provider", "ollama"),
                        base_url=model_cfg.get("base_url", "http://localhost:11434/v1"),
                        context_length=model_cfg.get("context_length", 4096),
                        max_tokens=model_cfg.get("max_tokens", 1024),
                        temperature=model_cfg.get("temperature", 0.3),
                        top_p=model_cfg.get("top_p", 0.9),
                        reasoning_effort=model_cfg.get("reasoning_effort", False),
                        max_turns=agent_cfg.get("max_turns", 10),
                        max_context_tokens=perf_cfg.get("max_context_tokens", 2048),
                        max_turns_history=perf_cfg.get("max_turns", 5),
                        max_tool_calls_per_turn=perf_cfg.get("max_tool_calls_per_turn", 3),
                        timeout_seconds=perf_cfg.get("timeout_seconds", 60),
                        enabled_tools=tools_cfg.get("enabled", [
                            "terminal", "web_search", "file", "cronjob", "session_search", "memory"
                        ]),
                        personality=agent_cfg.get("personality", "technical"),
                    )
        return cls()


@dataclass
class Message:
    role: str
    content: str = ""
    tool_calls: List[Dict] = field(default_factory=list)
    tool_call_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ToolResult:
    result: Any = None
    error: str = None


class BaseTool(ABC):
    """Base tool class"""
    name: str = ""
    description: str = ""
    parameters: Dict = {}
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass


class TerminalTool(BaseTool):
    name = "terminal"
    description = "Execute shell commands on the host system"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
            "cwd": {"type": "string", "description": "Working directory", "default": "."}
        },
        "required": ["command"]
    }
    
    async def execute(self, command: str, timeout: int = 60, cwd: str = ".") -> ToolResult:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return ToolResult(result=output)
        except subprocess.TimeoutExpired:
            return ToolResult(error=f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(error=str(e))


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web using DuckDuckGo"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results", "default": 5}
        },
        "required": ["query"]
    }
    
    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        try:
            from ddgs import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
            return ToolResult(result=results)
        except ImportError:
            return ToolResult(error="ddgs not installed. Run: pip install ddgs")
        except Exception as e:
            return ToolResult(error=str(e))


class FileTool(BaseTool):
    name = "file"
    description = "Read, write, list files"
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["read", "write", "list", "delete"], "description": "Action to perform"},
            "path": {"type": "string", "description": "File/directory path"},
            "content": {"type": "string", "description": "Content for write action"}
        },
        "required": ["action", "path"]
    }
    
    async def execute(self, action: str, path: str, content: str = "") -> ToolResult:
        try:
            p = Path(path).expanduser()
            if action == "read":
                if not p.exists():
                    return ToolResult(error=f"File not found: {path}")
                return ToolResult(result=p.read_text())
            elif action == "write":
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
                return ToolResult(result=f"Written {len(content)} chars to {path}")
            elif action == "list":
                if not p.exists():
                    return ToolResult(error=f"Path not found: {path}")
                if p.is_file():
                    return ToolResult(result=str(p))
                items = [{"name": f.name, "type": "dir" if f.is_dir() else "file", "size": f.stat().st_size if f.is_file() else 0} for f in p.iterdir()]
                return ToolResult(result=items)
            elif action == "delete":
                if not p.exists():
                    return ToolResult(error=f"Path not found: {path}")
                if p.is_dir():
                    import shutil
                    shutil.rmtree(p)
                else:
                    p.unlink()
                return ToolResult(result=f"Deleted {path}")
        except Exception as e:
            return ToolResult(error=str(e))


class CronJobTool(BaseTool):
    name = "cronjob"
    description = "Manage scheduled cron jobs"
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "remove", "list", "run"], "description": "Action to perform"},
            "schedule": {"type": "string", "description": "Cron schedule (e.g., '0 9 * * *' or 'every 1h')"},
            "command": {"type": "string", "description": "Command to run"},
            "name": {"type": "string", "description": "Job name"},
            "job_id": {"type": "string", "description": "Job ID for remove/run actions"}
        },
        "required": ["action"]
    }
    
    def __init__(self):
        self.jobs_file = HERMES_LITE_HOME / "cron" / "jobs.json"
        self.jobs_file.parent.mkdir(exist_ok=True)
        self.jobs = self._load_jobs()
    
    def _load_jobs(self) -> Dict:
        if self.jobs_file.exists():
            try:
                return json.loads(self.jobs_file.read_text())
            except:
                return {}
        return {}
    
    def _save_jobs(self):
        self.jobs_file.write_text(json.dumps(self.jobs, indent=2))
    
    async def execute(self, action: str, schedule: str = "", command: str = "", name: str = "", job_id: str = "") -> ToolResult:
        try:
            if action == "add":
                if not schedule or not command:
                    return ToolResult(error="schedule and command required for add")
                job_id = job_id or str(uuid.uuid4())[:8]
                self.jobs[job_id] = {
                    "id": job_id,
                    "name": name or job_id,
                    "schedule": schedule,
                    "command": command,
                    "created": datetime.now().isoformat(),
                    "enabled": True
                }
                self._save_jobs()
                return ToolResult(result=f"Added job {job_id}: {self.jobs[job_id]['name']}")
            
            elif action == "remove":
                if not job_id or job_id not in self.jobs:
                    return ToolResult(error=f"Job not found: {job_id}")
                del self.jobs[job_id]
                self._save_jobs()
                return ToolResult(result=f"Removed job {job_id}")
            
            elif action == "list":
                return ToolResult(result=list(self.jobs.values()))
            
            elif action == "run":
                if not job_id or job_id not in self.jobs:
                    return ToolResult(error=f"Job not found: {job_id}")
                job = self.jobs[job_id]
                result = subprocess.run(
                    job["command"],
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                job["last_run"] = datetime.now().isoformat()
                job["last_result"] = {
                    "stdout": result.stdout[-1000:],
                    "stderr": result.stderr[-1000:],
                    "returncode": result.returncode
                }
                self._save_jobs()
                return ToolResult(result=job["last_result"])
        except Exception as e:
            return ToolResult(error=str(e))


class SessionSearchTool(BaseTool):
    name = "session_search"
    description = "Search conversation history"
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["search", "list"], "description": "Action to perform"},
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results", "default": 5}
        },
        "required": ["action"]
    }
    
    async def execute(self, action: str, query: str = "", limit: int = 5) -> ToolResult:
        try:
            if action == "search":
                if not query:
                    return ToolResult(error="query required for search")
                results = []
                query_lower = query.lower()
                for session_file in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
                    try:
                        data = json.loads(session_file.read_text())
                        for msg in data.get("messages", []):
                            if query_lower in msg.get("content", "").lower():
                                results.append({
                                    "session_id": data.get("session_id"),
                                    "timestamp": data.get("timestamp"),
                                    "role": msg.get("role"),
                                    "snippet": msg.get("content", "")[:200]
                                })
                                if len(results) >= limit:
                                    return ToolResult(result=results)
                    except:
                        continue
                return ToolResult(result=results)
            
            elif action == "list":
                results = []
                for session_file in sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:limit]:
                    try:
                        data = json.loads(session_file.read_text())
                        results.append({
                            "session_id": data.get("session_id"),
                            "timestamp": data.get("timestamp"),
                            "message_count": len(data.get("messages", [])),
                            "first_msg": data.get("messages", [{}])[0].get("content", "")[:100]
                        })
                    except:
                        continue
                return ToolResult(result=results)
        except Exception as e:
            return ToolResult(error=str(e))


class MemoryTool(BaseTool):
    name = "memory"
    description = "Persistent key-value memory store"
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["get", "set", "delete", "list", "clear"], "description": "Action to perform"},
            "key": {"type": "string", "description": "Memory key"},
            "value": {"type": "string", "description": "Value for set action"}
        },
        "required": ["action"]
    }
    
    def __init__(self):
        self.memory_file = MEMORY_DIR / "agent_memory.json"
        self.memory = self._load_memory()
    
    def _load_memory(self) -> Dict:
        if self.memory_file.exists():
            try:
                return json.loads(self.memory_file.read_text())
            except:
                return {}
        return {}
    
    def _save_memory(self):
        self.memory_file.write_text(json.dumps(self.memory, indent=2))
    
    async def execute(self, action: str, key: str = "", value: str = "") -> ToolResult:
        try:
            if action == "get":
                return ToolResult(result=self.memory.get(key, "Key not found"))
            
            elif action == "set":
                if not key:
                    return ToolResult(error="key required for set")
                self.memory[key] = value
                # Enforce limits
                if len(self.memory) > 50:
                    oldest = min(self.memory.keys())
                    del self.memory[oldest]
                self._save_memory()
                return ToolResult(result=f"Set {key}")
            
            elif action == "delete":
                if key in self.memory:
                    del self.memory[key]
                    self._save_memory()
                    return ToolResult(result=f"Deleted {key}")
                return ToolResult(error="Key not found")
            
            elif action == "list":
                return ToolResult(result=list(self.memory.items()))
            
            elif action == "clear":
                self.memory = {}
                self._save_memory()
                return ToolResult(result="Memory cleared")
        except Exception as e:
            return ToolResult(error=str(e))


class HermesLiteAgent:
    """Main lightweight agent using native function calling"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session_id = str(uuid.uuid4())[:8]
        self.messages: List[Message] = []
        
        # Initialize tools
        self.tools: Dict[str, BaseTool] = {}
        self._init_tools()
        
        # Load system prompt
        self._load_system_prompt()
        
        logger.info(f"Hermes Lite started - Session: {self.session_id}")
        logger.info(f"Model: {config.model}, Tools: {list(self.tools.keys())}")
    
    def _init_tools(self):
        tool_classes = {
            "terminal": TerminalTool,
            "web_search": WebSearchTool,
            "file": FileTool,
            "cronjob": CronJobTool,
            "session_search": SessionSearchTool,
            "memory": MemoryTool
        }
        
        for name in self.config.enabled_tools:
            if name in tool_classes:
                self.tools[name] = tool_classes[name]()
                logger.debug(f"Loaded tool: {name}")
    
    def _load_system_prompt(self):
        personalities = {
            "technical": "You are a technical expert and Linux administrator with root shell access. Use web search for factual data. Use tools to give accurate data. Be concise, technical, and direct. No fluff, no examples unless asked.",
            "concise": "You are a concise assistant. Keep responses brief and to the point. Use tools when needed.",
            "helpful": "You are a helpful, friendly AI assistant. Use tools to assist the user."
        }
        self.system_prompt = personalities.get(self.config.personality, personalities["technical"])
    
    def _build_tool_schemas(self) -> List[Dict]:
        schemas = []
        for tool in self.tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return schemas
    
    def _trim_context(self, messages: List[Message]) -> List[Message]:
        """Trim context to fit within max_turns_history"""
        if len(messages) <= self.config.max_turns_history * 2:
            return messages
        return messages[-(self.config.max_turns_history * 2):]
    
    async def _call_model(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        """Call the LLM API"""
        try:
            import httpx
        except ImportError:
            return {"error": "httpx not installed. Run: pip install httpx"}
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "stream": False
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(
                    f"{self.config.base_url}/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            return {"error": f"Cannot connect to {self.config.base_url}. Is Ollama running?"}
        except httpx.TimeoutException:
            return {"error": f"Request timed out after {self.config.timeout_seconds}s"}
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            return {"error": str(e)}
    
    async def run(self, user_input: str) -> str:
        """Run one turn of the agent"""
        # Add user message
        self.messages.append(Message("user", user_input))
        
        # Build messages for API
        api_messages = [{"role": "system", "content": self.system_prompt}]
        for msg in self._trim_context(self.messages):
            api_messages.append({"role": msg.role, "content": msg.content})
            if msg.tool_calls:
                api_messages.append({"role": "assistant", "tool_calls": msg.tool_calls})
            if msg.tool_call_id:
                api_messages.append({"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content})
        
        # Call model with tools
        tools_schema = self._build_tool_schemas()
        response = await self._call_model(api_messages, tools_schema)
        
        if "error" in response:
            return f"Error: {response['error']}"
        
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})
        
        # Handle tool calls
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            # Add assistant message with tool calls
            self.messages.append(Message("assistant", message.get("content", ""), tool_calls=tool_calls))
            
            # Execute tools
            for tc in tool_calls[:self.config.max_tool_calls_per_turn]:
                tool_name = tc["function"]["name"]
                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}
                
                if tool_name in self.tools:
                    result = await self.tools[tool_name].execute(**tool_args)
                    result_content = json.dumps({"result": result.result, "error": result.error}) if result.error else json.dumps(result.result)
                else:
                    result_content = json.dumps({"error": f"Unknown tool: {tool_name}"})
                
                # Add tool result
                self.messages.append(Message("tool", result_content, tool_call_id=tc["id"]))
            
            # Get final response after tools
            api_messages = [{"role": "system", "content": self.system_prompt}]
            for msg in self._trim_context(self.messages):
                api_messages.append({"role": msg.role, "content": msg.content})
                if msg.tool_calls:
                    api_messages.append({"role": "assistant", "tool_calls": msg.tool_calls})
                if msg.tool_call_id:
                    api_messages.append({"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content})
            
            response = await self._call_model(api_messages)
            if "error" in response:
                return f"Error: {response['error']}"
            
            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})
        
        # Add final assistant message
        content = message.get("content", "")
        self.messages.append(Message("assistant", content))
        
        # Save session
        self._save_session()
        
        return content
    
    def _save_session(self):
        session_file = SESSIONS_DIR / f"{self.session_id}.json"
        data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": m.role, "content": m.content, "tool_calls": m.tool_calls, "tool_call_id": m.tool_call_id, "timestamp": m.timestamp}
                for m in self.messages
            ]
        }
        session_file.write_text(json.dumps(data, indent=2))
    
    def get_tool_list(self) -> List[Dict]:
        return [{"name": t.name, "description": t.description} for t in self.tools.values()]


async def main():
    """Interactive main loop"""
    config = Config.load()
    agent = HermesLiteAgent(config)
    
    print(f"Hermes Lite - Model: {config.model}")
    print(f"Tools: {', '.join(agent.tools.keys())}")
    print(f"Context: {config.max_context_tokens} tokens, {config.max_turns_history} turns")
    print("Type 'exit' to quit\n")
    
    while True:
        try:
            user_input = input("> ").strip()
            if user_input.lower() in ("exit", "quit", "q"):
                break
            if not user_input:
                continue
            
            response = await agent.run(user_input)
            print(f"\n{response}\n")
        except KeyboardInterrupt:
            break
        except EOFError:
            break
    
    print("\nGoodbye!")


if __name__ == "__main__":
    asyncio.run(main())
