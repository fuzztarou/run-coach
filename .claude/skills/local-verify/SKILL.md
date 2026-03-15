# ローカル動作確認

ローカルのDockerコンテナに対してAPIリクエストを送り、動作確認を行うスキル。

## トリガー

ユーザーが「ローカル確認」「動作確認」「local」「ローカルで試す」を依頼した時。

## コマンド一覧

```bash
# プラン生成 API（JSON整形出力）
make local-coach

# LINE テスト送信
make line-test-message
```

## 手順

1. `make ps` でコンテナが起動しているか確認
2. 起動していなければ `make up` で起動
3. `make logs` でアプリの起動完了を確認
4. `make local-coach` でプラン生成APIを叩く
5. レスポンスのJSONを確認

## 注意

- コンテナが起動していないとリクエストが失敗する
- `local-coach` は `POST /internal/coach` にリクエストを送る（ローカルではOIDC検証なし）
- `line-test-message` は `RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN` と `RUN_COACH_LINE_USER_ID` 環境変数が必要
