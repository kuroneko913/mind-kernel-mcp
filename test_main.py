import asyncio
from mind_kernel_mcp.main import app

async def run_test():
    print("App created successfully:", app)

if __name__ == "__main__":
    asyncio.run(run_test())
