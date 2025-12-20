from typing import Any, Callable
from mind_kernel_mcp.services import DynamoDBSecretStore, GitHubContentProvider
from .config import KERNEL_FILES

# Generic Tool Definition (Internal)
FETCH_GENERIC_TOOL_NAME = "fetch_mind_kernel_file"
FETCH_GENERIC_TOOL_DEFINITION = {
    "name": FETCH_GENERIC_TOOL_NAME,
    "description": "Get a file (e.g. kernel/identity.json) from private Mind Kernel repository.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "filePath": {
                "type": "string",
                "description": "Path to the file to fetch."
            }
        },
        "required": ["filePath"]
    }
}

def _execute_fetch_logic(user_id: str, file_path: str) -> str:
    """Internal logic to fetch file content."""
    secret_store = DynamoDBSecretStore()
    token = secret_store.get_github_token(user_id)
    
    content_provider = GitHubContentProvider(token)
    return content_provider.fetch_file(file_path)

def execute_fetch_generic_tool(arguments: dict[str, Any]) -> str:
    """Execute the generic fetch tool."""
    user_id = arguments.get("userId")
    file_path = arguments.get("filePath")
    
    if not user_id:
        raise ValueError("userId is required")
    if not file_path:
        raise ValueError("filePath is required")

    return _execute_fetch_logic(user_id, file_path)

# Dynamic Tool Generators
def _create_fetch_facade_definition(key: str, config: dict) -> dict:
    """Creates a tool definition for a specific file."""
    tool_name = f"fetch_mind_kernel_{key}"
    description = config.get("fetch_description", f"Get the {key} data from Mind Kernel.")
    return {
        "name": tool_name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }

def _create_fetch_executor(file_path: str) -> Callable[[dict[str, Any]], str]:
    """Creates an executor function for a specific file."""
    def executor(arguments: dict[str, Any]) -> str:
        user_id = arguments.get("userId")
        if not user_id:
            raise ValueError("userId is required")
        return _execute_fetch_logic(user_id, file_path)
    return executor

# Generate Registry
FETCH_TOOL_DEFINITIONS = []
FETCH_TOOL_EXECUTORS = {}

# Add Generic Tool (Internal use only, not added to public list by default if user wants to hide it,
# but for now we keep it separated or decide in __init__.py what to expose)
# The generic tool is separate.

for key, config in KERNEL_FILES.items():
    tool_def = _create_fetch_facade_definition(key, config)
    executor = _create_fetch_executor(config["path"])
    
    FETCH_TOOL_DEFINITIONS.append(tool_def)
    FETCH_TOOL_EXECUTORS[tool_def["name"]] = executor
