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
            "userId": {
                "type": "string",
                "description": "User ID for authentication."
            },
            "filePath": {
                "type": "string",
                "description": "Path to the file to update."
            },
            "version": {
                "type": "string",
                "description": "Version identifier to set in the target file (e.g., 'v1.2.3')."
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
            "changeLogEntry": {
                "type": "string",
                "description": "Optional ChangeLogs.md entry; if omitted a default entry based on version will be generated."
            },
            "prBody": {
                "type": "string",
                "description": "Optional PR body; if omitted a default description will be generated."
            },
            "updateSummary": {
                "type": "object",
                "description": "Optional JSON summary; if omitted a default summary containing the version will be generated."
            }
        },
        "required": ["userId", "filePath", "version", "jsonPatch", "commitMessage"]
    }
}

def _execute_update_logic(arguments: dict[str, Any], file_path: str = None) -> str:
    """Internal logic to update file content."""
    user_id = arguments.get("userId")
    # If file_path is passed explicitly (generic tool), iterate it. 
    # If not (facade tool), it should be passed as argument to this function.
    if not file_path:
        file_path = arguments.get("filePath")

    version = arguments.get("version")
    json_patch = arguments.get("jsonPatch")
    commit_message = arguments.get("commitMessage")
    change_log_entry = arguments.get("changeLogEntry")
    pr_body = arguments.get("prBody")
    update_summary = arguments.get("updateSummary")

    if not user_id:
        raise ValueError("userId is required")
    if not file_path:
        raise ValueError("filePath is required")
    if not version:
        raise ValueError("version is required")
    if not commit_message:
        raise ValueError("commitMessage is required")
    if not json_patch:
        raise ValueError("jsonPatch is required")

    # Auto-generate changeLogEntry if not supplied
    if not change_log_entry:
        change_log_entry = f"## [{version}] Update\n- Updated {file_path} version to {version}"

    # Auto-generate PR body if not supplied
    if not pr_body:
        pr_body = f"Update {file_path} to version {version}."

    # Auto-generate update summary if not supplied
    if not update_summary:
        update_summary = {"version": version}

    secret_store = DynamoDBSecretStore()
    token = secret_store.get_github_token(user_id)
    
    content_provider = GitHubContentProvider(token)
    result = content_provider.propose_update(
        file_path, 
        commit_message, 
        content=None, 
        json_patch=json_patch,
        change_log_entry=change_log_entry,
        pr_body=pr_body,
        update_summary_content=json.dumps(update_summary, ensure_ascii=False, indent=4)
    )
    
    pr_url = result.get("html_url", "URL unknown")
    pr_number = result.get("number", "?")
    return f"Pull Request successfully created: {pr_url} (PR #{pr_number})"

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
                "userId": { "type": "string", "description": "User ID for authentication." },
                "version": { "type": "string", "description": "Version identifier to set (e.g., 'v1.2.3')." },
                "jsonPatch": { "type": "array", "items": { "type": "object" }, "description": "JSON Patch operations." },
                "commitMessage": { "type": "string", "description": "Commit message for the Pull Request." },
                "changeLogEntry": { "type": "string", "description": "Optional ChangeLogs.md entry." },
                "prBody": { "type": "string", "description": "Optional PR body." },
                "updateSummary": { "type": "object", "description": "Optional JSON summary." }
            },
            "required": ["userId", "version", "jsonPatch", "commitMessage"]
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
