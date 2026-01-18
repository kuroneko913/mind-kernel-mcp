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
                amount = int(parts[-3]) # e.g. "1" in "1 week ago" logic is a bit loose with split
                # better parse: "1 week ago". split -> ["1", "week", "ago"]
                amount = int(parts[0])
                unit = parts[1]
                
                if "day" in unit:
                    delta = timedelta(days=amount)
                elif "week" in unit:
                    delta = timedelta(weeks=amount)
                elif "month" in unit:
                    delta = timedelta(days=amount * 30) # approx
                elif "year" in unit:
                    delta = timedelta(days=amount * 365)
                elif "hour" in unit:
                    delta = timedelta(hours=amount)
                else:
                     raise ValueError("Unknown time unit")
                
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

def extract_rich_context(data: Any) -> str:
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
    
    def _recurse(old, new, path):
        if isinstance(old, dict) and isinstance(new, dict):
            all_keys = set(old.keys()) | set(new.keys())
            for key in all_keys:
                new_path = f"{path}.{key}" if path else key
                
                # Ignore metadata
                if key in ["version", "schema", "$schema", "id"]:
                    continue

                if key not in old:
                    # ADDED
                    changes.append({
                        "type": "ADDED",
                        "key": new_path,
                        "value": new[key],
                        "context": extract_rich_context(new[key])
                    })
                elif key not in new:
                    # REMOVED (We mostly care about growth/additions, but good to know)
                    pass 
                else:
                    # MODIFIED - recurse
                    _recurse(old[key], new[key], new_path)
        elif old != new:
             # Leaf node change
             changes.append({
                "type": "MODIFIED",
                "key": path,
                "old": old,
                "new": new,
                "context": f"{old} -> {new}"
             })

    _recurse(old_data, new_data, "")
    return changes

def generate_rich_markdown(report: Dict[str, List[Dict[str, Any]]], duration_label: str):
    md = f"# Mind Kernel Growth Report ({duration_label})\n\n"
    
    if not report:
        md += "No significant changes detected in the specified period.\n"
        return md

    for category, changes in report.items():
        if not changes:
            continue
            
        md += f"## {category}\n"
        
        # Filter for top-level additions or significant changes to reduce noise
        added_items = [c for c in changes if c['type'] == 'ADDED']
        modified_items = [c for c in changes if c['type'] == 'MODIFIED']
        
        if added_items:
            md += "### 🆕 New Acquisitions\n"
            for item in added_items:
                key_name = item['key'].split('.')[-1]
                full_key = item['key']
                
                # Indent based on depth or just list
                if isinstance(item['value'], dict):
                    md += f"- **{key_name}** (`{full_key}`)\n"
                    context = item['context']
                    if context:
                        md += f"  > {context}\n"
                else:
                     md += f"- **{key_name}**: {item['value']}\n"

        if modified_items:
             md += "\n### 🔄 Updates & Shifts\n"
             for item in modified_items:
                 key_name = item['key'].split('.')[-1]
                 # Show semantic changes
                 md += f"- **{key_name}**: {item['context']}\n"
        
        md += "\n"
        
    return md

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
    label = f"Since {since}" if since else f"Since commit {commit[:7] if commit else 'unknown'}"

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
            return f"No commits found before {since} ({iso_date})."
        target_commit = commits[0]['sha']
        label = f"Since {since} ({target_commit[:7]})"

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
    
    return generate_rich_markdown(report, label)
