import json
import os
import asyncio
import jwt
from typing import Dict, Any, Callable, Optional, List
from jwt import PyJWKClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse, PlainTextResponse
import hmac

class ServerlessMcpServer:
    def __init__(self, name: str = "mcp-server", version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.jwks_client = None
        self.tools = []
        self.tool_executors = {}
        self.resources = []
        self.resource_handlers = {}
        self.prompts = []
        self.prompt_handlers = {}

    def register_tool(self, definition: dict, executor: Callable):
        self.tools.append(definition)
        self.tool_executors[definition["name"]] = executor

    def register_resource(self, definition: dict, handler: Callable):
        self.resources.append(definition)
        self.resource_handlers[definition["uri"]] = handler

    def register_prompt(self, definition: dict, handler: Callable):
        self.prompts.append(definition)
        self.prompt_handlers[definition["name"]] = handler

    def _get_jwks_url(self):
        region = os.environ.get("AWS_REGION", "ap-northeast-1")
        user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
        return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"

    def verify_token(self, request: Request) -> Optional[str]:
        auth_header = request.headers.get("Authorization")
        api_key_header = request.headers.get("X-API-Key")
        env_api_key = os.environ.get("MCP_API_KEY")

        # 1. API Key Auth
        if env_api_key and api_key_header and hmac.compare_digest(api_key_header, env_api_key):
            print("DEBUG: Authenticated via X-API-Key")
            return os.environ.get("LOCAL_USER_ID")
        
        # 2. JWT Auth (Cognito)
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ")[1]
        
        try:
            if self.jwks_client is None:
                url = self._get_jwks_url()
                print(f"DEBUG: Initializing JWKS Client with {url}")
                self.jwks_client = PyJWKClient(url)

            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
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

    async def handle_sse(self, request: Request):
        user_id = self.verify_token(request)
        if not user_id and os.environ.get("ALLOW_DEBUG_AUTH") == "true":
            user_id = os.environ.get("DEBUG_USER_ID")
            if user_id:
                print(f"DEBUG: Using fallback userId in SSE: {user_id}")

        if not user_id:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
            
        print(f"DEBUG: SSE connection for user={user_id}")

        async def event_generator():
            yield "event: endpoint\ndata: /messages\n\n"
            while True:
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    break

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # --- MCP RPC Handlers ---
    async def _handle_initialize(self, params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False}
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version
            }
        }

    async def _handle_notifications_initialized(self, params: Dict[str, Any], user_id: Optional[str]) -> None:
        return None

    async def _handle_ping(self, params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        return {}

    async def _handle_tools_list(self, params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        return {
            "tools": self.tools
        }

    async def _handle_tools_call(self, params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        if not user_id:
            raise ValueError("Unauthorized: Missing valid authentication token")

        name = params.get("name")
        args = params.get("arguments", {})
        if not isinstance(args, dict):
            raise ValueError("Invalid format: 'arguments' must be a JSON object")
        
        args["userId"] = user_id
        
        if name in self.tool_executors:
            content = self.tool_executors[name](args)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": content
                    }
                ]
            }
        else:
            raise ValueError(f"Unknown tool: {name}")

    async def _handle_resources_list(self, params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        return {
            "resources": self.resources
        }

    async def _handle_resources_read(self, params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        uri = params.get("uri", "")
        if uri in self.resource_handlers:
            return await self.resource_handlers[uri](uri, user_id)
        else:
            raise ValueError("Resource not found")

    async def _handle_prompts_list(self, params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        return {
            "prompts": self.prompts
        }

    async def _handle_prompts_get(self, params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        if not user_id:
            raise ValueError("Unauthorized: Missing valid authentication token")

        name = params.get("name")
        args = params.get("arguments", {})
        if not isinstance(args, dict):
            raise ValueError("Invalid format: 'arguments' must be a JSON object")
        
        if name in self.prompt_handlers:
            return await self.prompt_handlers[name](name, args, user_id)
        else:
            raise ValueError(f"Unknown prompt: {name}")

    async def dispatch_rpc(self, method: str, params: Dict[str, Any], user_id: Optional[str]) -> Optional[Dict[str, Any]]:
        handlers = {
            "initialize": self._handle_initialize,
            "notifications/initialized": self._handle_notifications_initialized,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
        }
        handler = handlers.get(method)
        if not handler:
            raise NotImplementedError(f"Method {method} not found")
        
        return await handler(params, user_id)

    async def handle_rpc(self, request: Request):
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
            user_id = self.verify_token(request)
            
            if not user_id and os.environ.get("ALLOW_DEBUG_AUTH") == "true":
                user_id = os.environ.get("DEBUG_USER_ID")
                if user_id:
                    print(f"DEBUG: Using fallback userId: {user_id}")

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

            result = await self.dispatch_rpc(method, params, user_id)
            
            if result is not None:
                response_data["result"] = result
            else:
                if method == "notifications/initialized":
                     return Response(status_code=200)
                if request_id is not None and result is None:
                     response_data["result"] = {}

        except NotImplementedError:
            response_data["error"] = {"code": -32601, "message": f"Method {method} not found"}
        
        except ValueError as ve:
            msg = str(ve)
            code = -32603 
            if "Unauthorized" in msg:
                 code = -32001 
            elif "Resource not found" in msg:
                 code = -32602 
            elif "Unknown tool" in msg or "Unknown prompt" in msg:
                 code = -32601 

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

    async def oauth_discovery(self, request: Request):
        print("DEBUG: oauth_discovery called")
        region = os.environ.get("AWS_REGION", "ap-northeast-1")
        user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
        
        base_url = str(request.base_url).rstrip("/")
        issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        
        metadata = {
            "resource": base_url,
            "authorization_servers": [issuer],
            "scopes_supported": ["email", "openid", "profile"],
            "code_challenge_methods_supported": ["S256"]
        }
        
        json_str = json.dumps(metadata)
        return StreamingResponse(iter([json_str]), media_type="application/json")

    def openai_verification(self, request: Request):
        token = os.environ.get("OPENAI_VERIFICATION_TOKEN", "")
        return PlainTextResponse(token)

    def create_app(self) -> Starlette:
        app = Starlette(
            routes=[
                Route("/.well-known/openai-apps-challenge", endpoint=self.openai_verification, methods=["GET"]),
                Route("/.well-known/oauth-protected-resource", endpoint=self.oauth_discovery, methods=["GET"]),
                Route("/messages", endpoint=self.handle_rpc, methods=["POST"]),
                Route("/sse", endpoint=self.handle_sse, methods=["GET", "POST"]), 
                Route("/", endpoint=self.handle_rpc, methods=["POST"]),
            ],
            debug=True
        )
        return app
