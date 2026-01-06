import unittest
from unittest.mock import patch, MagicMock
import asyncio
from mind_kernel_mcp.prompts.handlers import handle_list_prompts, handle_get_prompt
import mcp.types as types

class TestPromptsHandlers(unittest.TestCase):
    def test_list_prompts(self):
        prompts = asyncio.run(handle_list_prompts())
        self.assertTrue(len(prompts) >= 3)
        names = [p.name for p in prompts]
        self.assertIn("reflect", names)
        self.assertIn("consult_board", names)

    @patch("mind_kernel_mcp.prompts.handlers._execute_fetch_logic")
    def test_get_search_prompt_reflect(self, mock_fetch):
        # Setup mock to return dummy content for patterns
        mock_fetch.return_value = '{"patterns": ["pattern1"]}'
        
        args = {"context": "test context"}
        user_id = "test_user"
        
        result = asyncio.run(handle_get_prompt("reflect", args, user_id))
        
        self.assertIsInstance(result, types.GetPromptResult)
        self.assertEqual(len(result.messages), 2) # System(User) + User
        
        # Verify content substitution
        mock_fetch.assert_called_with(user_id, "kernel/patterns.json")
        
        # System message should contain patterns content
        self.assertIn('{"patterns": ["pattern1"]}', result.messages[0].content.text)
        
        # User message should contain context
        self.assertIn("test context", result.messages[1].content.text)

    @patch("mind_kernel_mcp.prompts.handlers._execute_fetch_logic")
    def test_get_search_prompt_consult_board(self, mock_fetch):
        mock_fetch.return_value = '{"identity": "ceo"}'
        
        args = {"topic": "strategic decision"}
        user_id = "test_user"
        
        result = asyncio.run(handle_get_prompt("consult_board", args, user_id))
        
        self.assertEqual(len(result.messages), 2)
        mock_fetch.assert_called_with(user_id, "kernel/identity.json")
        self.assertIn("strategic decision", result.messages[1].content.text)

if __name__ == "__main__":
    unittest.main()
