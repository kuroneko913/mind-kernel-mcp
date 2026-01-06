import asyncio
import boto3
import json
import os
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from typing import Any, List, Union, Dict, Optional
from mcp.types import TextContent, ImageContent, EmbeddedResource, Tool, TextResourceContents, BlobResourceContents

# NOTE: No local tool definitions imported. We strictly rely on the remote Lambda.
# from mind_kernel_mcp.tools import PUBLIC_TOOL_DEFINITIONS (REMOVED)

app = Server("mind-kernel-mcp-bridge")

# Configuration
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME", "MindKernelFunction")
API_KEY = os.getenv("MCP_API_KEY", "")

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
    types.Tool.model_config["extra"] = "allow"
except (AttributeError, KeyError):
    if hasattr(types.Tool, "Config"):
        types.Tool.Config.extra = "allow"

async def invoke_jsonrpc(method: str, params: Dict[str, Any] = None) -> Union[Dict[str, Any], int, None]:
    """
    Invokes the Lambda function using a simulated API Gateway event containing the JSON-RPC payload.
    Returns the 'result' from the JSON-RPC response, or throws an error if 'error' is present.
    """
    if params is None:
        params = {}
    
    rpc_payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    
    # Wrap in Mock API Gateway Event for Mangum
    api_gateway_event = {
        "resource": "/",
        "path": "/",
        "httpMethod": "POST",
        "headers": {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        },
        "multiValueHeaders": {},
        "queryStringParameters": None,
        "pathParameters": None,
        "requestContext": {
             "resourceId": "mock-id",
             "resourcePath": "/",
             "httpMethod": "POST",
             "requestId": "mock-request-id",
             "identity": {"apiKey": "", "sourceIp": "127.0.0.1"},
             "stage": "test"
        },
        "body": json.dumps(rpc_payload),
        "isBase64Encoded": False
    }
    
    print(f"DEBUG: Invoking Lambda {FUNCTION_NAME} with method={method}", file=sys.stderr)
    
    try:
        response = lambda_client.invoke(
            FunctionName=FUNCTION_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(api_gateway_event)
        )
    except Exception as e:
        raise RuntimeError(f"AWS Lambda Invoke Failed: {str(e)}")
    
    payload_stream = response['Payload']
    response_data = json.loads(payload_stream.read())
    
    # Unwrap API Gateway response (Mangum)
    if "body" in response_data:
        try:
            rpc_response = json.loads(response_data["body"])
        except ValueError:
            # If body is not JSON?
            raise RuntimeError(f"Invalid JSON body from Lambda: {response_data['body']}")
    else:
        # Direct return (unlikely with Mangum but possible if misconfigured)
        rpc_response = response_data
    
    if "error" in rpc_response:
        error = rpc_response["error"]
        msg = error.get("message", "Unknown error")
        code = error.get("code", 0)
        raise RuntimeError(f"JSON-RPC Error ({code}): {msg}")
    
    if "result" in rpc_response:
        return rpc_response["result"]
    
    # Notification or empty?
    return None


# --- Tool Handlers ---

@app.list_tools()
async def list_tools() -> List[types.Tool]:
    result = await invoke_jsonrpc("tools/list")
    tools_data = result.get("tools", [])
    
    # Convert dicts to types.Tool
    # We use **kwargs unpacking to support _meta if present
    tools = []
    for t in tools_data:
        tools.append(types.Tool(**t))
    return tools

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[Union[TextContent, ImageContent, EmbeddedResource]]:
    # Bridge expects arguments to be a dict usually
    if not isinstance(arguments, dict):
        raise ValueError("Arguments must be a dictionary")

    try:
        result = await invoke_jsonrpc("tools/call", {"name": name, "arguments": arguments})
        
        # Result is expected to be { "content": [...] }
        content_list = result.get("content", [])
        
        # Convert to MCP Types
        mcp_content = []
        for c in content_list:
             if c.get("type") == "text":
                 mcp_content.append(TextContent(type="text", text=c.get("text")))
             elif c.get("type") == "image":
                 mcp_content.append(ImageContent(type="image", data=c.get("data"), mimeType=c.get("mimeType")))
             elif c.get("type") == "resource":
                 # EmbeddedResource?
                 # c might be different structure
                 pass
        
        return mcp_content
        
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# --- Resource Handlers ---

@app.list_resources()
async def list_resources() -> List[types.Resource]:
    try:
        result = await invoke_jsonrpc("resources/list")
        resources_data = result.get("resources", [])
        return [types.Resource(**r) for r in resources_data]
    except Exception as e:
        print(f"Error listing resources: {e}", file=sys.stderr)
        return []

class PatchedTextResourceContents(types.TextResourceContents):
    @property
    def content(self):
        return self.text
    @property
    def mime_type(self):
        return self.mimeType

class PatchedBlobResourceContents(types.BlobResourceContents):
    @property
    def content(self):
        return self.blob
    @property
    def mime_type(self):
        return self.mimeType

@app.read_resource()
async def read_resource(uri: Any) -> List[Any]:
    uri_str = str(uri)
    try:
        result = await invoke_jsonrpc("resources/read", {"uri": uri_str})
        contents = result.get("contents", [])
        
        res_list = []
        for c in contents:
            if "text" in c:
                res_list.append(PatchedTextResourceContents(
                    uri=c["uri"],
                    mimeType=c["mimeType"],
                    text=c["text"]
                ))
            elif "blob" in c:
                 res_list.append(PatchedBlobResourceContents(
                    uri=c["uri"],
                    mimeType=c["mimeType"],
                    blob=c["blob"]
                ))
        return res_list
        
    except RuntimeError as e:
        raise ValueError(str(e))


# --- Prompt Handlers ---

@app.list_prompts()
async def list_prompts() -> List[types.Prompt]:
    try:
        result = await invoke_jsonrpc("prompts/list")
        prompts_data = result.get("prompts", [])
        return [types.Prompt(**p) for p in prompts_data]
    except RuntimeError as e:
        print(f"Check if Lambda supports prompts: {e}", file=sys.stderr)
        return []

@app.get_prompt()
async def get_prompt(name: str, arguments: Any) -> types.GetPromptResult:
    try:
        result = await invoke_jsonrpc("prompts/get", {"name": name, "arguments": arguments if arguments else {}})
        return types.GetPromptResult(**result)
    except RuntimeError as e:
        raise ValueError(str(e))


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
