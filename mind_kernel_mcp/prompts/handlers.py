from typing import List
import mcp.types as types
from mind_kernel_mcp.tools.config import KERNEL_FILES
from mind_kernel_mcp.tools.fetch_tool import _execute_fetch_logic
from .config import PROMPT_DEFINITIONS

async def handle_list_prompts() -> List[types.Prompt]:
    """Returns the list of available prompts."""
    prompts = []
    for key, definition in PROMPT_DEFINITIONS.items():
        arguments = [
            types.PromptArgument(
                name=arg["name"],
                description=arg.get("description"),
                required=arg.get("required", False)
            ) for arg in definition.get("arguments", [])
        ]
        prompts.append(types.Prompt(
            name=definition["name"],
            description=definition["description"],
            arguments=arguments
        ))
    return prompts

async def handle_get_prompt(name: str, arguments: dict, user_id: str) -> types.GetPromptResult:
    """Generates the prompt messages for a given prompt."""
    if name not in PROMPT_DEFINITIONS:
        raise ValueError(f"Unknown prompt: {name}")
    
    definition = PROMPT_DEFINITIONS[name]
    dependencies = definition.get("dependencies", {})
    
    # 1. Fetch Dependencies
    context_data = {}
    for placeholder, kernel_key in dependencies.items():
        if kernel_key not in KERNEL_FILES:
            raise ValueError(f"Unknown kernel file key: {kernel_key}")
        
        file_path = KERNEL_FILES[kernel_key]["path"]
        try:
            # We use the internal fetch logic which uses SecretStore -> GitHub
            content = _execute_fetch_logic(user_id, file_path)
            context_data[placeholder] = content
        except Exception as e:
            raise ValueError(f"Failed to fetch dependency {kernel_key}: {str(e)}")

    # 2. Format Messages
    messages = []
    
    # System Message (as User message with instruction)
    if "system_template" in definition:
        system_text = definition["system_template"].format(**context_data)
        messages.append(types.PromptMessage(
            role="user", 
            content=types.TextContent(type="text", text=system_text)
        ))
        
    # User Message
    if "user_template" in definition:
        # Merge arguments into context_data for user template
        user_context = {**context_data, **arguments}
        # Check for missing args
        for arg in definition.get("arguments", []):
            if arg["required"] and arg["name"] not in arguments:
                raise ValueError(f"Missing required argument: {arg['name']}")
                
        user_text = definition["user_template"].format(**user_context)
        messages.append(types.PromptMessage(
            role="user",
            content=types.TextContent(type="text", text=user_text)
        ))
        
    return types.GetPromptResult(
        description=definition["description"],
        messages=messages
    )
