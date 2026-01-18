
import unittest
from unittest.mock import MagicMock, patch
import json
from mind_kernel_mcp.tools.history_tool import execute_history_tool, detailed_semantic_diff, _parse_relative_date

class TestHistoryTool(unittest.TestCase):

    def test_parse_relative_date(self):
        # Basic check - we can't easily check "1 month ago" exact timestamp without freezing time, 
        # but we can check format.
        iso = _parse_relative_date("2023-01-01")
        self.assertEqual(iso, "2023-01-01T00:00:00Z")
        
        # Check "ago" logic returns something ISO-like
        ago = _parse_relative_date("1 day ago")
        self.assertTrue(ago.endswith("Z"))
        self.assertTrue("T" in ago)

    def test_detailed_semantic_diff(self):
        old = {"a": 1, "b": {"c": 2}}
        new = {"a": 1, "b": {"c": 3}, "d": "added"}
        
        changes = detailed_semantic_diff(old, new)
        
        # modified b.c
        mod = next((c for c in changes if c['key'] == 'b.c'), None)
        self.assertIsNotNone(mod)
        self.assertEqual(mod['type'], 'MODIFIED')
        
        # added d
        add = next((c for c in changes if c['key'] == 'd'), None)
        self.assertIsNotNone(add)
        self.assertEqual(add['type'], 'ADDED')
        self.assertEqual(add['value'], 'added')

    @patch('mind_kernel_mcp.tools.history_tool.DynamoDBSecretStore')
    @patch('mind_kernel_mcp.tools.history_tool.GitHubContentProvider')
    def test_execute_history_tool_commit(self, MockProvider, MockStore):
        # Setup mocks
        mock_store = MockStore.return_value
        mock_store.get_github_token.return_value = "fake_token"
        
        mock_provider = MockProvider.return_value
        
        # Mock fetch_file
        def fetch_side_effect(path, ref=None):
            if ref == "commit_sha":
                return json.dumps({"skills": ["python"]})
            else: # HEAD
                return json.dumps({"skills": ["python", "rust"]})
        
        mock_provider.fetch_file.side_effect = fetch_side_effect
        
        # Execute
        args = {
            "userId": "test_user",
            "commit": "commit_sha"
        }
        result = execute_history_tool(args)
        
        # Verification
        self.assertIn("Updates & Shifts", result)
        self.assertIn("rust", result)

    @patch('mind_kernel_mcp.tools.history_tool.DynamoDBSecretStore')
    @patch('mind_kernel_mcp.tools.history_tool.GitHubContentProvider')
    def test_execute_history_tool_since(self, MockProvider, MockStore):
        # Setup mocks
        mock_store = MockStore.return_value
        mock_store.get_github_token.return_value = "fake_token"
        
        mock_provider = MockProvider.return_value
        
        # Mock list_commits
        mock_provider.list_commits.return_value = [{"sha": "old_sha"}]
        
        # Mock fetch_file
        def fetch_side_effect(path, ref=None):
            if ref == "old_sha":
                return json.dumps({"values": ["kindness"]})
            else: # HEAD
                return json.dumps({"values": ["kindness", "courage"]})
        
        mock_provider.fetch_file.side_effect = fetch_side_effect
        
        # Execute
        args = {
            "userId": "test_user",
            "since": "1 week ago"
        }
        result = execute_history_tool(args)
        
        # Verification
        mock_provider.list_commits.assert_called_once()
        self.assertIn("Updates & Shifts", result)
        self.assertIn("courage", result)

if __name__ == '__main__':
    unittest.main()
