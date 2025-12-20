import json
import os
import asyncio
import jwt
from jwt import PyJWKClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from mangum import Mangum

from mind_kernel_mcp.tools import (
    PUBLIC_TOOL_DEFINITIONS, TOOL_EXECUTORS
)

JWKS_CLIENT = None

def get_jwks_url():
    region = os.environ.get("AWS_REGION", "ap-northeast-1")
    user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"

def verify_token(request: Request):
    """
    Verify the Bearer token in the Authorization header.
    Returns the user ID (sub) if valid, or None if invalid/missing.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    
    global JWKS_CLIENT
    try:
        if JWKS_CLIENT is None:
            url = get_jwks_url()
            print(f"DEBUG: Initializing JWKS Client with {url}")
            JWKS_CLIENT = PyJWKClient(url)

        signing_key = JWKS_CLIENT.get_signing_key_from_jwt(token)
        # Cognito Access Token typically uses 'client_id' claim, ID Token uses 'aud'.
        # We verify signature and expiration (default).
        data = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False} 
        )
        return data.get("sub")
    except Exception as e:
        print(f"WARN: Token verification failed: {e}")
        return None


async def handle_sse(request: Request):
    """
    Handle SSE connection manually using StreamingResponse.
    Yields the 'endpoint' event to tell the client where to post messages.
    """
    user_id = verify_token(request)
    if not user_id and not os.environ.get("DEBUG_USER_ID"):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    print(f"DEBUG: SSE connection for user={user_id}")

    async def event_generator():
        # Yield the endpoint for POST messages
        # Format: event: <name>\ndata: <json>\n\n
        yield "event: endpoint\ndata: /messages\n\n"
        
        # Keep the connection alive
        while True:
            try:
                await asyncio.sleep(10)
                # Optional: Send a comment to keep connection alive if needed, 
                # but simply holding the connection open is often enough.
                # yield ": keep-alive\n\n"
            except asyncio.CancelledError:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")

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
            
            # --- Implicit User ID Injection ---
            user_id = verify_token(request)
            
            # Fallback for local development
            if not user_id:
                user_id = os.environ.get("DEBUG_USER_ID")
                print(f"DEBUG: Using fallback userId: {user_id}")
            else:
                print(f"DEBUG: Authenticated userId: {user_id}")

            if not user_id:
                 # Strictly enforce auth if no fallback
                 raise ValueError("Unauthorized: Missing valid authentication token")

            # Inject into arguments
            args["userId"] = user_id
            # ----------------------------------
            
            if name in TOOL_EXECUTORS:
                try:
                    content = TOOL_EXECUTORS[name](args)
                except Exception as tool_err:
                     print(f"ERROR executing tool {name}: {tool_err}")
                     # Return error as content so the LLM sees it, or raise JSON-RPC error?
                     # Standard MCP behavior suggests returning TextContent with error info or raising.
                     raise tool_err 
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

async def oauth_discovery(request):
    """
    RFC 9728 OAuth 2.0 Protected Resource Metadata
    """
    print("DEBUG: oauth_discovery called")
    # import os (already at top level)
    region = os.environ.get("AWS_REGION", "ap-northeast-1")
    user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
    
    print(f"DEBUG: region={region}, user_pool_id={user_pool_id}")

    # Construct the base URL from the request if possible, or use a configured one.
    # Starlette request.url represents the full URL. We want the base.
    base_url = str(request.base_url).rstrip("/")
    print(f"DEBUG: base_url={base_url}")
    
    # Authorization Server URL (Cognito)
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
    
    metadata = {
        "resource": base_url,
        "authorization_servers": [
            issuer
        ],
        "scopes_supported": ["email", "openid", "profile"],
        "code_challenge_methods_supported": ["S256"]
    }
    
    json_str = json.dumps(metadata)
    print(f"DEBUG: returning metadata={json_str}")
    
    # Use StreamingResponse to be consistent with AWS_LWA_INVOKE_MODE: response_stream
    return StreamingResponse(iter([json_str]), media_type="application/json")

app = Starlette(
    routes=[
        Route("/.well-known/oauth-protected-resource", endpoint=oauth_discovery, methods=["GET"]),
        Route("/messages", endpoint=handle_rpc, methods=["POST"]),
        Route("/sse", endpoint=handle_sse, methods=["GET", "POST"]), 
        # For simple bridge invocations (Web Adapter default)
        Route("/", endpoint=handle_rpc, methods=["POST"]),
    ],
    debug=True
)

handler = Mangum(app, lifespan="off")
