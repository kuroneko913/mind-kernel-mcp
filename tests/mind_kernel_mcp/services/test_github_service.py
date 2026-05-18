# -*- coding: utf-8 -*-
"""Tests for GitHubContentProvider.

These tests mock external HTTP calls to the GitHub API using ``unittest.mock``.
The goal is to verify the behavior of the provider without making real network requests.
"""

import base64
import json

import pytest
from unittest.mock import patch, MagicMock

from mind_kernel_mcp.services.github_service import GitHubContentProvider

# Helper to create a mock response object
def make_response(status_code: int, json_data=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.raise_for_status.side_effect = None if status_code < 400 else Exception()
    return mock_resp

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("REPO_OWNER", "testowner")
    monkeypatch.setenv("REPO_NAME", "testrepo")
    return

@pytest.fixture
def provider():
    return GitHubContentProvider(token="dummy-token")

def test_fetch_file_success(provider):
    content_str = "{\"key\": \"value\"}"
    encoded = base64.b64encode(content_str.encode()).decode()
    mock_json = {"content": encoded}
    with patch("requests.get", return_value=make_response(200, mock_json)) as mock_get:
        result = provider.fetch_file("some/path.json")
        mock_get.assert_called_once()
        assert result == content_str

def test_fetch_file_not_found(provider):
    with patch("requests.get", return_value=make_response(404)) as mock_get:
        with pytest.raises(FileNotFoundError):
            provider.fetch_file("missing.json")
        mock_get.assert_called_once()

def test_update_file_create_new(provider):
    # Simulate get returning 404 (file does not exist yet)
    get_resp = make_response(404)
    put_resp = make_response(201, {"content": {"sha": "newsha"}})
    with patch("requests.get", return_value=get_resp) as mock_get, \
         patch("requests.put", return_value=put_resp) as mock_put:
        result = provider.update_file("new.json", "{}", "add new file")
        assert result == {"content": {"sha": "newsha"}}
        mock_get.assert_called_once()
        mock_put.assert_called_once()

def test_update_file_existing(provider):
    # Simulate existing file with SHA
    get_resp = make_response(200, {"sha": "oldsha"})
    put_resp = make_response(200, {"content": {"sha": "newsha"}})
    with patch("requests.get", return_value=get_resp) as mock_get, \
         patch("requests.put", return_value=put_resp) as mock_put:
        result = provider.update_file("existing.json", "{}", "update file")
        assert result == {"content": {"sha": "newsha"}}
        # Ensure the SHA was sent in the payload
        args, kwargs = mock_put.call_args
        sent_json = kwargs.get("json", {})
        assert sent_json.get("sha") == "oldsha"
        mock_get.assert_called_once()
        mock_put.assert_called_once()



def test_prepare_new_content_with_json_patch(provider):
    original = {"a": 1, "b": 2}
    patch_ops = [{"op": "replace", "path": "/b", "value": 3}]
    # Mock fetch_file to return the original JSON string
    with patch.object(provider, "fetch_file", return_value=json.dumps(original)):
        result = provider._prepare_new_content("file.json", None, patch_ops, "branch")
        expected = json.dumps({"a": 1, "b": 3}, indent=2, ensure_ascii=False)
        assert result == expected

def test_prepare_new_content_direct_content(provider):
    content = "{\"key\": \"value\"}"
    result = provider._prepare_new_content("file.json", content, None, "branch")
    assert result == content

def test_validate_update_params_success(provider):
    # Should not raise
    provider._validate_update_params("msg", None, "content")
    provider._validate_update_params("msg", [{"op": "add", "path": "/c", "value": 4}], None)

def test_validate_update_params_missing_message(provider):
    with pytest.raises(ValueError, match="commitMessage is required"):
        provider._validate_update_params("", None, "content")

def test_validate_update_params_missing_content_and_patch(provider):
    with pytest.raises(ValueError, match="Either content or json_patch must be provided"):
        provider._validate_update_params("msg", None, None)

def test_propose_update_flow(provider):
    # Patch internal helper methods to avoid network calls and focus on flow
    with patch.object(provider, "_create_work_branch", return_value=("test-branch", "main")) as mock_branch, \
         patch.object(provider, "_prepare_new_content", return_value="new content") as mock_prepare, \
         patch.object(provider, "_validate_update_params") as mock_validate, \
         patch.object(provider, "_update_target_file") as mock_update_target, \
         patch.object(provider, "_create_pr", return_value={"html_url": "http://github.com/pr/1"}) as mock_create_pr:
        result = provider.propose_update(
            path="core.json",
            commit_message="test commit",
            content="new content"
        )
        assert result == {"html_url": "http://github.com/pr/1"}
        mock_branch.assert_called_once_with("core.json")
        mock_prepare.assert_called_once_with("core.json", "new content", None, "test-branch")
        mock_validate.assert_called_once()
        mock_update_target.assert_called_once()
        mock_create_pr.assert_called_once()

def test_propose_update_with_pr_number(provider):
    """Regression test for updating existing PR using pr_number."""
    # Mock get_pull_request response
    mock_pr_resp = MagicMock()
    mock_pr_resp.json.return_value = {"head": {"ref": "existing-branch"}}
    mock_pr_resp.status_code = 200
    
    # Mock update_file response (GET sha)
    mock_get_sha = MagicMock()
    mock_get_sha.json.return_value = {"sha": "old_sha", "content": "eyJ2ZXJzaW9uIjogInYxLjAuMCIsICJmb28iOiAib3JpZ2luYWwifQ=="} 
    mock_get_sha.status_code = 200

    # Mock update_file response (PUT)
    mock_put_resp = MagicMock()
    mock_put_resp.json.return_value = {"commit": {"sha": "new_sha"}}
    mock_put_resp.status_code = 200

    # Configure requests.get side effects
    def side_effect(url, **kwargs):
        if "/pulls/999" in url:
            return mock_pr_resp
        if "/contents/" in url:
            return mock_get_sha
        return MagicMock() # default
        
    with patch("mind_kernel_mcp.services.github_service.requests.get", side_effect=side_effect) as mock_get, \
         patch("mind_kernel_mcp.services.github_service.requests.put", return_value=mock_put_resp) as mock_put, \
         patch("mind_kernel_mcp.services.github_service.requests.post") as mock_post:
        
        # Call propose_update
        provider.propose_update(
            path="core.json",
            commit_message="msg",
            content=None,
            json_patch=[{"op": "replace", "path": "/foo", "value": "bar"}],
            pr_number=999
        )
        
        # Verification
        # Should call get (pulls/999) - implied by side_effect trigger or explicit check
        # Should call put (contents/core.json) with branch="existing-branch"
        
        found_update = False
        for call_args in mock_put.call_args_list:
            url = call_args[0][0] # first arg
            if "core.json" in url:
                 found_update = True
                 data = call_args[1].get('json')
                 assert data.get('branch') == "existing-branch", f"Expected branch 'existing-branch', got {data.get('branch')}"
        
        assert found_update, "No update PUT request found for core.json"
            
        # Check NO POST (create PR) calls
        post_calls = mock_post.call_args_list
        for call_args in post_calls:
            url = call_args[0][0]
            if "/pulls" in url:
                 assert False, "Create PR (POST /pulls) was called!"
