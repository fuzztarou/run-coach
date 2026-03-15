# クラウド環境動作確認

Cloud Run上のAPIにリクエストを送り、動作確認を行うスキル。

## トリガー

ユーザーが「クラウド確認」「Cloud Run確認」「本番確認」「cloud」を依頼した時。

## コマンド一覧

```bash
# プラン生成 API（Cloud Run、OIDC認証付き）
make cloud-coach

# Cloud Schedulerジョブを手動実行
make scheduler-run

# 振り返りチェックジョブを手動実行
make check-activity-run

# Cloud Schedulerジョブの状態確認
make scheduler-describe

# GCPプロジェクト切り替え
make gcp-set-project

# profile.yaml を GCS にアップロード
make upload-profile
```

## 手順

### API動作確認

1. `make gcp-set-project` でプロジェクトが正しいか確認
2. `make cloud-coach` でCloud RunのAPIを叩く
3. レスポンスのJSONを確認

### Cloud Scheduler動作確認

1. `make scheduler-describe` でジョブの状態を確認
2. `make scheduler-run` で手動実行
3. Cloud Runのログで実行結果を確認

### 設定ファイル更新

1. `config/profile.yaml` を編集
2. `make upload-profile` でGCSにアップロード

## 注意

- `gcloud auth login` 済みであること
- `cloud-coach` は gcloud でIDトークンを取得しOIDC認証ヘッダを付与する
- 環境変数 `RUN_COACH_GCP_PROJECT_ID`, `RUN_COACH_GCS_BUCKET` が必要なコマンドあり
