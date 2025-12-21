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

# Import tools dynamically
from mind_kernel_mcp.tools import PUBLIC_TOOL_DEFINITIONS

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



# Monkeypatch types.Tool to allow extra fields (specifically _meta)
try:
    # Try Pydantic v2 style
    types.Tool.model_config["extra"] = "allow"
except (AttributeError, KeyError):
    # Try Pydantic v1 style
    if hasattr(types.Tool, "Config"):
        types.Tool.Config.extra = "allow"

@app.list_tools()
async def list_tools() -> List[types.Tool]:
    tools = []
    for tool_def in PUBLIC_TOOL_DEFINITIONS:
        # Now that we patched Tool to allow extras, we can pass _meta directly
        # constructing the kwargs dynamically
        tool_kwargs = {
            "name": tool_def["name"],
            "description": tool_def["description"],
            "inputSchema": tool_def["inputSchema"]
        }
        if "_meta" in tool_def:
            tool_kwargs["_meta"] = tool_def["_meta"]
            
        tools.append(types.Tool(**tool_kwargs))
    return tools

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[Union[TextContent, ImageContent, EmbeddedResource]]:
    try:
        # Construct JSON-RPC Payload for sse.py
        rpc_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            },
            "id": 1
        }

        # Wrap in Mock API Gateway Event for Mangum
        # Mangum expects an event that looks like API Gateway Proxy Request
        api_gateway_event = {
            "resource": "/",
            "path": "/",
            "httpMethod": "POST",
            "httpMethod": "POST",
            "headers": {
                "Content-Type": "application/json",
                "X-API-Key": os.getenv("MCP_API_KEY", "")
            },
            "multiValueHeaders": {},
            "queryStringParameters": None,
            "multiValueQueryStringParameters": None,
            "pathParameters": None,
            "stageVariables": None,
            "requestContext": {
                "resourceId": "mock-id",
                "resourcePath": "/",
                "httpMethod": "POST",
                "requestId": "mock-request-id",
                "accountId": "123456789012",
                "identity": {"apiKey": "", "sourceIp": "127.0.0.1"},
                "stage": "test"
            },
            "body": json.dumps(rpc_payload),
            "isBase64Encoded": False
        }
        
        # Invoke Lambda
        response = lambda_client.invoke(
            FunctionName=FUNCTION_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(api_gateway_event)
        )
        
        # Parse Response
        payload_stream = response['Payload']
        response_data = json.loads(payload_stream.read())
        
        # Response might be raw JSON-RPC response or AWS Lambda Web Adapter proxy response
        # Since we are invoking directly via invoke API but expecting Adapter to handle it...
        # Adapter usually wraps HTTP response. But if we invoke with JSON payload that looks like RPC...
        
        # Actually, if we use invoke(), the adapter might just pass it through if configured for RPC?
        # No, adapter converts Lambda Event to HTTP Request.
        # However, for direct invoke, it might be tricky. 
        # But our simple sse.py handles JSON body.
        
        # Let's check response structure. 
        # If it returns proxy response: statusCode, body etc.
        
        if "body" in response_data:
             body_str = response_data["body"]
             rpc_response = json.loads(body_str)
        else:
             rpc_response = response_data

        if "result" in rpc_response:
             # Extract content from result
             result_content = rpc_response["result"].get("content", [])
             # Convert back to MCP types if needed, or assume it matches
             return [
                 TextContent(type=c["type"], text=c["text"]) for c in result_content if c["type"] == "text"
             ]
        elif "error" in rpc_response:
             error_msg = rpc_response["error"].get("message", "Unknown error")
             return [
                TextContent(
                    type="text",
                    text=f"Error from Lambda (RPC): {error_msg}"
                )
            ]
        else:
             return [
                TextContent(
                    type="text",
                    text=f"Unexpected response from Lambda: {response_data}"
                )
             ]

    except Exception as e:
        return [
            TextContent(
                type="text",
                text=f"Bridge Error invoking Lambda: {str(e)}"
            )
        ]

@app.list_resources()
async def list_resources() -> List[types.Resource]:
    return [
        types.Resource(
            uri="ui://widget/backlog.html",
            name="Backlog Widget",
            description="React Widget for displaying backlog items.",
            mimeType="text/html+skybridge"
        )
    ]


class ResourceWrapper:
    def __init__(self, uri, mimeType, text):
        self.uri = uri
        self.mimeType = mimeType
        self.mime_type = mimeType # sdk wants snake_case
        self.text = text
        self.blob = text 
        self.content = text # sdk wants content

@app.read_resource()
async def read_resource(uri: Any) -> List[ResourceWrapper]:
    # Handle both string and pydantic.AnyUrl
    uri_str = str(uri)
    
    if "ui://widget/backlog.html" in uri_str:
        try:
             # Load JS and CSS from web/dist relative to current working directory
             base_path = os.path.join(os.getcwd(), "web", "dist")
             
             with open(os.path.join(base_path, "widget.js"), "r", encoding="utf-8") as f:
                 js_content = f.read()
             
             # CSS might be optional or in js
             css_path = os.path.join(base_path, "widget.css")
             if os.path.exists(css_path):
                 with open(css_path, "r", encoding="utf-8") as f:
                     css_content = f.read()
             else:
                 css_content = ""

             # Template
             html = f"""
<div id="backlog-root"></div>
<style>
{css_content}
</style>
<script type="module">
{js_content}
</script>
""".strip()
             return [
                 ResourceWrapper(
                     uri=uri_str,
                     mimeType="text/html+skybridge",
                     text=html
                 )
             ]
        except Exception as e:
            raise ValueError(f"Error loading widget: {str(e)}")
    
    raise ValueError(f"Resource not found: {uri}")

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
