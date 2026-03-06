# Garmin API調査

Garmin Connect APIのレスポンス構造やエンドポイントを調査するスキル。

## トリガー

ユーザーが「Garmin」「ワークアウト」「アクティビティ」に関するAPI調査を依頼した時。

## 手順

1. python-garminconnectのソースコードを確認
   - https://github.com/cyberjunky/python-garminconnect
2. 該当メソッドのエンドポイントURLを特定
3. レスポンス構造を確認（開発者ツールのNetwork情報があればそれを優先）
4. DESIGN.mdの「Garminから取得するデータ」セクションを参照・更新

## 既知のエンドポイント

```
# アクティビティ
GET /activity-service/activity/{id}              # サマリー
GET /activity-service/activity/{id}/details       # 詳細（心拍時系列等）
GET /activity-service/activity/{id}/splits        # 1km毎ラップ
GET /activity-service/activity/{id}/hrTimeInZones # 心拍ゾーン
GET /activity-service/activity/{id}/weather       # 天気

# カレンダー・イベント
GET /calendar-service/year/{year}/month/{month}   # 月別カレンダー
GET /calendar-service/event/{id}                  # イベント詳細

# 体調
GET /metrics-service/metrics/racepredictions      # レース予測
```

## 注意

- python-garminconnectは非公式ライブラリ。メソッドがない場合はgarthで直接叩く
- レスポンス構造は実際のAPIレスポンスを開発者ツールで確認するのが確実
