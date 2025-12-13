from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server
import mcp.types as types
from typing import Any, List, Union

from mind_kernel_mcp.tools import TOOL_DEFINITION, execute_fetch_tool, UPDATE_TOOL_DEFINITION, execute_update_tool

app = Server("mind-kernel-mcp")

@app.list_tools()
async def list_tools() -> List[types.Tool]:
    # Adapt dict definition to mcp.types.Tool
    return [
        types.Tool(
            name=TOOL_DEFINITION["name"],
            description=TOOL_DEFINITION["description"],
            inputSchema=TOOL_DEFINITION["inputSchema"]
        ),
        types.Tool(
            name=UPDATE_TOOL_DEFINITION["name"],
            description=UPDATE_TOOL_DEFINITION["description"],
            inputSchema=UPDATE_TOOL_DEFINITION["inputSchema"]
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[Union[TextContent, ImageContent, EmbeddedResource]]:
    if name == TOOL_DEFINITION["name"]:
        try:
            content = execute_fetch_tool(arguments)
            return [
                TextContent(
                    type="text",
                    text=content
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error executing tool: {str(e)}"
                )
            ]
            
    elif name == UPDATE_TOOL_DEFINITION["name"]:
        try:
            content = execute_update_tool(arguments)
            return [
                TextContent(
                    type="text",
                    text=content
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error executing tool: {str(e)}"
                )
            ]

    raise ValueError(f"Unknown tool: {name}")

async def run():
    async with stdio_server() as (read, write):
        await app.run(
            read_stream=read,
            write_stream=write,
            initialization_options=app.create_initialization_options()
        )
