# AIハーネスの調査・設計記録

## Confirmed

- 顧客別納入分析、集計・年次予測・グラフ・Excel 出力を行う既存 Python アプリ。構成と根拠は ARCHITECTURE.md。
- 現行接続は PostgreSQL のみ。Access ソース・依存・専用ファイル・切替設定は現行ツリーにない。旧DB関連削除は既存 update.md に記録。
- 外部指標は公開サイトから取得し SQLite に保存。Excel も更新対象。PostgreSQL の業務データ更新処理は確認されない。
- 調査時点では tests とプロジェクト Skills / Rules は未整備。pyright 設定のみ存在し CLI は未導入。
- README、.env.example、docs/update.md、DESIGN.md が存在。CHANGELOG はなく update.md が変更履歴。
- 既存 exe は 54,717,412 バイト。PYZ / CArchive 内に Access 依存は見つからない。

## Assumption

- 実行される主要運用フローは README 記載機能と考えられるが、利用頻度・正式な受入手順は未確認。
- 旧DB削除記録は Access 復帰時の再利用コードが別履歴や別資産にある可能性を示すが、その所在は確認できない。

## Unknown / 矛盾

- 実 DB の完全な DDL・権限、配布先 PC の WebView2 / .NET、業務受入基準、正式リリース手順。現在設定された環境の接続と主要3テーブルの列参照は検証済み。
- 既存 AGENTS の src/ またはルートという一般構成と、実装の app/ が異なる。既存構成は移動せず実態を地図に追加する。
- README は matplotlib をグラフ、予測も含めて説明するが予測計算は numpy。技術構成はコードで確認できる範囲に整理。
- 既存テストがないため既存 Tests との仕様矛盾は評価対象なし。予測の業務上の妥当性は推測で確定しない。

## 設計

| 要素 | 役割 |
|---|---|
| AGENTS.md | 既存規則を保持し、実際のコード・Docs・Skills・検証への地図を追加 |
| .cursor/rules/ | 既存規則と機密・本番操作の常時制約への参照 |
| .agents/skills/development-workflow | 通常開発・不具合修正の経路、共通更新検証・学びの提案 |
| .agents/skills/review-code | 要求と実装・Tests・Docs の整合評価 |
| .agents/skills/release | ビルド、同梱物、未検証条件の整理 |
| .agents/skills/code-simplifier | 仕様を維持する可読性・責務・重複レビュー |
| docs/ | 現在確認できた構成・仕様・データ・API・配布知識 |
| tests/ | オフライン回帰と配布検査条件の検証 |
| docs/update.md | 重要な変更履歴のみ |

機能追加と不具合修正は共通 workflow 内で分岐し、同じ手順の Skill 複製を避ける。
固有 Skill 候補は予測と外部指標更新。独立して繰り返す依頼実績が未確認のため現時点では追加せず、共通手順と関連 Docs を使う。
review-code は品質判断、release は配布可否、code-simplifier は仕様非変更の整理判断に限定する。参照 Docs と Tests は各 Skill に指定。
