# mind-kernel-mcp

Mind Kernel プライベートリポジトリから `core.json` を取得するための MCP (Model Context Protocol) サーバーです。
LocalStack 上の Lambda + DynamoDB で動作するサーバーレスアーキテクチャをローカルで完全に再現しています。
MCPクライアントはローカルのブリッジスクリプトを経由して Lambda を呼び出します。

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

VSCode の MCP対応拡張機能 (Claude Dev, Roo Codeなど) や Claude Desktop アプリの設定ファイルに以下のように追記してください。
設定例は `claude_desktop_config_example.json` にもあります。

```json
{
  "mcpServers": {
    "mind-kernel": {
      "command": "make",
      "args": ["run"]
    }
  }
}
```
※ `make` コマンドが実行できるパス（プロジェクトルート）で開いている必要があります。絶対パスを指定する場合は `"command": "/usr/bin/make", "args": ["run", "-C", "/abs/path/to/project"]` のようにしてください。

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
  - `server.py`: MCP サーバー定義。
  - `services/`: DynamoDB および GitHub サービス。
- `infra/`: インフラストラクチャスクリプト (LocalStack 初期化)。
- `scripts/`: ヘルパースクリプト (DB シード)。
