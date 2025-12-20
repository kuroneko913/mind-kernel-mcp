import pytest
from unittest.mock import patch, MagicMock
from mind_kernel_mcp.tools import TOOL_EXECUTORS
from mind_kernel_mcp.tools.fetch_tool import execute_fetch_generic_tool

@patch("mind_kernel_mcp.tools.fetch_tool.GitHubContentProvider")
@patch("mind_kernel_mcp.tools.fetch_tool.DynamoDBSecretStore")
def test_execute_fetch_generic_tool_success(MockStore, MockProvider):
    # Setup mocks
    mock_store_instance = MockStore.return_value
    mock_store_instance.get_github_token.return_value = "fake-token"
    
    mock_provider_instance = MockProvider.return_value
    mock_provider_instance.fetch_file.return_value = "content"

    # Execute
    args = {"userId": "user123", "filePath": "path/to/file.json"}
    result = execute_fetch_generic_tool(args)

    # Verify
    assert result == "content"
    MockStore.assert_called_once()
    mock_store_instance.get_github_token.assert_called_once_with("user123")
    MockProvider.assert_called_once_with("fake-token")
    mock_provider_instance.fetch_file.assert_called_once_with("path/to/file.json")

def test_execute_fetch_generic_tool_missing_args():
    # Missing userId
    with pytest.raises(ValueError, match="userId is required"):
        execute_fetch_generic_tool({"filePath": "test.json"})
        
    # Missing filePath
    with pytest.raises(ValueError, match="filePath is required"):
        execute_fetch_generic_tool({"userId": "u"})

@patch("mind_kernel_mcp.tools.fetch_tool.GitHubContentProvider")
@patch("mind_kernel_mcp.tools.fetch_tool.DynamoDBSecretStore")
def test_execute_fetch_facade_tools(MockStore, MockProvider):
    # Setup mocks
    mock_store_instance = MockStore.return_value
    mock_store_instance.get_github_token.return_value = "fake-token"
    mock_provider_instance = MockProvider.return_value
    mock_provider_instance.fetch_file.return_value = "content"
    
    args = {"userId": "user123"}

    # Identity
    TOOL_EXECUTORS["fetch_mind_kernel_identity"](args)
    mock_provider_instance.fetch_file.assert_called_with("kernel/identity.json")

    # Meta
    TOOL_EXECUTORS["fetch_mind_kernel_meta"](args)
    mock_provider_instance.fetch_file.assert_called_with("kernel/meta.json")

    # Patterns
    TOOL_EXECUTORS["fetch_mind_kernel_patterns"](args)
    mock_provider_instance.fetch_file.assert_called_with("kernel/patterns.json")

    # Backlog
    TOOL_EXECUTORS["fetch_mind_kernel_backlog"](args)
    mock_provider_instance.fetch_file.assert_called_with("kernel/backlog.json")
