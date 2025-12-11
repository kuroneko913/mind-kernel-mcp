import json
import os
import sys

# Lambda環境でパッケージルートをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mind_kernel_mcp.services.dynamo_service import DynamoDBSecretStore
from mind_kernel_mcp.services.github_service import GitHubContentProvider

def lambda_handler(event, context):
    """
    MCPツール実行用Lambdaハンドラ
    Expected event: {"tool": "fetch_mind_kernel_core", "arguments": {"userId": "..."}}
    """
    print(f"Received event: {json.dumps(event)}")
    
    tool_name = event.get("tool")
    arguments = event.get("arguments", {})
    
    if tool_name == "fetch_mind_kernel_core":
        return handle_fetch_core(arguments)
    
    return {
        "status": "error",
        "message": f"Unknown tool: {tool_name}"
    }

def handle_fetch_core(arguments):
    user_id = arguments.get("userId")
    if not user_id:
        return {"status": "error", "message": "userId is required"}

    try:
        # サービスの初期化
        # Lambda環境変数はデプロイ時に設定される
        
        # 1. DynamoDBからトークン取得
        secret_store = DynamoDBSecretStore()
        token = secret_store.get_github_token(user_id)
        
        if not token:
             return {"status": "error", "message": f"Token not found for user: {user_id}"}
        
        # 2. GitHubからcore.json取得
        # トークンを設定してプロバイダを初期化
        content_provider = GitHubContentProvider(token)
        core_json_content = content_provider.fetch_core_json()
        
        return {
            "status": "success",
            "content": core_json_content
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
