"""
Configuration for Mind Kernel MCP tools.
Defines the files exposed via facade tools.
"""

KERNEL_FILES = {
    "identity": {
        "path": "kernel/identity.json",
        "fetch_description": "Get the User Profile. Use this to understand the user's core values, mission, and basic information.",
        "update_description": "Update User Profile information."
    },
    "meta": {
        "path": "kernel/meta.json",
        "fetch_description": "Get System Metadata. CRITICAL: Fetch this FIRST to understand the kernel version, active modules, and system status.",
        "update_description": "Update System Metadata, active modules, or version info."
    },
    "patterns": {
        "path": "kernel/patterns.json",
        "fetch_description": "Get Thinking Patterns. Use this to reference standard optimization patterns and heuristics.",
        "update_description": "Update Thinking Patterns or heuristics."
    },
    "backlog": {
        "path": "kernel/backlog.json",
        "fetch_description": "Get the System Backlog. Use this to read current tasks, todos, and future plans.",
        "update_description": "Update the Backlog (add/remove tasks)."
    }
}
