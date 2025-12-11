import os
import boto3
from botocore.exceptions import ClientError
from ..interfaces import SecretStore

class DynamoDBSecretStore(SecretStore):
    def __init__(self):
        region = os.getenv("AWS_REGION", "us-east-1")
        endpoint_url = os.getenv("AWS_ENDPOINT_URL") # LocalStack用
        table_name = os.getenv("DYNAMODB_TABLE_NAME", "UserSecrets")

        self.dynamodb = boto3.resource(
            "dynamodb",
            region_name=region,
            endpoint_url=endpoint_url
        )
        self.table = self.dynamodb.Table(table_name)

    def get_github_token(self, user_id: str) -> str:
        try:
            response = self.table.get_item(Key={"userId": user_id})
        except ClientError as e:
            raise RuntimeError(f"データベースエラー: {e}")

        if "Item" not in response:
            raise ValueError(f"ユーザー {user_id} はシークレットストアに見つかりませんでした。")

        token = response["Item"].get("githubToken")
        if not token:
            raise ValueError(f"ユーザー {user_id} のGitHubトークンが見つかりません。")
        
        return token
