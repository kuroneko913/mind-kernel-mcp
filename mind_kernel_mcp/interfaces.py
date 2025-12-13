from abc import ABC, abstractmethod

class ContentProvider(ABC):
    @abstractmethod
    @abstractmethod
    def fetch_file(self, path: str, ref: str = None) -> str:
        """指定されたファイルの内容を取得します。"""
        pass

    @abstractmethod
    def update_file(self, path: str, content: str, commit_message: str) -> dict:
        """指定されたファイルを更新または作成します。"""
        pass

    @abstractmethod
    def propose_update(
        self, 
        path: str, 
        commit_message: str, 
        content: str = None, 
        json_patch: list = None, 
        change_log_entry: str = None, 
        pr_body: str = None, 
        update_summary_content: str = None
    ) -> dict:
        """変更をPull Requestとして提案します。"""
        pass

class SecretStore(ABC):
    @abstractmethod
    def get_github_token(self, user_id: str) -> str:
        """指定されたユーザーのGitHubパーソナルアクセストークンを取得します。"""
        pass
