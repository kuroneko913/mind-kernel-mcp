import os
import requests
import base64
import json
import time
import jsonpatch
from datetime import datetime
from typing import Optional, List
from ..interfaces import ContentProvider

class GitHubContentProvider(ContentProvider):
    def __init__(self, token: str):
        self.token = token
        self.owner = os.getenv("REPO_OWNER", "")
        self.repo = os.getenv("REPO_NAME", "") 
        self.path = "core.json"

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def fetch_file(self, path: str = "core.json", ref: Optional[str] = None) -> str:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{path}"
        headers = self._get_headers()
        params = {}
        if ref:
            params["ref"] = ref
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            content = response.json()
            # GitHub APIはコンテンツをbase64エンコードして返します
            if "content" in content:
                 return base64.b64decode(content["content"]).decode('utf-8')
            else:
                 raise ValueError("GitHubからの無効なレスポンス: 'content' フィールドがありません。")
        elif response.status_code == 404:
             raise FileNotFoundError(f"{self.owner}/{self.repo} に {path} が見つかりません。")
        elif response.status_code == 401:
             raise PermissionError("無効なGitHubトークンです。")
        else:
            response.raise_for_status()
            return ""

    def update_file(self, path: str, content: str, commit_message: str, branch: Optional[str] = None) -> dict:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{path}"
        headers = self._get_headers()

        # 1. 現在のファイルのSHAを取得
        params = {}
        if branch:
            params["ref"] = branch

        get_response = requests.get(url, headers=headers, params=params)
        sha = None
        if get_response.status_code == 200:
            current_data = get_response.json()
            sha = current_data.get("sha")
        elif get_response.status_code != 404:
             get_response.raise_for_status()

        # 2. ファイルを更新/作成
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        data = {
            "message": commit_message,
            "content": encoded_content
        }
        if sha:
            data["sha"] = sha
        if branch:
            data["branch"] = branch

        put_response = requests.put(url, headers=headers, json=data)
        
        if put_response.status_code in [200, 201]:
            return put_response.json()
        else:
            put_response.raise_for_status()
            return {}

    def get_default_branch(self) -> str:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
        headers = self._get_headers()
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("default_branch", "main")

    def create_branch(self, branch_name: str, base_sha: str):
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/git/refs"
        headers = self._get_headers()
        data = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()

    def get_ref_sha(self, ref: str) -> str:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/git/ref/heads/{ref}"
        headers = self._get_headers()
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()["object"]["sha"]

    def create_pull_request(self, title: str, body: str, head: str, base: str) -> dict:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls"
        headers = self._get_headers()
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()

    def _insert_change_log_entry(self, current_logs: str, change_log_entry: str) -> str:
        """Insert change_log_entry after the ## [Unreleased] header if present, otherwise append at end."""
        lines = current_logs.splitlines()
        insert_idx = None
        for i, line in enumerate(lines):
            if line.strip().lower() == "## [unreleased]":
                insert_idx = i
                break
        if insert_idx is not None:
            # Content before and after the header line
            before = "\n".join(lines[:insert_idx + 1])
            after = "\n".join(lines[insert_idx + 1:])
            # Remove a leading newline from after to avoid duplicate blank lines
            after = after.lstrip("\n")
            new_entry = "\n\n" + change_log_entry.strip() + "\n\n"
            change_log_new_entry = before + new_entry + after
        else:
            change_log_new_entry = current_logs + "\n\n" + change_log_entry.strip() + "\n"
        return change_log_new_entry

    def _create_work_branch(self, path: str) -> tuple[str, str]:
        """Creates a new branch for the proposed update."""
        default_branch = self.get_default_branch()
        base_sha = self.get_ref_sha(default_branch)
        safe_path = "".join([c if c.isalnum() else "-" for c in path])
        branch_name = f"update-{safe_path}-{int(time.time())}"
        self.create_branch(branch_name, base_sha)
        return branch_name, default_branch

    def _prepare_new_content(self, path: str, content: Optional[str], json_patch: Optional[List[dict]], branch_name: str) -> str:
        """Prepares the new content string based on direct content or a JSON patch."""
        if json_patch:
            try:
                current_content_str = self.fetch_file(path, ref=branch_name)
                current_content = json.loads(current_content_str)
            except (ValueError, json.JSONDecodeError):
                 raise ValueError(f"JSON Patch cannot be applied: {path} is not a valid JSON file or does not exist.")
            
            patch = jsonpatch.JsonPatch(json_patch)
            new_content = patch.apply(current_content)
            return json.dumps(new_content, indent=2, ensure_ascii=False)
        elif content is not None:
            return content
        else:
            raise ValueError("Either content or json_patch must be provided.")

    def _update_change_log(self, change_log_entry: str, commit_message: str, branch_name: str):
        """Updates the ChangeLogs.md file with a new entry."""
        log_path = "ChangeLogs.md"
        try:
            current_logs = self.fetch_file(log_path, ref=branch_name)
        except FileNotFoundError:
            current_logs = "# Change Logs\n"
        
        new_logs = self._insert_change_log_entry(current_logs, change_log_entry)
        self.update_file(log_path, new_logs, f"Update {log_path} for {commit_message}", branch=branch_name)

    def _update_summary(self, update_summary_content: str, branch_name: str):
        """Creates or updates an update summary file."""
        today = datetime.now().strftime("%Y-%m-%d")
        summary_path = f"update_summary/update_summary_{today}.json"
        self.update_file(summary_path, update_summary_content, f"Add update summary for {today}", branch=branch_name)

    def _create_pr(self, path: str, commit_message: str, pr_body: Optional[str], branch_name: str, default_branch: str) -> dict:
        """Creates a pull request for the changes."""
        body = pr_body if pr_body else f"Automated update for {path} via Mind Kernel MCP.\n\nCommit Message: {commit_message}"
        return self.create_pull_request(
            title=commit_message,
            body=body,
            head=branch_name,
            base=default_branch
        )

    def _update_target_file(self, path: str, new_content: str, commit_message: str, branch_name: str) -> None:
        """Update the target file (core.json) on the given branch."""
        self.update_file(path, new_content, commit_message, branch=branch_name)

    def _validate_update_params(self, commit_message: str, json_patch: Optional[List[dict]], content: Optional[str]) -> None:
        """Validate required parameters for an update.
        Raises ValueError if validation fails.
        """
        if not commit_message:
            raise ValueError("commitMessage is required")
        if not (json_patch or content):
            raise ValueError("Either content or json_patch must be provided.")

    def propose_update(self, path: str, commit_message: str, content: Optional[str] = None, json_patch: Optional[List[dict]] = None, change_log_entry: Optional[str] = None, pr_body: Optional[str] = None, update_summary_content: Optional[str] = None) -> dict:
        # 1. 作業用ブランチの作成
        branch_name, default_branch = self._create_work_branch(path)

        # 2. 新しいコンテンツの準備
        new_content_str = self._prepare_new_content(path, content, json_patch, branch_name)

        # 3. バリデーションチェック
        self._validate_update_params(commit_message, json_patch, content)

        # 4. ファイルを更新 (新しいブランチで)
        self._update_target_file(path, new_content_str, commit_message, branch_name)

        # 4. ChangeLogs.md の更新 (指定がある場合)
        if change_log_entry:
            self._update_change_log(change_log_entry, commit_message, branch_name)

        # 5. Update Summary の更新 (指定がある場合)
        if update_summary_content:
            self._update_summary(update_summary_content, branch_name)
        #6. Pull Requestの作成
        pr = self._create_pr(path, commit_message, pr_body, branch_name, default_branch)
        return pr
