import os
from mangum import Mangum
from mind_kernel_mcp.server import ServerlessMcpServer
from mind_kernel_mcp.tools import PUBLIC_TOOL_DEFINITIONS, TOOL_EXECUTORS
from mind_kernel_mcp.prompts.config import PROMPT_DEFINITIONS
from mind_kernel_mcp.prompts.handlers import handle_get_prompt

server = ServerlessMcpServer(name="mind-kernel-mcp", version="1.0.0")

# Register Tools
for tool_def in PUBLIC_TOOL_DEFINITIONS:
    server.register_tool(tool_def, TOOL_EXECUTORS[tool_def["name"]])

# Register Prompts
for prompt_name, prompt_def in PROMPT_DEFINITIONS.items():
    arguments = [
        {
            "name": arg["name"],
            "description": arg.get("description"),
            "required": arg.get("required", False)
        } for arg in prompt_def.get("arguments", [])
    ]
    formatted_def = {
        "name": prompt_def["name"],
        "description": prompt_def["description"],
        "arguments": arguments
    }
    
    def make_handler(name):
        async def handler(prompt_name, args, user_id):
            res = await handle_get_prompt(prompt_name, args, user_id)
            return res.model_dump()
        return handler

    # We need to bind the loop variable correctly
    server.register_prompt(formatted_def, make_handler(prompt_name))


# Register Resources
async def handle_backlog_widget(uri: str, user_id: str):
    # Load JS and CSS from web/dist relative to current working directory
    base_path = os.path.join(os.getcwd(), "web", "dist")
    
    if not os.path.exists(os.path.join(base_path, "widget.js")):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.join(os.path.dirname(current_dir), "web", "dist")

    if not os.path.exists(os.path.join(base_path, "widget.js")):
        print(f"ERROR: widget.js not found at {base_path}")
    
    js_content = ""
    try:
        with open(os.path.join(base_path, "widget.js"), "r", encoding="utf-8") as f:
            js_content = f.read()
    except FileNotFoundError:
        raise ValueError("Internal error: Required widget assets not found.")

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

server.register_resource(
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
    },
    handle_backlog_widget
)

app = server.create_app()
handler = Mangum(app, lifespan="off")
