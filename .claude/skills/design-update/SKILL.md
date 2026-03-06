# 設計ドキュメント更新

DESIGN.mdおよびdocs/phase*.mdの設計ドキュメントを更新するスキル。

## トリガー

ユーザーが設計の変更・追記を依頼した時。

## 手順

1. DESIGN.mdを読んで現状の設計を確認
2. 該当するPhaseドキュメント(docs/phase*.md)を確認
3. 変更内容を反映
4. 関連する他のファイルとの整合性を確認

## ファイル構成

```
DESIGN.md                      # 全体設計（データソース、アーキテクチャ、スキーマ等）
docs/phase1-mvp.md             # Phase 1: 最小MVP
docs/phase1.5-datasources.md   # Phase 1.5: データソース追加 + ガードレール
docs/phase2-data-logging.md    # Phase 2: データ蓄積 + ログ
docs/phase3-rag.md             # Phase 3: RAG導入
docs/phase4-langgraph.md       # Phase 4: LangGraph書き換え
docs/phase5-production.md      # Phase 5: 本番化 + 拡張
```

## 注意

- Mermaid図を更新する場合はGitHubでレンダリングされることを考慮
- Stateスキーマの変更はDESIGN.mdと各Phaseドキュメントの両方を更新
- プロジェクト名は「run-coach」
