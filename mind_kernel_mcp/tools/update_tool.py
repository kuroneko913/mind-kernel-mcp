import json
from typing import Any
from mind_kernel_mcp.services import DynamoDBSecretStore, GitHubContentProvider

UPDATE_TOOL_NAME = "update_mind_kernel_file"
UPDATE_TOOL_DEFINITION = {
    "name": UPDATE_TOOL_NAME,
    "description": "Propose changes to a file (e.g. core.json) in private Mind Kernel repository via Pull Request. Supports JSON Patch for partial updates, ChangeLogs updates, and Update Summaries. The 'content' field is optional and typically unused for core.json updates; provide 'jsonPatch' instead.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "userId": {
                "type": "string",
                "description": "User ID for authentication."
            },
            "version": {
                "type": "string",
                "description": "Version identifier to set in core.json (e.g., 'v1.2.3')."
            },
            "jsonPatch": {
                "type": "array",
                "items": { "type": "object" },
                "description": "JSON Patch operations to apply to core.json. Required for core.json updates."
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
        "required": ["userId", "version", "jsonPatch", "commitMessage"]
    }
}

def execute_update_tool(arguments: dict[str, Any]) -> str:
    """
    Execute the update_mind_kernel_file tool logic.
    Returns the PR creation result or raises an exception.
    """
    user_id = arguments.get("userId")
    version = arguments.get("version")
    json_patch = arguments.get("jsonPatch")
    commit_message = arguments.get("commitMessage")
    change_log_entry = arguments.get("changeLogEntry")
    pr_body = arguments.get("prBody")
    update_summary = arguments.get("updateSummary")

    if not user_id:
        raise ValueError("userId is required")
    if not version:
        raise ValueError("version is required")
    if not commit_message:
        raise ValueError("commitMessage is required")
    if not json_patch:
        raise ValueError("jsonPatch is required for core.json update")

    # Auto-generate changeLogEntry if not supplied
    if not change_log_entry:
        change_log_entry = f"## [{version}] Update\n- Updated core.json version to {version}"

    # Auto-generate PR body if not supplied
    if not pr_body:
        pr_body = f"Update core.json to version {version}."

    # Auto-generate update summary if not supplied
    if not update_summary:
        update_summary = {"version": version}

    # core.json is the only file we allow updates for
    file_path = "core.json"

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
