import pytest
import json
from unittest.mock import patch, MagicMock
from mind_kernel_mcp.tools.update_tool import execute_update_tool

@patch("mind_kernel_mcp.tools.update_tool.GitHubContentProvider")
@patch("mind_kernel_mcp.tools.update_tool.DynamoDBSecretStore")
def test_execute_update_tool_success_all_args(MockStore, MockProvider):
    # Setup mocks
    mock_store_instance = MockStore.return_value
    mock_store_instance.get_github_token.return_value = "fake-token"
    
    mock_provider_instance = MockProvider.return_value
    mock_provider_instance.propose_update.return_value = {
        "html_url": "http://github.com/pr/42",
        "number": 42
    }

    # Execute
    args = {
        "userId": "user123",
        "version": "v1.0.0",
        "jsonPatch": [{"op": "replace", "path": "/foo", "value": "bar"}],
        "commitMessage": "test commit",
        "changeLogEntry": "my changelog",
        "prBody": "my pr body",
        "updateSummary": {"foo": "bar"}
    }
    result = execute_update_tool(args)

    # Verify
    assert "Pull Request successfully created" in result
    assert "http://github.com/pr/42" in result
    
    mock_provider_instance.propose_update.assert_called_once_with(
        "core.json",
        "test commit",
        content=None,
        json_patch=[{"op": "replace", "path": "/foo", "value": "bar"}],
        change_log_entry="my changelog",
        pr_body="my pr body",
        update_summary_content=json.dumps({"foo": "bar"}, ensure_ascii=False, indent=4)
    )

@patch("mind_kernel_mcp.tools.update_tool.GitHubContentProvider")
@patch("mind_kernel_mcp.tools.update_tool.DynamoDBSecretStore")
def test_execute_update_tool_defaults(MockStore, MockProvider):
    # Setup mocks
    mock_store_instance = MockStore.return_value
    mock_store_instance.get_github_token.return_value = "fake-token"
    
    mock_provider_instance = MockProvider.return_value
    mock_provider_instance.propose_update.return_value = {} # Mock return

    # Execute with minimal required args
    args = {
        "userId": "user123",
        "version": "v2.0.0",
        "jsonPatch": [{"op": "test"}],
        "commitMessage": "minimal"
    }
    result = execute_update_tool(args)

    # Verify defaults were generated and passed to provider
    mock_provider_instance.propose_update.assert_called_once()
    call_args = mock_provider_instance.propose_update.call_args
    _, kwargs = call_args
    
    # Check generated defaults
    assert "v2.0.0" in kwargs["change_log_entry"]
    assert "v2.0.0" in kwargs["pr_body"]
    assert kwargs["update_summary_content"] == json.dumps({"version": "v2.0.0"}, ensure_ascii=False, indent=4)

def test_execute_update_tool_validation():
    # Helper to check validation errors
    def check_error(args, match_str):
        with pytest.raises(ValueError, match=match_str):
            execute_update_tool(args)

    base = {
        "userId": "u", "version": "v", 
        "jsonPatch": [], "commitMessage": "m"
    }

    # Missing userId
    bad_args = base.copy()
    del bad_args["userId"]
    check_error(bad_args, "userId is required")

    # Missing version
    bad_args = base.copy()
    del bad_args["version"]
    check_error(bad_args, "version is required")

    # Missing commitMessage
    bad_args = base.copy()
    del bad_args["commitMessage"]
    check_error(bad_args, "commitMessage is required")

    # Missing jsonPatch
    bad_args = base.copy()
    del bad_args["jsonPatch"]
    check_error(bad_args, "jsonPatch is required")
