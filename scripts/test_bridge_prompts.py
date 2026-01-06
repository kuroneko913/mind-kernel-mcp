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
    return json.loads(line)

def main():
    # Detect project root (parent of 'scripts' directory)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    # Start bridge.py as a subprocess using module execution
    env = os.environ.copy()
    if "MCP_API_KEY" not in env:
        env["MCP_API_KEY"] = "test-api-key" 
    
    cmd = [sys.executable, "-m", "mind_kernel_mcp.bridge"]
    print(f"Starting bridge: {' '.join(cmd)} (cwd={project_root})")
    
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr, # Pass stderr through
        text=True,
        env=env,
        cwd=project_root
    )

    try:
        # 1. Initialize
        print("\n--- Sending Initialize ---")
        init_req = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", # Correct version
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            },
            "id": 1
        }
        resp = send_request(process, init_req)
        print(f"Initialize Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")
        
        # 2. Notifications/Initialized
        print("\n--- Sending Initialized Notification ---")
        notify_req = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        # Notifications don't get responses in stdio server usually, but let's send it.
        json_str = json.dumps(notify_req) + "\n"
        process.stdin.write(json_str)
        process.stdin.flush()

        # 3. List Prompts
        print("\n--- Sending Prompts/List ---")
        list_req = {
            "jsonrpc": "2.0",
            "method": "prompts/list",
            "params": {},
            "id": 2
        }
        resp = send_request(process, list_req)
        print(f"Prompts List Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")
        
        # 4. Get Prompt (reflect)
        print("\n--- Sending Prompts/Get (reflect) ---")
        get_req = {
            "jsonrpc": "2.0",
            "method": "prompts/get",
            "params": {
                "name": "reflect",
                "arguments": {"context": "Testing the bridge connection."}
            },
            "id": 3
        }
        resp = send_request(process, get_req)
        print(f"Get Prompt Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        process.terminate()

if __name__ == "__main__":
    # Activate venv python if possible or just use sys.executable assuming ran from venv
    main()
