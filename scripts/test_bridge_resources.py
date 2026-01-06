import subprocess
import json
import sys
import os

def send_request(process, request):
    json_str = json.dumps(request) + "\n"
    process.stdin.write(json_str)
    process.stdin.flush()
    
    # Read response line by line
    line = process.stdout.readline()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        print(f"Failed to decode JSON: {line}")
        return None

def main():
    # Detect project root (parent of 'scripts' directory)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    # Start bridge.py as a subprocess using module execution
    env = os.environ.copy()
    # AWS_ENDPOINT_URL etc are already in os.environ from docker-compose
    # We only set keys if they are missing or need specific test values?
    # Actually, for localstack in docker, we MUST trust the env vars.
    if "MCP_API_KEY" not in env:
        env["MCP_API_KEY"] = "test-api-key" 
    
    # Use -m to run as module from project root
    cmd = [sys.executable, "-m", "mind_kernel_mcp.bridge"]
    print(f"Starting bridge: {' '.join(cmd)} (cwd={project_root})")
    
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr, # Pass stderr through
        text=True,
        env=env,
        cwd=project_root  # Run from project root so mind_kernel_mcp is found
    )

    try:
        # 1. Initialize
        print("\n--- Sending Initialize ---")
        init_req = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            },
            "id": 1
        }
        resp = send_request(process, init_req)
        # print(f"Initialize Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")
        
        # 2. Initialized Notification
        notify_req = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        process.stdin.write(json.dumps(notify_req) + "\n")
        process.stdin.flush()

        # 3. Read Resource
        print("\n--- Sending Resources/Read (ui://widget/backlog.html) ---")
        read_req = {
            "jsonrpc": "2.0",
            "method": "resources/read",
            "params": {
                "uri": "ui://widget/backlog.html"
            },
            "id": 2
        }
        resp = send_request(process, read_req)
        print(f"Read Resource Response:\n{json.dumps(resp, indent=2, ensure_ascii=False)}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        process.terminate()

if __name__ == "__main__":
    main()
