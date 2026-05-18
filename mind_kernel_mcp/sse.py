import json
import os
import asyncio
import jwt
from jwt import PyJWKClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse, PlainTextResponse
from mangum import Mangum

from mind_kernel_mcp.tools import (
    PUBLIC_TOOL_DEFINITIONS, TOOL_EXECUTORS
)
# Handlers are now used in rpc_handlers, but sse.py needs dispatcher
from mind_kernel_mcp.rpc_handlers import dispatch_rpc

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
    api_key_header = request.headers.get("X-API-Key")
    env_api_key = os.environ.get("MCP_API_KEY")

    # 1. API Key Auth (Simpler, for local tools)
    import hmac
    if env_api_key and api_key_header and hmac.compare_digest(api_key_header, env_api_key):
        print("DEBUG: Authenticated via X-API-Key")
        # Use a fixed debug user ID for API Key access
        return os.environ.get("LOCAL_USER_ID")
    
    # 2. JWT Auth (Cognito)
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
    # Only allow fallback if explicitly enabled
    if not user_id and os.environ.get("ALLOW_DEBUG_AUTH") == "true":
        user_id = os.environ.get("DEBUG_USER_ID")
        if user_id:
            print(f"DEBUG: Using fallback userId in SSE: {user_id}")

    if not user_id:
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
        # Authentication extraction (performed once for all methods)
        user_id = verify_token(request)
        
        # Fallback for local development - ONLY if explicitly allowed
        if not user_id and os.environ.get("ALLOW_DEBUG_AUTH") == "true":
            user_id = os.environ.get("DEBUG_USER_ID")
            if user_id:
                print(f"DEBUG: Using fallback userId: {user_id}")

        # Enforce authentication for all methods except initialize and ping
        PUBLIC_METHODS = ["initialize", "ping", "notifications/initialized"]
        if not user_id and method not in PUBLIC_METHODS:
            print(f"WARN: Unauthorized attempt to call {method}")
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32001, "message": "Unauthorized: Missing valid authentication token"},
                "id": request_id
            }, status_code=401)

        if user_id:
            print(f"DEBUG: Authenticated userId: {user_id}")

        result = await dispatch_rpc(method, params, user_id)
        
        # notifications/initialized returns None, and expects no response body if it was a notification
        # But JSON-RPC over HTTP usually expects a response for Requests.
        # notifications/initialized is a notification, so we might not need to return anything?
        # Specification says notifications don't get responses. 
        # However, for simplicity using starlette, we usually return 200 OK.
        # If result is None and id is None (notification) -> 200 OK empty?
        # In this implementation, handle_rpc handles requests with IDs mostly.
        # If request_id is present, we must return a response.
        
        if result is not None:
            response_data["result"] = result
        else:
            # Maybe it was a notification or just empty result?
            # If method is notifications/initialized, and no ID, we return nothing or 200 OK?
            # Original code returned Response(status_code=200).
            if method == "notifications/initialized":
                 return Response(status_code=200)
            # Default empty dict for result if not None?
            # If handler returns None and it's not notification, what then?
            # Let's assume handlers return dicts for results.
            if request_id is not None and result is None:
                 # Should typically not happen for methods that return data.
                 # Assuming empty dict if None/Void?
                 response_data["result"] = {}

    except NotImplementedError:
        response_data["error"] = {"code": -32601, "message": f"Method {method} not found"}
    
    except ValueError as ve:
        # Map ValueError to invalid params or internal error or unauthorized (custom)
        # Check message content for "Unauthorized" or "Resource not found"
        msg = str(ve)
        code = -32603 # Internal error default
        if "Unauthorized" in msg:
             code = -32001 # Custom auth error? or Internal
        elif "Resource not found" in msg:
             code = -32602 # Invalid params?
        elif "Unknown tool" in msg:
             code = -32601 # Method not found / Tool not found

        response_data["error"] = {
            "code": code,
            "message": msg
        }
        
    except Exception as e:
        print(f"ERROR: {e}")
        response_data["error"] = {
            "code": -32603,
            "message": f"Internal error: {str(e)}"
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

def openai_verification(request):
    """
    Handle ChatGPT domain verification.
    """
    token = os.environ.get("OPENAI_VERIFICATION_TOKEN", "")
    return PlainTextResponse(token)


app = Starlette(
    routes=[
        Route("/.well-known/openai-apps-challenge", endpoint=openai_verification, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource", endpoint=oauth_discovery, methods=["GET"]),
        Route("/messages", endpoint=handle_rpc, methods=["POST"]),
        Route("/sse", endpoint=handle_sse, methods=["GET", "POST"]), 
        # For simple bridge invocations (Web Adapter default)
        Route("/", endpoint=handle_rpc, methods=["POST"]),
    ],
    debug=True
)

handler = Mangum(app, lifespan="off")
