# ビルド構成と検証

セットアップ・起動方法・環境変数は README.md を参照。
既存方式は Windows / PyInstaller / windowed / onefile。生成 .spec は build 配下の作業ファイル。
build_exe.ps1 は同じ Python 環境でビルドと検査を行い、失敗時に成功メッセージを出さない。
作業ディレクトリは毎回 build/run-<識別子>。build/dist の一括削除は行わない。同じ出力先の同名 exe は上書きされる。

## 同梱方針

- scripts/verify_build.py の ACCESS_MODULES を除外一覧の単一管理箇所とする。
- pyodbc / pypyodbc は ODBC 用、win32com は COM 用の汎用ライブラリだが、現行アプリと導入済みランタイムで利用箇所がないため PostgreSQL 配布では除外する。将来共通機能が使用する場合は再調査する。
- psycopg / psycopg_binary と libpq、pandas / numpy / matplotlib / openpyxl、pywebview / pythonnet / clr_loader、SQLite は保持。
- 既存除外の scipy / sklearn / pytest / pyarrow は維持。
- add-data は画面フォルダ、アイコン、ロゴ、および存在する .env のみ。Access 専用設定・ドライバー・DB ファイルは現行ツリーに存在しない。
- exe の CArchive と PYZ 内のモジュールを検査し、Access モジュール・DB 拡張子・既知ドライバーの混入、主要ランタイム・画面素材不足をエラーにする。
- この検査は全未知ドライバーの用途を自動判定するものではない。将来の同梱物追加時には用途調査が必要。
- .env 同梱と外部 .env 優先は既存仕様を維持。配布前に同梱する接続情報の対象を確認し、実値をログ・Docs に書かない。

## Verification Gate

1. `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
2. `.\.venv\Scripts\python.exe -m compileall -q app scripts tests`
3. ビルド変更時は `.\build_exe.ps1 -OutputDirectory dist\postgres`。標準出力先は dist。
4. 再検査は `.\.venv\Scripts\python.exe scripts\verify_build.py <exeパス>`。
5. `git diff --check`、`git diff`、`git status --short`。Docs・テストの整合と意図しない変更を確認。
6. 検証ごとに PASS / FAIL / NOT RUN と理由を記録。実 DB、配布 PC の GUI と主要操作は自動テストとは別に確認。

接続済み環境の読取検証は `.\.venv\Scripts\python.exe -m scripts.check_postgres`。
設定済み接続先を使用し、読取専用トランザクションで主要3テーブルを LIMIT 1 で参照する。共有接続は一度だけ設定し、値は表示しない。SQL タイムアウトは10秒。

lint コマンドは未導入。pyrightconfig.json は存在するが型チェック CLI は現行 .venv に未導入。
ビルド検査 PASS は実 DB 接続や GUI 動作を保証しない。未検証の重要条件があれば無条件に Release Ready と判定しない。

## Approval Gate

本番 DB の削除・初期化・大量更新・移行、本番設定・認証情報変更、本番配布、外部送信は、対象と件数・影響・復旧方法を具体化し、既存のユーザー許可を確認する。未許可なら操作直前に承認を得る。
テストはモック・一時 SQLite・一時 Excel を使い、本番データを変更しない。
正式リリース・署名・ロールバック運用は Unknown。旧成果物を比較用に保持することは正式な復旧手順の確認ではない。
