# Phase 6.3: Cloud Scheduler + 自動実行

Cloud Schedulerで週次プラン生成を自動実行する。

## ゴール

Macを閉じていても自動でプラン生成が動く状態にする。Phase 7（LINE通知）の前提基盤。

## 前提

- Phase 6.2 でCloud Run上にプラン生成APIがデプロイ済みであること

## フロー

```mermaid
flowchart TB
    CS[Cloud Scheduler<br>毎週月曜朝] -->|HTTP + OIDC| CR

    subgraph CR[Cloud Run: run-coach]
        FG[fetch_garmin] --> FC[fetch_calendar<br>Google Calendar API]
        FG --> DB[(Supabase<br>PostgreSQL)]
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

### Cloud Scheduler

- [ ] ジョブ作成（毎週月曜朝にHTTPリクエスト）
- [ ] ターゲット: Cloud Runの `/generate` エンドポイント
- [ ] タイムゾーン: `Asia/Tokyo`

### IAM認証

- [ ] Cloud SchedulerにCloud Run起動権限を付与
- [ ] OIDCトークンでの認証設定
- [ ] 未認証リクエストの拒否を確認

### リトライ / 障害対応

- [ ] Cloud Scheduler側でHTTP失敗時のリトライ設定
- [ ] Garmin API / LLM APIの一時的失敗はアプリ側で短いリトライ
- [ ] 部分失敗時はログを残し、再実行できるようにする
- [ ] DB接続失敗時は `500` を返し、Schedulerに再試行させる

## テスト方針

- [ ] Cloud Scheduler → Cloud Run のE2Eテスト
- [ ] IAM認証が正しく機能すること（認証なしリクエストが拒否されること）
- [ ] リトライが正しく動作すること
- [ ] 週次実行でプラン生成 → Calendar同期が完了すること
