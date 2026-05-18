import json
from typing import Any, Callable
from mind_kernel_mcp.services import DynamoDBSecretStore, GitHubContentProvider
from .config import KERNEL_FILES

# Generic Tool Definition (Internal)
UPDATE_GENERIC_TOOL_NAME = "update_mind_kernel_file"
UPDATE_GENERIC_TOOL_DEFINITION = {
    "name": UPDATE_GENERIC_TOOL_NAME,
    "description": "Propose changes to a file (e.g. kernel/identity.json) in private Mind Kernel repository via Pull Request. Supports JSON Patch for partial updates, ChangeLogs updates, and Update Summaries.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "filePath": {
                "type": "string",
                "description": "Path to the file to update."
            },
            "jsonPatch": {
                "type": "array",
                "items": { "type": "object" },
                "description": "JSON Patch operations to apply to the target file."
            },
            "commitMessage": {
                "type": "string",
                "description": "Commit message for the Pull Request."
            },
            "prBody": {
                "type": "string",
                "description": "Optional PR body; if omitted a default description will be generated."
            },
            "prNumber": {
                "type": "integer",
                "description": "Optional PR number. If provided, updates the existing PR instead of creating a new one."
            }
        },
        "required": ["jsonPatch", "commitMessage"]
    },
    "annotations": {
        "priority": 0.5,
        "readOnlyHint": False,
        "destructiveHint": True,
        "openWorldHint": False
    },
    "_meta": {
        "openai/isConsequential": True
    }
}

def _execute_update_logic(arguments: dict[str, Any], file_path: str = None) -> str:
    """Internal logic to update file content."""
    user_id = arguments.get("userId")
    # If file_path is passed explicitly (generic tool), iterate it. 
    # If not (facade tool), it should be passed as argument to this function.
    if not file_path:
        file_path = arguments.get("filePath")

    json_patch = arguments.get("jsonPatch")
    commit_message = arguments.get("commitMessage")
    pr_body = arguments.get("prBody")
    pr_number = arguments.get("prNumber")

    if not user_id:
        raise ValueError("userId is required")
    if not file_path:
        raise ValueError("filePath is required")
    if not commit_message:
        raise ValueError("commitMessage is required")
    if not json_patch:
        raise ValueError("jsonPatch is required")
    if not isinstance(json_patch, list):
        raise ValueError("jsonPatch must be a list of JSON Patch operations")
    for op in json_patch:
        if not isinstance(op, dict):
            raise ValueError("Each item in jsonPatch must be a JSON object")

    # Auto-generate PR body if not supplied
    if not pr_body:
        pr_body = f"Update {file_path} via Mind Kernel MCP."

    secret_store = DynamoDBSecretStore()
    token = secret_store.get_github_token(user_id)
    
    content_provider = GitHubContentProvider(token)
    result = content_provider.propose_update(
        file_path, 
        commit_message, 
        content=None, 
        json_patch=json_patch,
        pr_body=pr_body,
        pr_number=pr_number
    )
    
    if pr_number:
        return f"Pull Request successfully updated: PR #{pr_number}"
    else:
        pr_url = result.get("html_url", "URL unknown")
        pr_number_res = result.get("number", "?")
        return f"Pull Request successfully created: {pr_url} (PR #{pr_number_res})"

def execute_update_generic_tool(arguments: dict[str, Any]) -> str:
    """Execute the generic update tool."""
    return _execute_update_logic(arguments)

# Dynamic Tool Generators
def _create_update_facade_definition(key: str, config: dict) -> dict:
    """Creates a tool definition for a specific file."""
    tool_name = f"update_mind_kernel_{key}"
    description = config.get("update_description", f"Propose changes to {key} data via Pull Request.")
    return {
        "name": tool_name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "jsonPatch": { "type": "array", "items": { "type": "object" }, "description": "JSON Patch operations." },
                "commitMessage": { "type": "string", "description": "Commit message for the Pull Request." },
                "prBody": { "type": "string", "description": "Optional PR body." },
                "prNumber": { "type": "integer", "description": "Optional PR number to update specific PR." }
            },
            "required": ["jsonPatch", "commitMessage"]
        },
        "annotations": {
            "priority": 0.5,
            "readOnlyHint": False,
            "destructiveHint": True,
            "openWorldHint": False
        },
        "_meta": {
            "openai/isConsequential": True
        }
    }

def _create_update_executor(file_path: str) -> Callable[[dict[str, Any]], str]:
    """Creates an executor function for a specific file."""
    def executor(arguments: dict[str, Any]) -> str:
        return _execute_update_logic(arguments, file_path)
    return executor

# Generate Registry
UPDATE_TOOL_DEFINITIONS = []
UPDATE_TOOL_EXECUTORS = {}

for key, config in KERNEL_FILES.items():
    tool_def = _create_update_facade_definition(key, config)
    executor = _create_update_executor(config["path"])
    
    UPDATE_TOOL_DEFINITIONS.append(tool_def)
    UPDATE_TOOL_EXECUTORS[tool_def["name"]] = executor
