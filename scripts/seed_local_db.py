import boto3
import os
import sys

def seed_db():
    print("LocalStack DynamoDBにシードデータを投入中...")
    
    endpoint_url = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    region = os.getenv("AWS_REGION", "us-east-1")
    table_name = os.getenv("DYNAMODB_TABLE_NAME", "UserSecrets")
    
    # 環境変数からトークンを取得するか、ダミーを使用
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("警告: GITHUB_TOKEN が設定されていません。'dummy_token' を使用します。フェッチは401エラーで失敗します。", file=sys.stderr)
        github_token = "dummy_token"

    dynamodb = boto3.resource(
        "dynamodb",
        region_name=region,
        endpoint_url=endpoint_url
    )
    
    table = dynamodb.Table(table_name)
    
    # Security: Use a UUID from env (must be set in .env)
    user_id = os.getenv("USER_ID")
    if not user_id:
        print("Error: USER_ID environment variable is not set.")
        sys.exit(1)
    
    try:
        table.put_item(
            Item={
                "userId": user_id,
                "githubToken": github_token
            }
        )
        print(f"ユーザー '{user_id}' にトークンを正常にシードしました。")
    except Exception as e:
        print(f"DBシード中のエラー: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    seed_db()
