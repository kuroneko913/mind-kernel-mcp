import sys
import json
import subprocess
import os

def verify_rpc():
    # Start bridge.py as a subprocess
    process = subprocess.Popen(
        [sys.executable, "-m", "mind_kernel_mcp.bridge"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        env=os.environ.copy(),
        text=True,
        bufsize=0
    )

    # 1. Send Initialize
    init_req = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "verifier", "version": "1.0"}
        },
        "id": 1
    }
    
    print(f"Sending Init...", file=sys.stderr)
    process.stdin.write(json.dumps(init_req) + "\n")
    process.stdin.flush()

    # Read Init Response
    init_res_str = process.stdout.readline()
    print(f"Init Response: {init_res_str}", file=sys.stderr)

    # 2. Send Initialized notification
    initialized_notif = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {}
    }
    process.stdin.write(json.dumps(initialized_notif) + "\n")
    process.stdin.flush()

    # 3. Send tools/list
    list_req = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": 2
    }
    print(f"Sending tools/list...", file=sys.stderr)
    process.stdin.write(json.dumps(list_req) + "\n")
    process.stdin.flush()

    # Read list response
    list_res_str = process.stdout.readline()
    print(f"List Response Raw: {list_res_str}", file=sys.stderr)
    
    try:
        data = json.loads(list_res_str)
        tools = data.get("result", {}).get("tools", [])
        backlog = next((t for t in tools if t["name"] == "fetch_mind_kernel_backlog"), None)
        
        if backlog:
            print("\n--- Backlog Tool Definition ---")
            print(json.dumps(backlog, indent=2))
            
            if "_meta" in backlog:
                print("\n[SUCCESS] _meta found in backlog tool!")
            else:
                print("\n[FAILURE] _meta NOT found in backlog tool.")
        else:
            print("[FAILURE] Backlog tool not found.")
            
            
    except Exception as e:
        print(f"Error parsing response: {e}")

    # 4. Verify Resource Read
    print(f"\nSending resources/read for ui://widget/backlog.html...", file=sys.stderr)
    read_req = {
        "jsonrpc": "2.0",
        "method": "resources/read",
        "params": {
            "uri": "ui://widget/backlog.html"
        },
        "id": 3
    }
    process.stdin.write(json.dumps(read_req) + "\n")
    process.stdin.flush()
    
    read_res_str = process.stdout.readline()
    try:
        read_data = json.loads(read_res_str)
        content_list = read_data.get("result", {}).get("contents", [])
        if content_list:
            blob = content_list[0].get("text", "")
            if "<script" in blob and "backlog-root" in blob:
                print("[SUCCESS] Resource read returned valid HTML with script!")
                # print(blob[:200] + "...") 
            else:
                print("[FAILURE] Resource read returned unexpected content.")
                print(blob[:200])
        else:
             print(f"[FAILURE] Resource read failed or empty: {read_res_str}")
    except Exception as e:
        print(f"Error parsing resource response: {e}")

    process.terminate()

if __name__ == "__main__":
    verify_rpc()
