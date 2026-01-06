import os
import asyncio
from typing import Any, Dict, Optional, List
import mcp.types as types

from mind_kernel_mcp.tools import (
    PUBLIC_TOOL_DEFINITIONS, TOOL_EXECUTORS
)
from mind_kernel_mcp.prompts import handle_list_prompts, handle_get_prompt

# --- Handlers ---

async def handle_initialize(params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"subscribe": False, "listChanged": False},
            "prompts": {"listChanged": False}
        },
        "serverInfo": {
            "name": "mind-kernel-mcp",
            "version": "1.0.0"
        }
    }

async def handle_notifications_initialized(params: Dict[str, Any], user_id: Optional[str]) -> None:
    # Just acknowledge
    return None

async def handle_ping(params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    return {}

async def handle_tools_list(params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    return {
        "tools": PUBLIC_TOOL_DEFINITIONS
    }

async def handle_tools_call(params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    if not user_id:
        raise ValueError("Unauthorized: Missing valid authentication token")

    name = params.get("name")
    args = params.get("arguments", {})
    
    # Inject user_id
    args["userId"] = user_id
    
    if name in TOOL_EXECUTORS:
        # Executes the tool synchronously (if it's not async)
        # However, TOOL_EXECUTORS functions might be blocking?
        # In sse.py it was just called directly: content = TOOL_EXECUTORS[name](args)
        # If they are IO bound, they should ideally be async or run in executor.
        # For now, we keep existing behavior.
        content = TOOL_EXECUTORS[name](args)
        return {
            "content": [
                {
                    "type": "text",
                    "text": content
                }
            ]
        }
    else:
        raise ValueError(f"Unknown tool: {name}")

async def handle_resources_list(params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    return {
        "resources": [
            {
                "uri": "ui://widget/backlog.html",
                "name": "Backlog Widget",
                "description": "React Widget for displaying backlog items.",
                "mimeType": "text/html+skybridge",
                "annotations": {
                    "widget": {
                        "csp": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';",
                        "domain": "backlog-widget"
                    }
                }
            }
        ]
    }

async def handle_resources_read(params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    uri = params.get("uri", "")
    if uri == "ui://widget/backlog.html":
        # Load JS and CSS from web/dist relative to current working directory
        # In Lambda, CWD is usually /var/task. We need to ensure web/dist is there.
        # We try to use os.getcwd which is root of lambda task
        base_path = os.path.join(os.getcwd(), "web", "dist")
        
        if not os.path.exists(os.path.join(base_path, "widget.js")):
            # Fallback for different lambda root or local dev
            current_dir = os.path.dirname(os.path.abspath(__file__)) # mind_kernel_mcp/
            # web is sibling of mind_kernel_mcp
            base_path = os.path.join(os.path.dirname(current_dir), "web", "dist")

        if not os.path.exists(os.path.join(base_path, "widget.js")):
            print(f"ERROR: widget.js not found at {base_path}")
            print(f"DEBUG: CWD is {os.getcwd()}")
        
        js_content = ""
        try:
            with open(os.path.join(base_path, "widget.js"), "r", encoding="utf-8") as f:
                js_content = f.read()
        except FileNotFoundError:
            raise ValueError(f"Server error: widget.js not found at {base_path}")

        css_content = ""
        css_path = os.path.join(base_path, "widget.css")
        if os.path.exists(css_path):
            with open(css_path, "r", encoding="utf-8") as f:
                css_content = f.read()

        html = f"""
<div id="backlog-root"></div>
<style>
{css_content}
</style>
<script type="module">
{js_content}
</script>
""".strip()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/html+skybridge",
                    "text": html
                }
            ]
        }
    else:
        raise ValueError("Resource not found") # Will be caught and mapped to error code if needed, or we can raise specific exceptions

async def handle_prompts_list(params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    prompts = await handle_list_prompts()
    return {
        "prompts": [p.model_dump() for p in prompts]
    }

async def handle_prompts_get(params: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    if not user_id:
        raise ValueError("Unauthorized: Missing valid authentication token")

    name = params.get("name")
    args = params.get("arguments", {})
    
    result = await handle_get_prompt(name, args, user_id)
    return result.model_dump()


# --- Dispatcher ---

HANDLERS = {
    "initialize": handle_initialize,
    "notifications/initialized": handle_notifications_initialized,
    "ping": handle_ping,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
    "resources/list": handle_resources_list,
    "resources/read": handle_resources_read,
    "prompts/list": handle_prompts_list,
    "prompts/get": handle_prompts_get,
}

async def dispatch_rpc(method: str, params: Dict[str, Any], user_id: Optional[str]) -> Optional[Dict[str, Any]]:
    handler = HANDLERS.get(method)
    if not handler:
        raise NotImplementedError(f"Method {method} not found")
    
    return await handler(params, user_id)
