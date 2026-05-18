import unittest
from unittest.mock import MagicMock, patch
import json
from mind_kernel_mcp.main import server

class TestUpdateToolRPCIntegration(unittest.IsolatedAsyncioTestCase):
    """
    Integration tests for the update tool via the RPC handler.
    """

    @patch('mind_kernel_mcp.tools.update_tool.DynamoDBSecretStore')
    @patch('mind_kernel_mcp.tools.update_tool.GitHubContentProvider')
    async def test_update_file_rpc_flow(self, MockProvider, MockStore):
        # --- Setup Mocks ---
        mock_store = MockStore.return_value
        mock_store.get_github_token.return_value = "fake_token"
        
        mock_provider = MockProvider.return_value
        mock_provider.propose_update.return_value = {"html_url": "https://github.com/test/repo/pull/123", "number": 123}

        # --- Execute RPC Call ---
        # update_mind_kernel_patterns
        params = {
            "name": "update_mind_kernel_patterns",
            "arguments": {
                "version": "v1.2.3",
                "commitMessage": "test update",
                "jsonPatch": [{"op": "add", "path": "/test", "value": "value"}]
            }
        }
        user_id = "integration_test_user_update"

        result_dict = await server.dispatch_rpc("tools/call", params, user_id)

        # --- Verify ---
        # 1. Check RPC structure
        self.assertIn("content", result_dict)
        content_list = result_dict["content"]
        self.assertTrue(len(content_list) > 0)
        text_content = content_list[0]["text"]

        # 2. Check Tool Logic Execution
        mock_store.get_github_token.assert_called_with(user_id)
        mock_provider.propose_update.assert_called()
        
        # 3. Check Response Content
        self.assertIn("Pull Request successfully created", text_content)
        self.assertIn("https://github.com/test/repo/pull/123", text_content)

if __name__ == '__main__':
    unittest.main()
