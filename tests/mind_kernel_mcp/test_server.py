import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from starlette.requests import Request
from starlette.responses import JSONResponse
from mind_kernel_mcp.server import ServerlessMcpServer

# Helper to create a mock Starlette Request
def make_mock_request(method="POST", headers=None, body=None):
    scope = {
        "type": "http",
        "method": method,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    
    async def receive():
        return {
            "type": "http.request",
            "body": json.dumps(body).encode() if body else b"",
        }
    
    return Request(scope, receive)

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.fixture
def server():
    # Clear env vars that might affect auth
    os.environ.pop("MCP_API_KEY", None)
    os.environ.pop("LOCAL_USER_ID", None)
    os.environ.pop("ALLOW_DEBUG_AUTH", None)
    return ServerlessMcpServer(name="test-server", version="1.0.0")

@pytest.mark.anyio
async def test_initialize(server):
    req = make_mock_request(body={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    })
    
    response = await server.handle_rpc(req)
    assert isinstance(response, JSONResponse)
    body = json.loads(response.body)
    
    assert "error" not in body
    assert body["result"]["serverInfo"]["name"] == "test-server"

@pytest.mark.anyio
async def test_unauthorized_access(server):
    # Protected method without auth token
    req = make_mock_request(body={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })
    
    response = await server.handle_rpc(req)
    body = json.loads(response.body)
    
    assert response.status_code == 401
    assert "error" in body
    assert "Unauthorized" in body["error"]["message"]

@pytest.mark.anyio
@patch.dict(os.environ, {"MCP_API_KEY": "test-key", "LOCAL_USER_ID": "admin-123"})
async def test_api_key_auth_tools_call(server):
    # Register a mock tool
    mock_executor = MagicMock(return_value="tool_result")
    server.register_tool({"name": "test_tool", "description": "desc"}, mock_executor)
    
    req = make_mock_request(
        headers={"X-API-Key": "test-key"},
        body={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "test_tool",
                "arguments": {"arg1": "val1"}
            }
        }
    )
    
    response = await server.handle_rpc(req)
    body = json.loads(response.body)
    
    assert response.status_code == 200
    assert "error" not in body
    assert body["result"]["content"][0]["text"] == "tool_result"
    
    # Verify user_id was injected into arguments
    mock_executor.assert_called_once_with({"arg1": "val1", "userId": "admin-123"})

@pytest.mark.anyio
@patch.dict(os.environ, {"MCP_API_KEY": "test-key", "LOCAL_USER_ID": "admin-123"})
async def test_prompts_get(server):
    # Register an async prompt handler
    mock_handler = AsyncMock(return_value={"description": "mock prompt", "messages": []})
    server.register_prompt({"name": "test_prompt", "description": "desc"}, mock_handler)
    
    req = make_mock_request(
        headers={"X-API-Key": "test-key"},
        body={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "prompts/get",
            "params": {
                "name": "test_prompt",
                "arguments": {}
            }
        }
    )
    
    response = await server.handle_rpc(req)
    body = json.loads(response.body)
    
    assert response.status_code == 200
    assert body["result"]["description"] == "mock prompt"
    mock_handler.assert_called_once_with("test_prompt", {}, "admin-123")

@pytest.mark.anyio
@patch.dict(os.environ, {"MCP_API_KEY": "test-key", "LOCAL_USER_ID": "admin-123"})
async def test_resources_read(server):
    # Register an async resource handler
    mock_handler = AsyncMock(return_value={"contents": [{"uri": "test://uri", "text": "hello"}]})
    server.register_resource({"uri": "test://uri"}, mock_handler)
    
    req = make_mock_request(
        headers={"X-API-Key": "test-key"},
        body={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {
                "uri": "test://uri"
            }
        }
    )
    
    response = await server.handle_rpc(req)
    body = json.loads(response.body)
    
    assert response.status_code == 200
    assert body["result"]["contents"][0]["text"] == "hello"
    mock_handler.assert_called_once_with("test://uri", "admin-123")

@pytest.mark.anyio
@patch.dict(os.environ, {"COGNITO_USER_POOL_ID": "fake-pool-id"})
@patch("mind_kernel_mcp.server.PyJWKClient")
@patch("mind_kernel_mcp.server.jwt.decode")
async def test_jwt_auth(mock_decode, mock_jwks_client, server):
    # Setup mock JWT decoding
    mock_decode.return_value = {"sub": "cognito-user-456"}
    mock_jwks_instance = MagicMock()
    mock_jwks_instance.get_signing_key_from_jwt.return_value.key = "fake-key"
    mock_jwks_client.return_value = mock_jwks_instance
    
    req = make_mock_request(
        headers={"Authorization": "Bearer fake.jwt.token"},
        body={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
    )
    
    response = await server.handle_rpc(req)
    body = json.loads(response.body)
    
    assert response.status_code == 200
    assert "error" not in body
    assert "tools" in body["result"]
    mock_decode.assert_called_once()

@pytest.mark.anyio
@patch.dict(os.environ, {"MCP_API_KEY": "test-key", "LOCAL_USER_ID": "admin-123"})
async def test_permission_error_handling(server):
    # Setup a mock tool that raises PermissionError
    mock_executor = MagicMock(side_effect=PermissionError("無効なGitHubトークンです。"))
    server.register_tool({"name": "fail_tool", "description": "desc"}, mock_executor)
    
    req = make_mock_request(
        headers={"X-API-Key": "test-key"},
        body={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "fail_tool",
                "arguments": {}
            }
        }
    )
    
    response = await server.handle_rpc(req)
    body = json.loads(response.body)
    
    assert response.status_code == 200
    assert "error" in body
    assert body["error"]["code"] == -32001
    assert "無効なGitHubトークンです。" in body["error"]["message"]

