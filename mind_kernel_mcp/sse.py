import json
import asyncio
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from sse_starlette.sse import EventSourceResponse
from mangum import Mangum

from mind_kernel_mcp.tools import (
    PUBLIC_TOOL_DEFINITIONS, TOOL_EXECUTORS
)

async def handle_sse(request: Request):
    """
    Handle SSE connection.
    Yields the 'endpoint' event to tell the client where to post messages.
    """
    async def event_generator():
        # Yield the endpoint for POST messages
        # We use a relative path /messages, assuming the client respects it relative to the SSE URL base
        yield {
            "event": "endpoint",
            "data": "/messages"
        }
        
        # Keep the connection alive
        while True:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break

    return EventSourceResponse(event_generator())

async def handle_rpc(request: Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None}, status_code=400)

    request_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    print(f"DEBUG: RPC method={method} params={params}")
    
    response_data = {
        "jsonrpc": "2.0",
        "id": request_id,
    }

    try:
        if method == "initialize":
            response_data["result"] = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False}
                },
                "serverInfo": {
                    "name": "mind-kernel-mcp",
                    "version": "1.0.0"
                }
            }
        
        elif method == "notifications/initialized":
            # Just acknowledge
            return Response(status_code=200)

        elif method == "tools/list":
            response_data["result"] = {
                "tools": PUBLIC_TOOL_DEFINITIONS
            }

        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})
            
            if name in TOOL_EXECUTORS:
                content = TOOL_EXECUTORS[name](args)
            else:
                 raise ValueError(f"Unknown tool: {name}")
            
            response_data["result"] = {
                "content": [
                    {
                        "type": "text",
                        "text": content
                    }
                ]
            }
            
        else:
            if method == "ping":
                 response_data["result"] = {}
            else:
                 response_data["error"] = {"code": -32601, "message": f"Method {method} not found"}

    except Exception as e:
        print(f"ERROR: {e}")
        response_data["error"] = {
            "code": -32603,
            "message": str(e)
        }

    return JSONResponse(response_data)


async def health(request):
    return JSONResponse({"status": "ok"})

app = Starlette(
    routes=[
        Route("/messages", endpoint=handle_rpc, methods=["POST"]),
        Route("/sse", endpoint=handle_sse, methods=["GET"]), 
        # For simple bridge invocations (Web Adapter default)
        Route("/", endpoint=handle_rpc, methods=["POST"]),
    ],
    debug=True
)

handler = Mangum(app, lifespan="off")
