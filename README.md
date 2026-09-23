# mind-kernel-mcp

個人の思考や価値観を言語化した **Mind Kernel** を、Claude や ChatGPT から安全に参照・更新するための MCP (Model Context Protocol) サーバーです。

- **リモート MCP サーバー** — AWS Lambda 上で動作し、MCP クライアントから HTTP で直接接続できます
- **OAuth 2.0 認証** — Amazon Cognito による認可と JWT 検証。`/.well-known/oauth-protected-resource` を実装しています
- **SSE ストリーミング** — Lambda Function URL のレスポンスストリーミング (`InvokeMode: RESPONSE_STREAM`) を利用。API Gateway ではレスポンスストリーミングができないため、この構成を選んでいます
- **更新は必ず Pull Request 経由** — AI による変更提案は PR として作成され、マージ権限は常に人間側にあります
- **ローカル完全再現** — LocalStack 上に Lambda + DynamoDB を再現し、AWS にデプロイせずに開発できます

カーネルは `identity` / `meta` / `patterns` / `backlog` の4モジュールで構成され、プライベートリポジトリ上の JSON として管理されます。

> **詳細ドキュメント**: プロジェクトの設計思想やアーキテクチャについては [PROJECT_GUIDE.md](./PROJECT_GUIDE.md) を参照してください。

## アーキテクチャ

| | 本番 (AWS) | ローカル開発 |
| --- | --- | --- |
| 実行環境 | Lambda (arm64 コンテナイメージ) | Docker + LocalStack |
| エンドポイント | Lambda Function URL (`RESPONSE_STREAM`) | stdio ブリッジスクリプト |
| 認証 | Cognito OAuth 2.0 / JWT 検証 | API Key |
| データストア | DynamoDB (ユーザー別クレデンシャル) | LocalStack DynamoDB |
| デプロイ | AWS SAM | `make up` |

## セットアップ


1. **Docker コンテナのビルド**
   ```bash
   docker compose build
   ```

2. **環境設定**
   `.env` ファイルを編集し、以下の項目を設定してください:
   - `GITHUB_TOKEN`: GitHub Personal Access Token
   - `REPO_OWNER`, `REPO_NAME`: 対象のリポジトリ
   - `USER_ID`: シードデータとして使用するユーザーID (デフォルトはUUIDが既に設定されています)

## ローカルでの実行 (Makefile使用)

`Makefile` を用意しました。以下のコマンドで簡単に操作できます。

1. **環境の起動 (ビルド + LocalStack + 初期化)**
   ```bash
   make up
   ```
   ※ 初回はイメージのビルドと、LocalStackの起動待ち(数秒)が発生します。
   ※ 完了するまで少し待ってください。

2. **MCP サーバーの実行 (クライアント接続用)**
   ```bash
   make run
   ```
   このコマンドは標準入出力(stdio)を使用し、MCPクライアントからの接続を受け付けます。

### その他のコマンド
- `make build`: Dockerイメージの再ビルド
- `make logs`: アプリケーションとLocalStackのログを表示
- `make shell`: コンテナ内のシェルに入る
- `make down`: 環境の停止
### VSCode / Claude Desktop での利用

利用形態に合わせて、以下のいずれかの設定を `claude_desktop_config.json` 等に追記してください。

#### A. ローカル開発環境 (LocalStck + Docker)
開発中のコードをローカルで即座に動かしたい場合に使用します。
※ 事前に `make up` でコンテナを起動しておく必要があります。

```json
{
  "mcpServers": {
    "mind-kernel-local": {
      "command": "make",
      "args": ["run"]
    }
  }
}
```
※ 絶対パス指定の例: `"command": "/usr/bin/make", "args": ["run", "-C", "/abs/path/to/project"]`

#### B. 本番環境 (AWS Lambda)
デプロイ済みの Lambda 関数に直接接続します。
Dockerコンテナを起動しておく必要がなく、常時利用に適しています。

```json
{
  "mcpServers": {
    "mind-kernel-remote": {
      "serverUrl": "https://<FunctionUrlID>.lambda-url.<Region>.on.aws/",
      "headers": {
        "X-API-Key": "<ENV: MCP_API_KEY>"
      }
    }
  }
}
```

### MCP Inspector でのテスト

ブラウザ上で動作検証ができる MCP Inspector を簡単に起動できます。

```bash
make inspector
```
実行すると URL が表示されますので、ブラウザでアクセスしてツールをテストしてください。

## 使用方法
このサーバーは以下のツールを公開しています: `fetch_mind_kernel_core`。
引数: `{"userId": ""}`。

## プロジェクト構造
- `mind_kernel_mcp/`: ソースコード。
  - `services/`: DynamoDB および GitHub サービス。
- `infra/`: インフラストラクチャスクリプト (LocalStack 初期化)。
- `scripts/`: ヘルパースクリプト (DB シード)。
