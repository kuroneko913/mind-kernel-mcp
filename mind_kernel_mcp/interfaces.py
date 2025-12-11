from abc import ABC, abstractmethod

class ContentProvider(ABC):
    @abstractmethod
    def fetch_core_json(self) -> str:
        """core.json の内容を取得します。"""
        pass

class SecretStore(ABC):
    @abstractmethod
    def get_github_token(self, user_id: str) -> str:
        """指定されたユーザーのGitHubパーソナルアクセストークンを取得します。"""
        pass
