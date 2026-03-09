# Phase 6: Cloud Run + Cloud Scheduler デプロイ

Cloud Runにデプロイし、自動実行環境を構築。

## ゴール

Macを閉じていても自動でプラン生成が動く状態にする。Phase 7（LINE通知）の前提基盤。

## フロー

### 週次プラン生成

```mermaid
flowchart TB
    CS[Cloud Scheduler<br>毎週月曜朝] -->|HTTP| CR

    subgraph CR[Cloud Run: run-coach]
        FG[fetch_garmin] --> FC[fetch_calendar<br>Google Calendar API]
        FC --> FW[fetch_weather]
        FW --> GR[ガードレール]
        GR --> GEN[LLM: プラン生成]
        GEN --> CHK[セルフチェック]
        CHK -->|OK| OUT[output_plan<br>+ Calendar同期]
        CHK -->|NG| GEN
    end

    OUT -.->|Phase 7| LINE[LINE Push通知]

    style CS fill:#4a9eff,color:#fff
    style CR fill:#f5f5f5,color:#333
```

## やること

### Cloud Run デプロイ

- [ ] Dockerfile作成
- [ ] Cloud Runサービスのデプロイ
- [ ] Cloud Schedulerの設定（週次プラン生成トリガー）
- [ ] Google Calendar APIのサービスアカウント設定
- [ ] Secret Managerで認証情報を管理（Garmin / LLM API）

### HTTPエンドポイント

- [ ] `/generate` — Cloud Schedulerから呼ばれ、プラン生成 → Calendar同期
- [ ] ヘルスチェック用エンドポイント

## テスト方針

- [ ] 既存テスト全通し: Phase 1〜5のテストがCloud Run環境でも通ること
- [ ] 認証: Secret Managerからの認証情報取得が動くか
- [ ] HTTPエンドポイント: `/generate` が正しくプラン生成を実行するか
- [ ] E2Eテスト: Cloud Scheduler → Cloud Run の一連の流れ

```python
# テスト例
def test_generate_endpoint(client):
    """/generate エンドポイントが正常に動作するか"""
    response = client.post("/generate")
    assert response.status_code == 200

def test_secret_manager_integration():
    """Secret Managerから認証情報を取得できるか"""
    # モック環境での検証
    secret = get_secret("GARMIN_EMAIL")
    assert secret is not None
```
