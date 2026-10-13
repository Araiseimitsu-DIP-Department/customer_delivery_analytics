---
name: development-workflow
description: このプロジェクトの機能追加、既存機能変更、不具合修正を調査から検証まで進める。
---

# 開発手順

AGENTS.md、関連 Rules と Docs を読む。入口は docs/ARCHITECTURE.md、業務処理は BUSINESS_RULES.md、データ接続は DATABASE.md、画面・外部指標は API.md。
要求と現行仕様との差分を Confirmed / Assumption / Unknown に分け、不明な業務仕様を勝手に実装しない。
不具合は再現条件・ログ・実装から原因を特定し、最小修正と発生経路の回帰テストを作る。機能追加は入出力と既存処理への影響を確認して最小実装する。
DB・Excel 等の更新を変更するときだけ [データ更新検証](references/data-update-verification.md) を読む。SQLite は外部指標用であり削除対象ではない。
tests/test_postgres.py、test_core.py、test_build.py の関連ケースを実行する。30行以上の変更または新規モジュールでは code-simplifier を使い、review-code と docs/RELEASE.md の Verification Gate で確認する。
Docs 更新要否を判断し、重要な変更は docs/update.md に記録。完了時は変更ファイル、検証結果と未実施理由、残る確認事項を日本語で報告する。
再利用できる学びは [学びの提案・承認・反映](references/learning-feedback.md) に従う。今回の開発許可を templates 更新や本番操作の許可と扱わない。
