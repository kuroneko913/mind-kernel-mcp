from typing import Any
from mind_kernel_mcp.services import DynamoDBSecretStore, GitHubContentProvider

FILTER_TOOL_NAME = "fetch_mind_kernel_file"
TOOL_DEFINITION = {
    "name": FILTER_TOOL_NAME,
    "description": "Get a file (default: core.json) from private Mind Kernel repository.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "userId": {
                "type": "string",
                "description": "User ID for authentication."
            },
            "filePath": {
                "type": "string",
                "description": "Path to the file to fetch (default: core.json)."
            }
        },
        "required": ["userId"]
    }
}

def execute_fetch_tool(arguments: dict[str, Any]) -> str:
    """
    Execute the fetch_mind_kernel_file tool logic.
    Returns the content of the file or raises an exception.
    """
    user_id = arguments.get("userId")
    file_path = arguments.get("filePath", "core.json")
    
    if not user_id:
        raise ValueError("userId is required")

    secret_store = DynamoDBSecretStore()
    token = secret_store.get_github_token(user_id)
    
    content_provider = GitHubContentProvider(token)
    return content_provider.fetch_file(file_path)
