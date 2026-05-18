# Mind Kernel MCP Project Guide

## 1. プロジェクトの目的 (Purpose)

**Mind Kernel MCP** は、個人の思考や価値観を言語化した「Mind Kernel (`core.json` 等)」を、外部のLLM（Claude, ChatGPT 等）から安全かつ制御された状態で参照・更新するためのインターフェース（MCPサーバー）です。

自身の「思考のOS」をデジタル化し、AIとの対話を通じて自己理解を深めたり、自身の分身のようなエージェントを育てるための実験的な基盤です。

## 2. 設計思想 (Design Philosophy)

このプロジェクトは以下の3つの哲学に基づいて設計されています。

### 2.1. Privacy by Abstraction (抽象化によるプライバシー保護)
Mind Kernel はプライベートリポジトリで管理されますが、MCPを通じてLLMに渡す情報は、**「外部に出しても恥ずかしくない・実害がない」レベルまで抽象化** されることを前提としています。
- 固有名詞は役割名（例: Aさん→チームリーダー）に置換する。
- 具体的なエピソードは「パターン」として一般化する。

### 2.2. Versioning Strategy (バージョニング戦略)
データの整合性を保つため、以下のバージョン管理を採用しています。
- **Git Tagging**: GitHub上のリリース/タグ機能を利用し、カーネル全体の「ある時点でのスナップショット」を保存します。これにより、思考の特定の時点へのロールバックや参照を可能にします。

### 2.3. Operational Transparency (運用の透明性)
AIによる更新提案は必ず **Pull Request** の形で行われます。
AIが勝手に思考を書き換えることはなく、最終的な決定権（マージ権限）は常に人間にあります。

## 3. 現在の機能 (Capabilities)

現在、以下の機能が実装され、稼働しています。

### 3.1. Kernel Files Management
Mind Kernel を構成する4つの主要モジュールに対し、**読み取り (Fetch)** と **更新提案 (Update)** が可能です。

| モジュール | ファイルパス | 役割 |
| :--- | :--- | :--- |
| **Meta** | `kernel/meta.json` | システム全体の設計思想、公開ポリシー、バージョニングルール |
| **Identity** | `kernel/identity.json` | ユーザーのプロフィール、価値観、行動指針、強み |
| **Patterns** | `kernel/patterns.json` | 経験から得られた思考パターン、問題解決のヒューリスティクス |
| **Backlog** | `kernel/backlog.json` | 現在の課題、将来の実験、解決したいテーマ |

### 3.2. Secure Tools
全ての操作は MCP Tool として提供されます。
- `fetch_mind_kernel_{module}`: 最新のJSONコンテンツを取得します。
- `update_mind_kernel_{module}`: 内容の変更を Pull Request として提案します。JSON Patch による差分更新に対応しています。

## 4. アーキテクチャ (Architecture)

本システムは **AWS Serverless (Lambda + DynamoDB)** 上で動作しつつ、**ローカル開発 (LocalStack / MCP Bridge)** も完全にサポートするハイブリッドな構成です。

```mermaid
graph LR
    User[User / LLM Client] -- Stdio/SSE --> Bridge[MCP Bridge / Local Script]
    Bridge -- Invoke/HTTP --> Server[MCP Server (Lambda)]
    Server -- Oauth/API Key --> Auth[Authentication]
    Server -- Read/Write --> GitHub[GitHub API (Private Repo)]
    Server -- Secrets --> DynamoDB[UserSecrets (Tokens)]
```

### 4.1. Authentication Strategy (認証戦略)
本システムは2つの認証経路を持っています。
1.  **Cognito / OAuth (Web/Remote)**:
    - インターネット経由（HTTPS）でアクセスする場合に使用。
    - `Authorization: Bearer <Token>` ヘッダが必要。
2.  **Local Bypass (Dev/MCP Bridge)**:
    - ローカルで MCP Bridge を経由する場合に使用。
    - サーバー側の環境変数 `LOCAL_USER_ID` と `MCP_API_KEY` を利用し、Cognitoトークンなしで特定の管理者ユーザーとして振る舞います。これにより、LLMクライアント（Claude Desktop 等）からのシームレスな利用を実現しています。

### 4.2. Response Streaming
AWS Lambda の **Response Streaming** を利用し、SSE (Server-Sent Events) を長時間維持することで、非同期なMCP通信を安定させています。

## 5. デプロイと運用 (Deployment & Operations)

### 5.1. Local Development (LocalStack)
ローカル開発環境は `docker compose` と `LocalStack` で構築されています。
以下のコマンドで、コンテナのビルド、LocalStackの起動、DB初期化、Lambda関数のデプロイまでが自動で行われます。

```bash
make up
```

※ `.env` ファイルの設定（特に `GITHUB_TOKEN`）がコンテナ内に反映されます。

### 5.2. Production Deployment (AWS)
本番環境（AWS）へのデプロイには **AWS SAM (Serverless Application Model)** を使用します。

```bash
# 1. ビルド
sam build

# 2. デプロイ (初回は --guided 推奨)
sam deploy --resolve-image-repos
```

デプロイ時には以下のパラメータ入力が求められます：
- `RepoOwner`: GitHubリポジトリのオーナー
- `RepoName`: GitHubリポジトリ名
- `McpApiKey`: ローカル接続用のAPI Key
- `LocalUserId`: ローカル接続時に使用するユーザーID

## 6. クライアント設定とユーザー管理 (Client Setup & User Management)

### 6.1. MCP Client Integration (Cursor / Antigravity)
デプロイされた Lambda 関数は、HTTPS経由で MCP サーバーとして直接利用可能です。
`mcp_config.json` 等の設定ファイルに以下のように `X-API-Key` をヘッダとして付与することで、認証を通過できます。

```json
{
    "mcpServers": {
        "mind-kernel-mcp": {
            "serverUrl": "https://<URL_ID>.lambda-url.<REGION>.on.aws/",
            "headers": {
                "X-API-Key": "<ENV: MCP_API_KEY>"
            }
        }
    }
}
```
このキーが一致する場合、サーバーは `LocalUserId` として振る舞います。

### 6.2. User Registration (DynamoDB)
本システムを利用するユーザー（`LocalUserId` も含む）は、自身の GitHub Personal Access Token (PAT) を DynamoDB の `UserSecrets` テーブルに登録しておく必要があります。
これが行われていないと、ツール実行時に「GitHub Tokenが見つからない」というエラーになります。

**登録レコード例 (DynamoDB)**:
| Partition Key (userId) | Attribute (githubToken) |
| :--- | :--- |
| `LocalUserId`の値 | `github_pat_...` |
| (Cognito User ID) | `github_pat_...` |

※ ローカル開発 (`make up`) の場合は、`scripts/seed_local_db.py` が `.env` の内容を元に自動的にこのレコードを作成してくれます。

---
*Created at: 2025-12-21*

## 7. Troubleshooting & Development Tips (トラブルシューティングと開発のヒント)

開発中によく遭遇するシナリオと対処法です。

### 7.1. Code Changes & Lambda Redeployment
`mind_kernel_mcp/` 配下のコード（ツールロジックやサービス）を変更した場合、変更を反映させるには **Lambda関数の再デプロイ** が必要です。`app` コンテナの再起動だけでは反映されません。

```bash
# Lambda関数を更新して、Activeになるまで待機する
docker compose run --rm app python scripts/deploy_lambda.py
```

### 7.2. Environment Variable Changes (GITHUB_TOKEN etc.)
`.env` ファイルを変更した場合（例: `GITHUB_TOKEN` の更新）、その値をシステムに認識させるために **DBの再シード** が必要です。

```bash
# DynamoDB (UserSecrets) を .env の値で更新する
docker compose run --rm app python scripts/seed_local_db.py
```

### 7.3. Authentication vs Identity
ローカル開発における認証とユーザー識別の違いについて：

*   **`MCP_API_KEY` (Authentication)**: 
    *   **"あなたは誰ですか？"（アクセス許可）**
    *   クライアントがサーバーにアクセスするための合言葉です。認証をパスするために使用します。
*   **`USER_ID` (Identity)**: 
    *   **"どのユーザーのデータを使いますか？"（データコンテキスト）**
    *   認証通過後、システムがどのユーザーとして振る舞うかを決定します。DynamoDBからGitHubトークンなどの秘匿情報を引き出すキーとして使用されます。
