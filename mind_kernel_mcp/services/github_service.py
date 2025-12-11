import os
import requests
import base64
from ..interfaces import ContentProvider

class GitHubContentProvider(ContentProvider):
    def __init__(self, token: str):
        self.token = token
        self.owner = os.getenv("REPO_OWNER", "")
        self.repo = os.getenv("REPO_NAME", "") 
        self.path = "core.json"

    def fetch_core_json(self) -> str:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{self.path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            content = response.json()
            # GitHub APIはコンテンツをbase64エンコードして返します
            if "content" in content:
                 return base64.b64decode(content["content"]).decode('utf-8')
            else:
                 raise ValueError("GitHubからの無効なレスポンス: 'content' フィールドがありません。")
        elif response.status_code == 404:
             raise FileNotFoundError(f"{self.owner}/{self.repo} に core.json が見つかりません。")
        elif response.status_code == 401:
             raise PermissionError("無効なGitHubトークンです。")
        else:
            response.raise_for_status()
            return "" # raise_for_statusのためここには到達しません
