# Phase 6.4: Terraform によるインフラ管理

GCPリソースをTerraformでコード管理する。リポジトリは `run-coach` とは別のプライベートリポジトリで管理する。

## ゴール

GCPインフラの構成をコード化し、再現可能な状態にする。

## 前提

- Phase 6.1〜6.3 で手動構築したGCPリソースが動作していること

## 別リポジトリ構成

```
run-coach-infra/          # プライベートリポジトリ
├── main.tf               # プロバイダ設定 + モジュール呼び出し
├── variables.tf           # project_id, region
├── outputs.tf             # SA email, Cloud Run URL等
├── terraform.tfvars       # 変数値
├── versions.tf            # Terraform/Provider バージョン + GCSバックエンド
├── modules/
│   ├── iam/               # SA 3つ (runner, scheduler, deployer)
│   ├── secret-manager/    # シークレット4つ (箱のみ)
│   ├── gcs/               # run-coach-config バケット + IAM
│   ├── artifact-registry/ # Docker リポジトリ
│   ├── cloud-run/         # run-coach サービス + IAM
│   ├── cloud-scheduler/   # run-coach-daily ジョブ
│   └── workload-identity/ # GitHub Actions OIDC連携
├── .tflint.hcl            # tflint設定 (google plugin)
├── .claude/
│   └── settings.json      # hooks: terraform apply/destroy をブロック
└── .gitignore
```

### run-coachリポジトリと分ける理由

- インフラ変更とアプリ変更のライフサイクルが異なる
- プライベートリポジトリで権限を厳格に管理できる

### シークレット管理方針

- TerraformではSecret Managerの**リソース（箱）だけ**を管理する
- シークレットの**値**はTerraformで管理しない（`gcloud` CLIで手動設定）

## 管理対象リソース

| リソース | 用途 |
|---------|------|
| IAM (SA 3つ) | runner / scheduler / deployer |
| Secret Manager (4つ) | GARMIN_EMAIL, GARMIN_PASSWORD, OPENAI_API_KEY, DATABASE_URL |
| GCS バケット | run-coach-config (Garminトークン保存) |
| Artifact Registry | Docker イメージリポジトリ |
| Cloud Run サービス | run-coachアプリのデプロイ先 |
| Cloud Scheduler ジョブ | 毎朝9時 (JST) プラン生成トリガー |
| Workload Identity | GitHub Actions OIDC → deployer SA |

## 実施記録

### tfstate管理

- GCSバケット `run-coach-tfstate` を手動作成（バージョニング有効）
- `versions.tf` でGCSバックエンド設定

### import結果

全16リソースを `terraform import` → `terraform plan` で **No changes** を確認:

- `google_service_account` x3
- `google_secret_manager_secret` x4
- `google_storage_bucket` x1 + `iam_member` x1
- `google_artifact_registry_repository` x1
- `google_cloud_run_service` x1 + `iam_member` x1
- `google_cloud_scheduler_job` x1
- `google_iam_workload_identity_pool` x1
- `google_iam_workload_identity_pool_provider` x1
- `google_service_account_iam_member` x1

### Claude Code Hooks

`.claude/settings.json` に PreToolUse hook を設定し、`terraform apply` / `terraform destroy` を拒否。手動でのみ実行可能。

### Lint

- `terraform fmt -check -recursive` → OK
- `tflint` (google plugin) → Warning 0

## やったこと

- [x] プライベートリポジトリ `run-coach-infra` 作成
- [x] tfstate用GCSバケット `run-coach-tfstate` 手動作成
- [x] Terraform基盤ファイル作成 + GCSバックエンド設定
- [x] Claude Code Hooks設定 (apply/destroy ブロック)
- [x] tflint設定 (google plugin)
- [x] 7モジュール作成 (iam, secret-manager, gcs, artifact-registry, cloud-run, cloud-scheduler, workload-identity)
- [x] 全16リソースの `terraform import`
- [x] `terraform plan` → **No changes** 確認
- [x] lint通過確認

## 対象外

- CI/CD パイプライン（GitHub Actions からの `terraform apply`）は将来検討
- Supabase（GCP外）
- Google Calendar共有設定（Calendar UI管理）
- tfstate用GCSバケット自体（手動管理）
- シークレットの値
