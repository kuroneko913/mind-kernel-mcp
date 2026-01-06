from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server
import mcp.types as types
from typing import Any, List, Union

from mind_kernel_mcp.tools import TOOL_DEFINITION, execute_fetch_tool, UPDATE_TOOL_DEFINITION, execute_update_tool
from mind_kernel_mcp.prompts import handle_list_prompts, handle_get_prompt
import os

app = Server("mind-kernel-mcp")

@app.list_prompts()
async def list_prompts() -> List[types.Prompt]:
    return await handle_list_prompts()

@app.get_prompt()
async def get_prompt(name: str, arguments: Any) -> types.GetPromptResult:
    # Local server might not have auth context easily?
    # Or we can assume a default user_id env var for local usage.
    user_id = os.environ.get("LOCAL_USER_ID", "test-user")
    return await handle_get_prompt(name, arguments, user_id)

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
