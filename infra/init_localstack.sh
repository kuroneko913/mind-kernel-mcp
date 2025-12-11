#!/bin/bash
echo "LocalStackリソースを初期化中..."

TABLE_NAME="${DYNAMODB_TABLE_NAME:-UserSecrets}"

echo "DynamoDBテーブルを作成中: $TABLE_NAME"
awslocal dynamodb create-table \
    --table-name "$TABLE_NAME" \
    --attribute-definitions AttributeName=userId,AttributeType=S \
    --key-schema AttributeName=userId,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5

echo "初期化完了。"
