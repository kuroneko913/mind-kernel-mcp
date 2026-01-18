import json
import jsonpatch
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from mind_kernel_mcp.services import DynamoDBSecretStore, GitHubContentProvider

HISTORY_TOOL_NAME = "fetch_mind_kernel_history"
HISTORY_TOOL_DEFINITION = {
    "name": HISTORY_TOOL_NAME,
    "description": "Analyze the growth and changes of the Mind Kernel over a specific period.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "since": {
                "type": "string",
                "description": "Start date for analysis (e.g., '2023-01-01', '1 week ago')."
            },
            "commit": {
                "type": "string",
                "description": "Specific commit hash to compare against."
            }
        },
        "required": []
    }
}

def _parse_relative_date(date_spec: str) -> str:
    """Parses simple relative date strings like '1 week ago' into ISO 8601 format."""
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    date_spec = date_spec.lower().strip()
    
    if date_spec.endswith("ago"):
        parts = date_spec.split()
        if len(parts) >= 3:
            try:
                # better parse: "1 week ago". split -> ["1", "week", "ago"]
                amount = int(parts[0])
                unit_str = parts[1]
                
                # Unit mapping for cleaner logic
                unit_multipliers = {
                    "day": timedelta(days=1),
                    "week": timedelta(weeks=1),
                    "month": timedelta(days=30), # approx
                    "year": timedelta(days=365), # approx
                    "hour": timedelta(hours=1)
                }
                
                # Find matching unit
                multiplier = next((m for u, m in unit_multipliers.items() if u in unit_str), None)
                
                if not multiplier:
                     raise ValueError("Unknown time unit")
                
                delta = multiplier * amount
                target_date = now - delta
                
                return target_date.isoformat() + "Z"
            except (ValueError, IndexError):
                pass
    
    # Try parsing strictly as date
    try:
        # Try YYYY-MM-DD
        dt = datetime.strptime(date_spec, "%Y-%m-%d")
        return dt.isoformat() + "Z"
    except ValueError:
        pass

    return date_spec # Return as is if we can't parse, hoping it's already ISO or API accepts it

def summarize_entity(data: Any) -> str:
    """
    Extracts a human-readable summary from a dictionary (description, name, values).
    Returns a string representation.
    """
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return ", ".join([str(x) for x in data])
    if isinstance(data, dict):
        context = []
        if "name" in data:
            context.append(f"Name: {data['name']}")
        if "description" in data:
            context.append(f"Description: {data['description']}")
        if "definitions" in data:
             context.append(f"Definition: {data['definitions']}")
        if "values" in data:
            context.append(f"Values: {', '.join(data['values']) if isinstance(data['values'], list) else data['values']}")
        if "signals" in data:
            signals = data['signals']
            if isinstance(signals, list):
                context.append(f"Signals: {', '.join(signals)}")
            else:
                context.append(f"Signals: {signals}")
        
        # If no specific semantic keys found, dump the whole thing if it's small, else just keys
        if not context:
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        return " | ".join(context)
    return str(data)

def detailed_semantic_diff(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Recursively compares two dictionaries to find significant additions and changes.
    Returns a flat list of change events.
    """
    changes = []
    
    def _handle_dict_diff(old_dict: Dict, new_dict: Dict, current_path: str):
        all_keys = set(old_dict.keys()) | set(new_dict.keys())
        
        for key in all_keys:
            # Ignore metadata
            if key in ["version", "schema", "$schema", "id"]:
                continue

            new_path = f"{current_path}.{key}" if current_path else key
            
            if key not in old_dict:
                changes.append({
                    "type": "ADDED",
                    "key": new_path,
                    "value": new_dict[key],
                    "context": summarize_entity(new_dict[key])
                })
            elif key not in new_dict:
                changes.append({
                    "type": "REMOVED",
                    "key": new_path,
                    "value": old_dict[key],
                    "context": summarize_entity(old_dict[key])
                })
            else:
                _recurse(old_dict[key], new_dict[key], new_path)

    def _recurse(old, new, path):
        if isinstance(old, dict) and isinstance(new, dict):
            _handle_dict_diff(old, new, path)
        elif old != new:
             changes.append({
                "type": "MODIFIED",
                "key": path,
                "old": old,
                "new": new,
                "context": f"{old} -> {new}"
             })

    _recurse(old_data, new_data, "")
    return changes

def execute_history_tool(arguments: dict[str, Any]) -> str:
    user_id = arguments.get("userId")
    since = arguments.get("since")
    commit = arguments.get("commit")

    if not user_id:
        raise ValueError("userId is required")
    
    if not since and not commit:
        raise ValueError("Either 'since' or 'commit' must be provided.")

    secret_store = DynamoDBSecretStore()
    token = secret_store.get_github_token(user_id)
    provider = GitHubContentProvider(token)

    target_commit = commit

    # Resolve commit if 'since' is provided
    if not target_commit and since:
        iso_date = _parse_relative_date(since)
        # We want the commit BEFORE this date, effectively. 
        # Actually 'since' usually means we want changes that happened AFTER this date.
        # So we compare HEAD against the state AT 'since'.
        # To get state AT 'since', we need the commit closest to 'since' (before or at).
        # GitHub API 'until' param gets commits before a date.
        commits = provider.list_commits(until=iso_date, limit=1)
        if not commits:
            return json.dumps({"error": f"No commits found before {since} ({iso_date})."}, ensure_ascii=False)
        target_commit = commits[0]['sha']

    files_to_analyze = [
        ("kernel/patterns.json", "Capabilities & Skills"),
        ("kernel/identity.json", "Mindset & Values"),
        ("kernel/meta.json", "System & Meta"),
        ("kernel/backlog.json", "Backlog & Tasks"),
    ]

    report = {}

    for file_path, category_label in files_to_analyze:
        try:
            # Old data
            old_content_str = provider.fetch_file(file_path, ref=target_commit)
            old_json = json.loads(old_content_str)
        except Exception as e:
            # File might not have existed or error fetching
            old_json = {}
            # print(f"Warning: Could not fetch {file_path} at {target_commit}: {e}")

        try:
            # New data (HEAD)
            new_content_str = provider.fetch_file(file_path) # Default to HEAD
            new_json = json.loads(new_content_str)
        except Exception:
            new_json = {}
        
        if not old_json and not new_json:
            continue

        changes = detailed_semantic_diff(old_json, new_json)
        if changes:
             report[category_label] = changes
    
    return json.dumps(report, ensure_ascii=False)
