# 変更履歴

## 2026-06-23

- GUI 起動経路を旧GUIから pywebview に変更。
- `docs/DESIGN/DESIGN.md` のデザインガイドに合わせ、左サイドバー、カード、フォーム、テーブル、淡い青基調の Web UI を追加。
- pywebview 用の HTML / CSS / JavaScript と Python API を追加し、検索・年次予測・グラフ表示・Excel 出力を Web UI から利用できるように変更。
- 配布ビルド設定と README の依存関係・起動説明を pywebview 版に更新。
- 未使用になった旧GUI実装、旧 hook、旧 UI ユーティリティ、旧仮想環境、旧ビルド成果物を削除。
- basedpyright がプロジェクトの `.venv` を参照するよう `pyrightconfig.json` を追加。
- pywebview の native window を JS API に公開しないよう修正し、起動時の再帰エラーを解消。
- 起動時の候補データ同期読み込みを廃止し、入力欄フォーカス時に必要な候補を読み込む方式へ変更。
- サイドバーを削除し、DESIGN.md に基づくヘッダーロゴと標準 Footer 表示へ変更。
- DB 接続を PostgreSQL に変更し、旧DBコネクタ・旧DB依存・旧DB仕様書を削除。
- 納品実績の既定接続先を `arai_masters.deliveries`、製品・客先マスタの既定接続先を `order_management` に設定。
- `.env.example` を追加し、`.env` から PostgreSQL 接続 URL と `POSTGRES_SCHEMA` を読み込めるように変更。
- 現在の Python / pywebview / PostgreSQL 構成に合わせて `.gitignore` を更新。
- 顧客・品番候補を入力欄フォーカス時に自動読み込みするプルダウン UI へ変更し、候補読込ボタンを削除。
- 納品実績テーブルが接続先に存在しない場合、利用可能な PostgreSQL 接続から `deliveries` を自動選択するよう修正。
- 起動時のユーザー不要メッセージを非表示化し、最大化起動・一画面レイアウト・テーブル内スクロールへ調整。
- グラフ生成時の日本語フォントを Windows 環境向けに調整し、文字化けを抑制。
- 外部指標取得の待ち時間を短縮し、ネットワーク不通時でも予測処理が長時間停止しないよう調整。
- 予測メモの表示文言をユーザー向けに簡略化し、表示欄をコンパクト化。
- 品番集計時の予測 Excel 保存名から不要な `全顧客_` を除外。
- CI の参照先 Excel を最新ページから自動解決する方式に変更し、古い固定 URL による 404 を解消。
- IIP / CI のうち取得できた外部指標だけでも外部要因回帰を行うよう変更し、外部指標不足時の代用処理を削減。
- 新しい PNG から Windows 用 `docs/icon.ico` を再生成し、アプリ / exe 用アイコンを差し替え。
- onefile ビルド時に `.env` を同梱し、exe 単体で PostgreSQL 接続設定を読めるように変更。
