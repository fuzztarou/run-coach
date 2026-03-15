# マイグレーション

Alembicによるデータベースマイグレーションを管理するスキル。

## トリガー

ユーザーが「マイグレーション」「migrate」「DB変更」「テーブル追加」を依頼した時。

## コマンド一覧

```bash
# マイグレーション実行（最新まで適用）
make migrate

# マイグレーション履歴を表示
make migrate-history

# 新規マイグレーション作成（モデル変更後に実行）
make migrate-new MSG="add users table"

# 1つ前にロールバック
make migrate-down
```

## 手順

### 新規マイグレーション作成

1. SQLAlchemyモデルを変更
2. DBコンテナが起動していることを確認（`make db-up`）
3. `make migrate-new MSG="変更の説明"` で自動生成
4. 生成されたファイル（`alembic/versions/`）を確認・修正
5. `make migrate` で適用
6. `make migrate-history` で反映を確認

### ロールバック

1. `make migrate-history` で現在の状態を確認
2. `make migrate-down` で1つ戻す
3. 必要に応じて繰り返す

## 注意

- マイグレーション実行前にDBコンテナが起動している必要がある
- autogenerateの結果は必ず目視確認すること（意図しない変更が含まれる場合がある）
