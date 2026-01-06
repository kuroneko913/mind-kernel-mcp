.DEFAULT_GOAL := help
.PHONY: build up down logs shell run clean help

build: ## Dockerイメージをビルド
	@docker compose build

up: ## 環境を起動 (LocalStack + 初期化)
	@docker compose up -d

down: ## 環境を停止
	@docker compose down

logs: ## ログを表示
	@docker compose logs -f

shell: ## コンテナ内のシェルに入る
	@docker compose run --rm -it app bash

run: ## MCPサーバーを実行 (クライアント接続用)
	@docker compose exec -T app python -m mind_kernel_mcp.bridge

inspector: ## MCP Inspectorを起動してサーバーをテスト
	@npx @modelcontextprotocol/inspector make run

clean: ## 環境を停止し、ボリュームとイメージを削除
	@docker compose down --rmi local -v

help: ## ヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
