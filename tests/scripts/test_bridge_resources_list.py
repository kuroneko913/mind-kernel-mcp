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
    if "MCP_API_KEY" not in env:
        env["MCP_API_KEY"] = "test-api-key" 
    
    cmd = [sys.executable, "-m", "mind_kernel_mcp.bridge"]
    print(f"Starting bridge: {' '.join(cmd)} (cwd={project_root})")
    
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr, 
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
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            },
            "id": 1
        }
        send_request(process, init_req)
        
        # 2. Initialized Notification
        notify_req = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        process.stdin.write(json.dumps(notify_req) + "\n")
        process.stdin.flush()

        # 3. List Resources
        print("\n--- Sending Resources/List ---")
        read_req = {
            "jsonrpc": "2.0",
            "method": "resources/list",
            "params": {},
            "id": 2
        }
        resp = send_request(process, read_req)
        # print(f"List Resources Response:\n{json.dumps(resp, indent=2, ensure_ascii=False)}")

        # Validation
        if "result" in resp and "resources" in resp["result"]:
            resources = resp["result"]["resources"]
            widget = next((r for r in resources if r["name"] == "Backlog Widget"), None)
            if widget:
                print("Found 'Backlog Widget'. Checking annotations...")
                if "annotations" in widget:
                    annotations = widget["annotations"]
                    print(f"Annotations found: {json.dumps(annotations, indent=2)}")
                    if "widget" in annotations and "csp" in annotations["widget"]:
                        print("SUCCESS: 'widget' and 'csp' annotations present.")
                    else:
                        print("FAILURE: 'widget' or 'csp' missing in annotations.")
                else:
                    print("FAILURE: 'annotations' field missing.")
            else:
                print("FAILURE: 'Backlog Widget' not found in resources.")
        else:
             print("FAILURE: Invalid response structure.")
             print(json.dumps(resp, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        process.terminate()

if __name__ == "__main__":
    main()
