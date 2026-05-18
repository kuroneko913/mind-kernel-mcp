import unittest
from unittest.mock import MagicMock, patch
import json
from mind_kernel_mcp.main import server

class TestHistoryToolRPCIntegration(unittest.IsolatedAsyncioTestCase):
    """
    Integration tests for the history tool via the RPC handler.
    Verifies that the RPC layer correctly injects dependencies (userId) and invokes the tool.
    """

    @patch('mind_kernel_mcp.tools.history_tool.DynamoDBSecretStore')
    @patch('mind_kernel_mcp.tools.history_tool.GitHubContentProvider')
    async def test_fetch_history_rpc_flow(self, MockProvider, MockStore):
        # --- Setup Mocks ---
        mock_store = MockStore.return_value
        mock_store.get_github_token.return_value = "fake_token"
        
        mock_provider = MockProvider.return_value
        # Mock fetch_file to return dummy checks
        def fetch_side_effect(path, ref=None):
            # Return slightly different content based on ref to simulate changes
            if ref: # Old commit
                return json.dumps({"skills": ["python"]})
            else: # HEAD
                return json.dumps({"skills": ["python", "rust"]})
        
        mock_provider.fetch_file.side_effect = fetch_side_effect
        # Mock list_commits for 'since' logic
        mock_provider.list_commits.return_value = [{"sha": "old_sha_123"}]

        # --- Execute RPC Call ---
        params = {
            "name": "fetch_mind_kernel_history",
            "arguments": {
                "since": "1 week ago"
            }
        }
        user_id = "integration_test_user"

        # handle_tools_call is async
        result_dict = await server.dispatch_rpc("tools/call", params, user_id)

        # --- Verify ---
        # 1. Check RPC structure
        self.assertIn("content", result_dict)
        content_list = result_dict["content"]
        self.assertTrue(len(content_list) > 0)
        text_content = content_list[0]["text"]

        # 2. Check Tool Logic Execution (userId injection working?)
        # mock_store.get_github_token should have been called with "integration_test_user"
        mock_store.get_github_token.assert_called_with(user_id)

        # 3. Check Response Content
        # We expect "Capabilities & Skills" (MODIFIED) for skills changing from python->python,rust
        self.assertIn("Capabilities & Skills", text_content)
        self.assertIn("rust", text_content)

if __name__ == '__main__':
    unittest.main()
