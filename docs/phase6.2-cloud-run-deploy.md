# Phase 6.2: Cloud Run デプロイ + Secret Manager

Cloud Runにデプロイし、本番環境で動作する状態にする。

## ゴール

Cloud Run上でプラン生成APIが動く状態にする。Phase 6.3（自動実行）の前提基盤。

## 前提

- Phase 6.1 でDockerコンテナがローカルで動作すること
- GCPプロジェクトが作成済みであること
- Supabase PostgreSQL が利用できること

## やること

### Cloud Run デプロイ

- [ ] Cloud Runサービスのデプロイ（`gcloud run deploy`）
- [ ] 未認証リクエストを拒否する設定
- [ ] リージョン: `asia-northeast1`

```bash
gcloud run deploy run-coach \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated=false
```

### Secret Manager

- [ ] `GARMIN_EMAIL` / `GARMIN_PASSWORD`
- [ ] `OPENAI_API_KEY`
- [ ] `DATABASE_URL`（Supabase接続文字列）
- [ ] Cloud Runから環境変数として注入

### DB接続

- [ ] Supabase PostgreSQL への接続設定
- [ ] transaction pooler を優先（prepared statements前提を避ける）
- [ ] `DATABASE_URL` で接続先を管理

### Google Calendar認証（Workload Identity）

- [ ] run-coach専用カレンダーを個人アカウントで作成
- [ ] Cloud Runのサービスアカウントに専用カレンダーの編集権限を共有
- [ ] Workload Identityで認証（キーファイル不要）
- [ ] コード側で環境に応じて認証を切り替え（ローカル: OAuth / Cloud Run: `google.auth.default()`）
- [ ] 専用カレンダーのIDを `config/settings.yaml` で管理

### Garmin認証（GCSトークン保存方式）

Cloud Runはステートレスなので `~/.garminconnect` のトークン保存方式が使えない。
GCSにトークンを保存し、起動時に復元する方式を採用する。

- [ ] GCSバケット作成（トークン保存用）
- [ ] 起動時にGCSからトークンを取得 → `/tmp` に復元
- [ ] トークンで認証（期限切れ時はパスワードでフォールバック）
- [ ] 認証後、更新されたトークンをGCSに書き戻し
- [ ] Cloud Runのサービスアカウントにバケットの読み書き権限を付与

```
起動時: GCSからトークン取得 → /tmpに復元
  ↓
認証: トークンで認証（期限切れならパスワードでフォールバック）
  ↓
終了時: 更新されたトークンをGCSに書き戻し
```

## テスト方針

- [ ] Cloud Run上で `/health` が応答すること
- [ ] Secret Managerから認証情報を取得できること
- [ ] Supabase PostgreSQL に接続して `workouts` / `workout_splits` を読めること
- [ ] `/generate` でプラン生成が実行されること

## 対象外（Phase 6.3）

- Cloud Scheduler
- 自動実行（週次トリガー）
- リトライ / 障害対応
