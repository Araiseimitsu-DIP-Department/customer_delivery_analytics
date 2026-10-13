# 現在の構成

確認根拠は `app/`、`requirements.txt`、`build_exe.ps1`。Windows 用 Python / pywebview アプリ。

| 層 | ファイル | 役割 |
|---|---|---|
| 起動 | app/main.py | 画面起動、致命的起動エラーの標準エラー出力と Windows ダイアログ |
| 画面 API | app/webview_app.py | JS API、検索・予測・保存・グラフ生成、エラーログ |
| UI | app/web/ | HTML / CSS / JavaScript。UI フレームワークなし |
| 設定 | app/config/settings.py | 環境変数、.env、同梱リソースの解決 |
| DB | app/db/postgres_connector.py | psycopg 接続、スキーマ設定、辞書形式の取得 |
| 業務 | app/service/delivery_service.py | 検索条件、マスタ対応付け、集計 |
| 予測 | app/service/forecast_service.py | NumPy による回帰予測 |
| 外部指標 | app/service/external_indicator_service.py | IIP / CI の取得、キャッシュ、年次化 |
| 保存 | app/infrastructure/ | SQLite 指標保存、AppData パス |
| 出力 | app/service/export_service.py | openpyxl による Excel とグラフ出力 |
| 配布 | build_exe.ps1、scripts/verify_build.py | onefile exe 生成と同梱物検査 |

検索は UI → Python API → PostgreSQL → pandas 集計 → UI の順。
予測時は実績と取得できた外部指標を使用する。Excel はユーザー指定先に保存する。
GUI は `edgechromium` を指定。`pythonnet` / `clr_loader` / WebView2 DLL は GUI 依存であり、Access 専用ではない。
`sqlite3` は外部指標キャッシュ用であり配布から除外しない。

現行ツリーに Access コネクタ、切替設定、Access フォールバックは存在しない。
過去の旧DB対応削除は `docs/update.md` に記録されている。今回の最適化はアプリコードを削除・変更しない。
セットアップ・環境変数の一覧は README、DB は DATABASE、業務仕様は BUSINESS_RULES を参照。
