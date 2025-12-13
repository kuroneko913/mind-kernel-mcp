import pytest
from unittest.mock import patch, MagicMock
from mind_kernel_mcp.tools.fetch_tool import execute_fetch_tool

@patch("mind_kernel_mcp.tools.fetch_tool.GitHubContentProvider")
@patch("mind_kernel_mcp.tools.fetch_tool.DynamoDBSecretStore")
def test_execute_fetch_tool_success(MockStore, MockProvider):
    # Setup mocks
    mock_store_instance = MockStore.return_value
    mock_store_instance.get_github_token.return_value = "fake-token"
    
    mock_provider_instance = MockProvider.return_value
    mock_provider_instance.fetch_file.return_value = "content"

    # Execute
    args = {"userId": "user123", "filePath": "test.json"}
    result = execute_fetch_tool(args)

    # Verify
    assert result == "content"
    MockStore.assert_called_once()
    mock_store_instance.get_github_token.assert_called_once_with("user123")
    MockProvider.assert_called_once_with("fake-token")
    mock_provider_instance.fetch_file.assert_called_once_with("test.json")

@patch("mind_kernel_mcp.tools.fetch_tool.GitHubContentProvider")
@patch("mind_kernel_mcp.tools.fetch_tool.DynamoDBSecretStore")
def test_execute_fetch_tool_default_path(MockStore, MockProvider):
    # Setup mocks
    mock_store_instance = MockStore.return_value
    mock_store_instance.get_github_token.return_value = "fake-token"
    
    mock_provider_instance = MockProvider.return_value
    mock_provider_instance.fetch_file.return_value = "default content"

    # Execute
    args = {"userId": "user123"}
    result = execute_fetch_tool(args)

    # Verify
    assert result == "default content"
    mock_provider_instance.fetch_file.assert_called_once_with("core.json")

def test_execute_fetch_tool_missing_user_id():
    args = {"filePath": "test.json"}
    with pytest.raises(ValueError, match="userId is required"):
        execute_fetch_tool(args)
