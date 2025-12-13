import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run():
    print("Connecting to bridge...", file=sys.stderr)
    
    # Run the bridge script as a subprocess
    # We assume this script is run from the project root in the container
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "mind_kernel_mcp.bridge"],
        env=dict(os.environ) # Inherit env vars (AWS credentials etc)
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List tools
                print("Listing tools...", file=sys.stderr)
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                print(f"Tools found: {tool_names}", file=sys.stderr)
                
                if "fetch_mind_kernel_file" not in tool_names:
                    print("Error: fetch_mind_kernel_file not found!", file=sys.stderr)
                    sys.exit(1)
                
                # Determine user_id
                default_user_id = os.getenv("USER_ID")
                user_id = sys.argv[1] if len(sys.argv) > 1 else default_user_id
                
                if not user_id:
                    print("Error: USER_ID not provided via argument or environment variable.", file=sys.stderr)
                    sys.exit(1)
                
                # Call tool
                print(f"Calling fetch_mind_kernel_file with userId='{user_id}'...", file=sys.stderr)
                result = await session.call_tool("fetch_mind_kernel_file", arguments={"userId": user_id})
                
                # Output result
                if result.content and len(result.content) > 0:
                    print("\n--- Result Content ---")
                    print(result.content[0].text)
                    print("----------------------\n")
                else:
                    print("Empty result content.")
                    
    except Exception as e:
        print(f"Test failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run())
