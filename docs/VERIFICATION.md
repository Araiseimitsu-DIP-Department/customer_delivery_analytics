# 今回の検証結果（2026-10-13）

## 検証範囲

アプリケーション本体の変更なし。変更対象はビルド、検査・テスト、AIハーネスと関連ドキュメント。
code-simplifier と review-code を適用し、除外方針の単一管理、責務、重複、仕様非変更、Docs と Tests の整合を確認。

| 項目 | 結果・限界 |
|---|---|
| Tests | unittest の全回帰テスト PASS。最初の一時ファイル権限エラーは制限外で再実行して解消 |
| 構文 | compileall と PowerShell Parser PASS |
| Skills | 4 Skills の quick_validate PASS。参照2ファイルは指定 templates から配置 |
| 起動関連 | Access import を拒否した別プロセスで app.main / app.webview_app の import PASS。初期 JS API は DB 接続なしで PASS |
| PostgreSQL | 設定済み接続の読取専用検証 PASS。deliveries / product_master / customer_master の必要列を LIMIT 1 で参照。データ値は非表示 |
| 主要処理 | 固定データの集計・直線回帰・Excel 読み戻し、SQLite upsert の更新・再実行 PASS |
| Build | Windows x64 / Python 3.12.10 / PyInstaller 6.21.0 の onefile 再ビルド PASS |
| 同梱物 | 新旧 exe の CArchive / PYZ 検査 PASS。Access 依存なし、必要な PostgreSQL / GUI / SQLite / Web 素材あり |
| lint / 型チェック | NOT RUN。CLI 未導入。pyright 設定のみ存在 |
| GUI 受入・外部指標 | 配布先 PC の画面操作、実 DB の検索結果の業務確認、外部指標の最新ダウンロード、外部要因予測・グラフ・予測 Excel 全体は未検証 |

## 成果物比較

旧: `dist/顧客別納入分析システム.exe`、54,717,412 バイト。
新: `dist/postgres/顧客別納入分析システム.exe`、55,774,238 バイト。
差分: +1,056,826 バイト（約 +1.93%）。旧 exe にも Access がなく、Access 除外による削減は確認できない。
Python モジュール一覧は同一。新 exe では Windows api-ms-* / ucrtbase.dll の追加が確認された。互換性への影響を推測して削除しない。
旧ビルド実行時の OS / ランタイム条件は未確認のため、今回の設定だけのサイズ効果と断定しない。

## 残る確認

本番データの更新・削除・移行・配布は行っていない。
配布先 Windows での起動と主要操作の受入確認後に正式配布を判断する。
Access 復帰用ソースの所在は Unknown。現行ツリーには対応ソースがないため今回削除していない。復帰には過去資産の調査と配布プロファイルの再検討が必要。
通常のデータ更新検証手順はハーネスへ組み込んだ。今回のアプリ更新経路変更は適用外。SQLite / Excel はテスト用データの読み戻しのみ実施し、本番データの途中停止・再実行は行わない。
