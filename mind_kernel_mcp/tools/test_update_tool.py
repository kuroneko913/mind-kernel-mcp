import pytest
import json
from unittest.mock import patch, MagicMock
from mind_kernel_mcp.tools import TOOL_EXECUTORS
from mind_kernel_mcp.tools.update_tool import execute_update_generic_tool

@patch("mind_kernel_mcp.tools.update_tool.GitHubContentProvider")
@patch("mind_kernel_mcp.tools.update_tool.DynamoDBSecretStore")
def test_execute_update_generic_tool_success(MockStore, MockProvider):
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
        "filePath": "path/file.json",
        "version": "v1.0.0",
        "jsonPatch": [{"op": "replace", "path": "/foo", "value": "bar"}],
        "commitMessage": "test commit",
        "changeLogEntry": "my changelog",
        "prBody": "my pr body",
        "updateSummary": {"foo": "bar"}
    }
    result = execute_update_generic_tool(args)

    # Verify
    assert "Pull Request successfully created" in result
    assert "http://github.com/pr/42" in result
    
    mock_provider_instance.propose_update.assert_called_once_with(
        "path/file.json",
        "test commit",
        content=None,
        json_patch=[{"op": "replace", "path": "/foo", "value": "bar"}],
        change_log_entry="my changelog",
        pr_body="my pr body",
        update_summary_content=json.dumps({"foo": "bar"}, ensure_ascii=False, indent=4)
    )

def test_execute_update_generic_tool_validation():
    # Helper to check validation errors
    def check_error(args, match_str):
        with pytest.raises(ValueError, match=match_str):
            execute_update_generic_tool(args)

    base = {
        "userId": "u", "version": "v", "filePath": "f",
        "jsonPatch": [], "commitMessage": "m"
    }

    # Missing userId
    bad_args = base.copy()
    del bad_args["userId"]
    check_error(bad_args, "userId is required")

    # Missing filePath
    bad_args = base.copy()
    del bad_args["filePath"]
    check_error(bad_args, "filePath is required")

    # Missing version
    bad_args = base.copy()
    del bad_args["version"]
    check_error(bad_args, "version is required")

@patch("mind_kernel_mcp.tools.update_tool.GitHubContentProvider")
@patch("mind_kernel_mcp.tools.update_tool.DynamoDBSecretStore")
def test_execute_update_facade_tools(MockStore, MockProvider):
    # Setup mocks
    mock_store_instance = MockStore.return_value
    mock_store_instance.get_github_token.return_value = "fake-token"
    mock_provider_instance = MockProvider.return_value
    mock_provider_instance.propose_update.return_value = {}

    base_args = {
        "userId": "user123",
        "version": "v1.0.0",
        "jsonPatch": [{"op": "test"}],
        "commitMessage": "test"
    }

    # Identity
    TOOL_EXECUTORS["update_mind_kernel_identity"](base_args.copy())
    args, _ = mock_provider_instance.propose_update.call_args
    assert args[0] == "kernel/identity.json"

    # Meta
    TOOL_EXECUTORS["update_mind_kernel_meta"](base_args.copy())
    args, _ = mock_provider_instance.propose_update.call_args
    assert args[0] == "kernel/meta.json"
    
    # Patterns
    TOOL_EXECUTORS["update_mind_kernel_patterns"](base_args.copy())
    args, _ = mock_provider_instance.propose_update.call_args
    assert args[0] == "kernel/patterns.json"

    # Backlog
    TOOL_EXECUTORS["update_mind_kernel_backlog"](base_args.copy())
    args, _ = mock_provider_instance.propose_update.call_args
    assert args[0] == "kernel/backlog.json"
