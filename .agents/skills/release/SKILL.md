---
name: release
description: Windows用PostgreSQL配布のビルド、同梱物、動作検証と未確認事項を整理する。本番配布は実行許可を別途確認する。
---

# 配布準備

docs/RELEASE.md、README、.env.example、docs/update.md を確認する。
tests/test_build.py と関連回帰を実行し、build_exe.ps1 で既存成果物を残す出力先にビルドする。
Access 専用依存と共通依存の用途を実装・フックから調査する。除外一覧は scripts/verify_build.py にあり、アプリの Access ソース削除を伴わせない。
生成 exe の自動検査結果と前後サイズを確認する。postgres バイナリ、GUI DLL、SQLite、画面素材不足を見逃さない。
実 PostgreSQL 検索、予測、グラフ、Excel、配布先 Windows の起動を可能な範囲で確認し、環境不足なら未検証と明示する。
データ更新に関係する場合だけ ../development-workflow/references/data-update-verification.md を適用する。
git diff / status と Docs の整合を確認する。本番配布直前に RELEASE.md の Approval Gate を適用する。
