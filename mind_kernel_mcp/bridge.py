import asyncio
import boto3
import json
import os
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from typing import Any, List, Union
from mcp.types import TextContent, ImageContent, EmbeddedResource

app = Server("mind-kernel-mcp-bridge")

# Configuration
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME", "MindKernelFunction")

# Initialize Boto3 Client for Lambda
lambda_client = boto3.client(
    "lambda",
    region_name=AWS_REGION,
    endpoint_url=AWS_ENDPOINT_URL,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test")
)

@app.list_tools()
async def list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="fetch_mind_kernel_core",
            description="Fetch core.json from private Mind Kernel repository via Lambda.",
            inputSchema={
                "type": "object",
                "properties": {
                    "userId": {
                        "type": "string",
                        "description": "User ID for authentication lookup."
                    }
                },
                "required": ["userId"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[Union[TextContent, ImageContent, EmbeddedResource]]:
    if name == "fetch_mind_kernel_core":
        try:
            # Payload for Lambda
            payload = {
                "tool": name,
                "arguments": arguments
            }
            
            # Invoke Lambda
            response = lambda_client.invoke(
                FunctionName=FUNCTION_NAME,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            # Parse Response
            payload_stream = response['Payload']
            result_json = json.loads(payload_stream.read())
            
            # Parse Lambda Function Result
            if result_json.get("status") == "success":
                return [
                    TextContent(
                        type="text",
                        text=result_json.get("content", "")
                    )
                ]
            else:
                 error_msg = result_json.get("message", "Unknown error from Lambda")
                 return [
                    TextContent(
                        type="text",
                        text=f"Error from Lambda: {error_msg}"
                    )
                ]

        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Bridge Error invoking Lambda: {str(e)}"
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

if __name__ == "__main__":
    print(f"Starting MCP Bridge connecting to Lambda: {FUNCTION_NAME} at {AWS_ENDPOINT_URL}", file=sys.stderr)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
