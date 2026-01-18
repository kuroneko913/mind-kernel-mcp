import unittest
from mind_kernel_mcp.tools.history_tool import HISTORY_TOOL_DEFINITION

class TestHistoryToolSchema(unittest.TestCase):
    def test_schema_no_user_id(self):
        properties = HISTORY_TOOL_DEFINITION["inputSchema"]["properties"]
        self.assertNotIn("userId", properties, "userId should not be in schema properties")
        
        required = HISTORY_TOOL_DEFINITION["inputSchema"].get("required", [])
        self.assertNotIn("userId", required, "userId should not be in required list")

if __name__ == '__main__':
    unittest.main()
