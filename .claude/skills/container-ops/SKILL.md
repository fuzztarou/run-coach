# ローカルコンテナ操作

Docker Composeでapp + dbの起動・停止・ログ確認を行うスキル。

## トリガー

ユーザーが「コンテナ」「docker」「起動」「停止」「ログ」を依頼した時。

## コマンド一覧

```bash
# app + db 起動
make up

# 停止
make down

# ログ表示（follow）
make logs

# コンテナ状態を確認
make ps

# app を再起動
make restart

# app イメージをリビルド
make build

# DB のみ起動
make db-up

# DB のみ停止
make db-down

# DB ログ表示
make db-logs

# psql で接続
make db-psql
```

## 手順

1. `make ps` でコンテナの現在の状態を確認
2. 目的に応じたコマンドを実行
3. 実行後に `make ps` で状態を再確認

## 注意

- `make up` は `--build` 付きなのでコード変更が自動反映される
- ポート番号は `config/settings.yaml` の `app_port` から取得される（デフォルト: 8080）
