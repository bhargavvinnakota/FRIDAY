"""
Friday :: MCP (Model Context Protocol) Manager
Orchestrates connections to MCP servers (stdio/SSE).
Enables standardized tool-use across diverse backends.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
MCP_CONFIG = FRIDAY_ROOT / "config" / "mcp_servers.json"

class MCPManager:
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.server_configs: Dict[str, Any] = self._load_config()
        self.tools: List[Dict] = []

    def _load_config(self) -> Dict:
        if not MCP_CONFIG.exists():
            # Default config: local filesystem MCP
            default = {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", str(FRIDAY_ROOT)]
                }
            }
            MCP_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            with open(MCP_CONFIG, "w") as f:
                json.dump(default, f, indent=2)
            return default
        with open(MCP_CONFIG, "r") as f:
            return json.load(f)

    async def connect_all(self):
        """Initialize connections to all configured MCP servers."""
        for name, cfg in self.server_configs.items():
            try:
                await self.connect_server(name, cfg)
            except Exception as e:
                print(f"MCP Warning: Failed to connect to {name}: {e}")

    async def connect_server(self, name: str, cfg: Dict):
        """Connect to a single MCP server via stdio."""
        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env={**os.environ, **cfg.get("env", {})}
        )
        
        # Note: In a real long-running daemon, we'd handle the context managers properly
        # For Friday's current request-response flow, we'll use a simplified persistent session model
        async with stdio_client(params) as (read, write):
            session = ClientSession(read, write)
            await session.initialize()
            self.sessions[name] = session
            
            # Fetch tools
            tools_resp = await session.list_tools()
            for t in tools_resp.tools:
                self.tools.append({
                    "server": name,
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.inputSchema
                })
            print(f"MCP: Connected to {name} ({len(tools_resp.tools)} tools)")

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict) -> Any:
        """Invoke a tool on a specific MCP server."""
        if server_name not in self.sessions:
            # Try to connect on-demand
            if server_name in self.server_configs:
                await self.connect_server(server_name, self.server_configs[server_name])
            else:
                raise ValueError(f"MCP Server {server_name} not found in config.")
        
        session = self.sessions[server_name]
        return await session.call_tool(tool_name, arguments)

    def get_tool_definitions(self) -> List[Dict]:
        """Return tool metadata for LLM function calling."""
        return self.tools

# Simple test harness
if __name__ == "__main__":
    manager = MCPManager()
    async def test():
        await manager.connect_all()
        print(f"Available tools: {json.dumps(manager.get_tool_definitions(), indent=2)}")
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test())
