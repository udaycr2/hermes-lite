#!/usr/bin/env python3
"""Session search for Hermes Lite"""
import json
import sys
from pathlib import Path
from datetime import datetime

SESSIONS_DIR = Path(__file__).parent.parent / "sessions"

def search(query: str, limit: int = 5) -> list:
    """Search sessions for query"""
    results = []
    query_lower = query.lower()
    
    for session_file in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(session_file.read_text())
            session_id = data.get("session_id", session_file.stem)
            timestamp = data.get("timestamp", "")
            
            for msg in data.get("messages", []):
                content = msg.get("content", "")
                if query_lower in content.lower():
                    results.append({
                        "session_id": session_id,
                        "timestamp": timestamp,
                        "role": msg.get("role", ""),
                        "snippet": content[:200]
                    })
                    if len(results) >= limit:
                        return results
        except:
            continue
    return results

def list_recent(limit: int = 10) -> list:
    """List recent sessions"""
    results = []
    for session_file in sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            data = json.loads(session_file.read_text())
            results.append({
                "session_id": data.get("session_id", session_file.stem),
                "timestamp": data.get("timestamp", ""),
                "message_count": len(data.get("messages", [])),
                "first_msg": data.get("messages", [{}])[0].get("content", "")[:100] if data.get("messages") else ""
            })
        except:
            continue
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: session_search.py <search|list> [query] [limit]")
        sys.exit(1)
    
    action = sys.argv[1]
    if action == "search" and len(sys.argv) >= 3:
        query = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        print(json.dumps(search(query, limit), indent=2))
    elif action == "list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        print(json.dumps(list_recent(limit), indent=2))
    else:
        print("Usage: session_search.py <search|list> [query] [limit]")
