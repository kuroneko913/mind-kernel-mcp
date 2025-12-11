from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server
import mcp.types as types
from typing import Any, List, Union

from .services import DynamoDBSecretStore, GitHubContentProvider

app = Server("mind-kernel-mcp")

@app.list_tools()
async def list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="fetch_mind_kernel_core",
            description="プライベートなMind Kernelリポジトリから core.json ファイルを取得します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "userId": {
                        "type": "string",
                        "description": "認証情報を取得するためのユーザーID。"
                    }
                },
                "required": ["userId"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[Union[TextContent, ImageContent, EmbeddedResource]]:
    if name == "fetch_mind_kernel_core":
        user_id = arguments.get("userId")
        if not user_id:
            raise ValueError("userId は必須です")

        try:
            secret_store = DynamoDBSecretStore()
            token = secret_store.get_github_token(user_id)
            
            content_provider = GitHubContentProvider(token)
            core_json_content = content_provider.fetch_core_json()
            
            return [
                TextContent(
                    type="text",
                    text=core_json_content
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"core.json の取得中にエラーが発生しました: {str(e)}"
                )
            ]

    raise ValueError(f"不明なツールです: {name}")

async def run():
    async with stdio_server() as (read, write):
        await app.run(
            read_stream=read,
            write_stream=write,
            initialization_options=app.create_initialization_options()
        )
