from .fetch_tool import FETCH_TOOL_DEFINITIONS, FETCH_TOOL_EXECUTORS
from .update_tool import UPDATE_TOOL_DEFINITIONS, UPDATE_TOOL_EXECUTORS
from .history_tool import HISTORY_TOOL_DEFINITION, execute_history_tool

# Aggregate Public Tools (excluding generic ones if desired, but here we only expose what's in the lists)
PUBLIC_TOOL_DEFINITIONS = FETCH_TOOL_DEFINITIONS + UPDATE_TOOL_DEFINITIONS + [HISTORY_TOOL_DEFINITION]

# Aggregate Executors
TOOL_EXECUTORS = {
    **FETCH_TOOL_EXECUTORS,
    **UPDATE_TOOL_EXECUTORS,
    HISTORY_TOOL_DEFINITION["name"]: execute_history_tool
}

# Also expose generic tools for internal or optional use (not in PUBLIC_TOOL_DEFINITIONS by default based on user request)
# but we can keep the symbols available.

