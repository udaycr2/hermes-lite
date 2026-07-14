#!/usr/bin/env python3
"""
Hermes Lite CLI - Lightweight entry point
"""

import sys
import asyncio
import argparse
from pathlib import Path

# Add agent to path
sys.path.insert(0, str(Path(__file__).parent / "agent"))

from agent_core import HermesLiteAgent, Config, main as agent_main


def create_parser():
    parser = argparse.ArgumentParser(
        description="Hermes Lite - Lightweight AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hermes-lite                    # Interactive mode
  hermes-lite -q "search query"  # Quick query
  hermes-lite --config custom.yaml  # Custom config
  hermes-lite --list-tools       # List available tools
        """
    )
    parser.add_argument(
        "-q", "--query",
        help="Single query mode (non-interactive)"
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to config file",
        default=str(Path(__file__).parent / "config" / "config.yaml")
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available tools and exit"
    )
    parser.add_argument(
        "--model",
        help="Override model (e.g., granite4.1:3b)"
    )
    parser.add_argument(
        "--provider",
        help="Override provider (ollama, openai, etc.)"
    )
    parser.add_argument(
        "--base-url",
        help="Override API base URL"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    return parser


async def run_single_query(agent: HermesLiteAgent, query: str) -> str:
    """Run a single query and return response"""
    return await agent.run(query)


def main():
    parser = create_parser()
    args = parser.parse_args()
    
    # Load config
    config = Config.load()
    
    # Override from CLI args
    if args.model:
        config.model = args.model
    if args.provider:
        config.provider = args.provider
    if args.base_url:
        config.base_url = args.base_url
    if args.verbose:
        config.verbose = True
        import logging
        logging.getLogger("hermes-lite").setLevel(logging.INFO)
    
    # Create agent
    agent = HermesLiteAgent(config)
    
    if args.list_tools:
        print("Available tools:")
        for tool in agent.get_tool_list():
            print(f"  {tool['name']}: {tool['description']}")
        return 0
    
    if args.query:
        # Single query mode
        try:
            response = asyncio.run(run_single_query(agent, args.query))
            print(response)
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    # Interactive mode
    try:
        asyncio.run(agent_main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
