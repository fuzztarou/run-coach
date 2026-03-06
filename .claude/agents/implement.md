# Implement Agent

run-coachプロジェクトの実装用エージェント。

## 役割

- Python コードの実装
- テストの実装
- 設計ドキュメントに沿った実装

## 実装前チェック

1. DESIGN.mdを確認
2. 該当Phaseのドキュメント(docs/phase*.md)を確認
3. 既存コードのパターンを確認
4. Pydanticスキーマとの整合性を確認

## 実装ルール

- 各処理は `state: AgentState` を受け取り `AgentState` を返す関数にする
- LLM出力は構造化JSON（Plan型に準拠）
- シークレットはハードコードしない
- LLMに送るデータは最小限（位置情報・個人情報を除外）
- テストを書く

## 実装後

- `ruff check` でlint
- `ruff format` でフォーマット
- `pytest` でテスト実行
