# Phase 6.4: Terraform によるインフラ管理

GCPリソースをTerraformでコード管理する。リポジトリは `run-coach` とは別のプライベートリポジトリで管理する。

## ゴール

GCPインフラの構成をコード化し、再現可能な状態にする。

## 前提

- Phase 6.1〜6.3 で手動構築したGCPリソースが動作していること

## 別リポジトリ構成

```
run-coach-infra/          # プライベートリポジトリ
├── main.tf
├── variables.tf
├── outputs.tf
├── modules/
│   ├── cloud-run/
│   ├── cloud-scheduler/
│   ├── secret-manager/
│   ├── gcs/
│   └── iam/
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
| Cloud Run サービス | run-coachアプリのデプロイ先 |
| Cloud Scheduler ジョブ | 週次プラン生成トリガー |
| Secret Manager シークレット | Garmin / OpenAI / DATABASE_URL |
| GCS バケット | Garminトークン保存 |
| IAM | サービスアカウント、権限設定 |
| Workload Identity | Google Calendar認証 |

## やること

- [ ] プライベートリポジトリ `run-coach-infra` 作成
- [ ] Terraform state の管理方針を決める（GCSバックエンド）
- [ ] 既存の手動構築リソースをTerraform importする
- [ ] 各リソースのモジュール化
- [ ] `terraform plan` / `terraform apply` で再現できることを確認

## 対象外

- CI/CD パイプライン（GitHub Actions からの `terraform apply`）は将来検討
