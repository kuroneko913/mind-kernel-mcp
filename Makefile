.PHONY: build up down logs shell run clean help

build:
	@docker compose build

up:
	@docker compose up -d

down:
	@docker compose down

logs:
	@docker compose logs -f

shell:
	@docker compose run --rm -it app bash

run:
	@docker compose exec -T app python -m mind_kernel_mcp.bridge

inspector:
	@npx @modelcontextprotocol/inspector make run

clean:
	@docker compose down --rmi local -v

help:
	@echo "make build  - Dockerイメージをビルド"
	@echo "make up     - 環境を起動 (LocalStack + 初期化)"
	@echo "make down   - 環境を停止"
	@echo "make logs   - ログを表示"
	@echo "make shell  - コンテナ内のシェルに入る"
	@echo "make run    - MCPサーバーを実行 (クライアント接続用)"
	@echo "make clean  - 環境を停止し、ボリュームとイメージを削除"
