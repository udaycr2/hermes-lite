#!/usr/bin/env python3
"""Web search tool using DDGS"""

from .agent_core import BaseTool, ToolResult
from typing import List, Dict

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


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
        if DDGS is None:
            return ToolResult(error="ddgs not installed. Run: pip install ddgs")
        
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
            return ToolResult(result=results)
        except Exception as e:
            return ToolResult(error=str(e))
