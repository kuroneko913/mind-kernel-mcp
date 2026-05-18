import unittest
from unittest.mock import MagicMock, patch
import json
from mind_kernel_mcp.main import server

class TestFetchToolRPCIntegration(unittest.IsolatedAsyncioTestCase):
    """
    Integration tests for the fetch tool via the RPC handler.
    """

    @patch('mind_kernel_mcp.tools.fetch_tool.DynamoDBSecretStore')
    @patch('mind_kernel_mcp.tools.fetch_tool.GitHubContentProvider')
    async def test_fetch_file_rpc_flow(self, MockProvider, MockStore):
        # --- Setup Mocks ---
        mock_store = MockStore.return_value
        mock_store.get_github_token.return_value = "fake_token"
        
        mock_provider = MockProvider.return_value
        mock_provider.fetch_file.return_value = json.dumps({"identity": "test_identity"})

        # --- Execute RPC Call ---
        # fetch_mind_kernel_identity relies on pre-configured path
        params = {
            "name": "fetch_mind_kernel_identity",
            "arguments": {}
        }
        user_id = "integration_test_user_fetch"

        result_dict = await server.dispatch_rpc("tools/call", params, user_id)

        # --- Verify ---
        # 1. Check RPC structure
        self.assertIn("content", result_dict)
        content_list = result_dict["content"]
        self.assertTrue(len(content_list) > 0)
        text_content = content_list[0]["text"]

        # 2. Check Tool Logic Execution
        mock_store.get_github_token.assert_called_with(user_id)
        mock_provider.fetch_file.assert_called()
        
        # 3. Check Response Content
        self.assertIn("test_identity", text_content)

if __name__ == '__main__':
    unittest.main()
