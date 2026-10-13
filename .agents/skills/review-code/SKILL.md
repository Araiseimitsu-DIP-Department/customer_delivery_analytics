---
name: review-code
description: このプロジェクトの実装変更を、既存仕様への影響、回帰、Docsとテストの整合からレビューする。
---

# 実装レビュー

要求、git diff、関連 Docs、実装、関連 Tests を照合する。DB は docs/DATABASE.md、業務は BUSINESS_RULES.md、配布は RELEASE.md を参照。
入力・空値・日付・境界値・例外・接続終了・データ型・依存用途を確認し、変更していない業務フローへ影響がないか調べる。
データ更新変更時だけ ../development-workflow/references/data-update-verification.md の読み戻し・再実行・途中停止を確認する。
指摘は根拠となるファイル・条件と Critical / High / Medium / Low の重大度を示す。未検証を PASS としない。Critical / High が残る場合はリリース可能と判断しない。
検証不足を実装不具合と区別し、不要なリファクタリングや仕様変更を提案しない。
再利用できる確認漏れは ../development-workflow/references/learning-feedback.md に従って具体案を提案する。
