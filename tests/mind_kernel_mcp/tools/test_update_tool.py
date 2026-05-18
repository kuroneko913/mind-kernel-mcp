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
        "filePath": "kernel/patterns.json",
        "jsonPatch": [{"op": "replace", "path": "/foo", "value": "bar"}],
        "commitMessage": "test commit",
        "prBody": "my pr body"
    }
    result = execute_update_generic_tool(args)

    # Verify
    assert "Pull Request successfully created" in result
    assert "http://github.com/pr/42" in result
    
    mock_provider_instance.propose_update.assert_called_once_with(
        "kernel/patterns.json",
        "test commit",
        content=None,
        json_patch=[{"op": "replace", "path": "/foo", "value": "bar"}],
        pr_body="my pr body",
        pr_number=None
    )

def test_execute_update_generic_tool_validation():
    # Helper to check validation errors
    def check_error(args, match_str):
        with pytest.raises(ValueError, match=match_str):
            execute_update_generic_tool(args)

    base = {
        "userId": "u", "filePath": "kernel/patterns.json",
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

def test_file_path_whitelist_blocks_traversal():
    """Security: filePath outside KERNEL_FILES whitelist must be rejected (OWASP LLM06)."""
    
    def check_blocked(file_path: str):
        with pytest.raises(ValueError, match="not allowed"):
            execute_update_generic_tool({
                "userId": "user123",
                "filePath": file_path,
                "jsonPatch": [{"op": "replace", "path": "/jobs", "value": "evil"}],
                "commitMessage": "pwn"
            })

    # Path traversal attempts
    check_blocked("../../.github/workflows/deploy.yml")
    check_blocked("/etc/passwd")
    check_blocked(".github/workflows/ci.yml")
    check_blocked("kernel/unknown.json")

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
