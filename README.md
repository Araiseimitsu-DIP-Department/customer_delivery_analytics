# 顧客別納入分析システム

PostgreSQL の納入実績を参照し、検索・集計・年次予測・グラフ表示・Excel 出力までをまとめて扱う Windows 業務アプリです。  
現在の GUI 実装は `pywebview` 版です。HTML/CSS の画面をデスクトップアプリとして表示します。

## 主な機能

- 期間・顧客・品番・集計単位による納入実績検索
- 年別・月別推移グラフの表示
- 年次予測の算出
- 予測算出詳細の説明表示
- 一覧および予測結果の Excel 出力
- PostgreSQL の納入実績とマスタを使った予測補助
- IIP / CI など取得できた外部指標を使った外部要因予測

## 技術スタック

- Python 3.10 以上
- GUI: `pywebview`
- DB 接続: `psycopg`
- 集計・予測: `pandas` / `numpy`
- グラフ: `matplotlib`
- Excel 出力: `openpyxl`
- UI: HTML / vanilla CSS / JavaScript
- 配布: `PyInstaller`

## 起動方法

```powershell
cd <リポジトリのルート>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# .env の PostgreSQL URL を実環境に合わせて編集
python -m app.main
```

補足:
- `app/main.py` が起動点です。
- `app/webview_app.py` に pywebview 版の画面 API、`app/web/` に HTML/CSS/JavaScript があります。
- PostgreSQL 接続先は `.env` または環境変数で設定します。

## 配布用 exe の作成

```powershell
pip install pyinstaller
.\build_exe.ps1
```

既定は `onefile` 配布です。生成されるのは単体の `.exe` です。
ビルド時に `.env` が存在する場合は exe に同梱されます。exe と同じフォルダに `.env` を置いた場合は、同梱値より優先して読み込まれます。

## フォルダ構成

```text
customer_delivery_analytics/
├─ app/
│  ├─ main.py
│  ├─ webview_app.py
│  ├─ web/
│  ├─ config/
│  ├─ db/
│  ├─ infrastructure/
│  └─ service/
├─ docs/
├─ requirements.txt
├─ build_exe.ps1
├─ README.md
└─ .gitignore
```

## 配布先 PC で必要なもの

- PostgreSQL サーバーへ到達できるネットワーク権限
- `.env` または PostgreSQL 接続 URL 環境変数
- 外部指標を更新する場合はインターネット接続。取得できない指標がある場合は、取得済み指標だけで外部要因予測します。

## 必要な環境変数

`.env.example` を `.env` にコピーし、接続先 URL を実環境に合わせて編集してください。`.env` は Git 管理対象外です。

| 変数 | 用途 |
|---|---|
| `POSTGRES_SCHEMA` | PostgreSQL の参照スキーマ。未指定時は `public` |
| `POSTGRES_ARAI_MASTERS_URL` | 納品実績 DB の標準接続 URL。`arai_masters.deliveries` を参照 |
| `POSTGRES_ORDER_MANAGEMENT_DB_URL` | マスタ DB の標準接続 URL。`order_management.product_master` / `order_management.customer_master` を参照 |
| `CDA_POSTGRES_PASSWORD` | 個別指定で接続 URL を組み立てる場合の PostgreSQL パスワード |
| `CDA_POSTGRES_HOST` | PostgreSQL ホスト。未指定時は `192.168.1.120` |
| `CDA_POSTGRES_PORT` | PostgreSQL ポート。未指定時は `5432` |
| `CDA_POSTGRES_USER` | PostgreSQL ユーザー。未指定時は `postgres` |
| `CDA_DELIVERIES_DATABASE` | 納品実績 DB。未指定時は `arai_masters` |
| `CDA_MASTERS_DATABASE` | 製品・客先マスタ DB。未指定時は `order_management` |
| `CDA_DELIVERIES_DATABASE_URL` | 納品実績 DB の接続 URL。指定時は `POSTGRES_ARAI_MASTERS_URL` より優先 |
| `CDA_MASTERS_DATABASE_URL` | 製品・客先マスタ DB の接続 URL。指定時は `POSTGRES_ORDER_MANAGEMENT_DB_URL` より優先 |

## トラブルシュート

| 現象 | 確認事項 |
|---|---|
| PostgreSQL に接続できない | 接続 URL、`CDA_POSTGRES_PASSWORD`、サーバー到達性、DB 名を確認 |
| 外部要因予測が一部指標のみになる | IIP / CI の公開元サイトへのネットワーク到達性、プロキシ、ファイアウォールを確認 |
| 画面の表示が崩れる | `pip install -r requirements.txt` の再実行、`pywebview` / `matplotlib` の導入確認 |
| exe が起動しない | `.\build_exe.ps1` を再実行して再ビルド |

## ライセンス

利用ライブラリは各パッケージのライセンスに従います。社内配布ルールやデータ取り扱いルールもあわせて確認してください。
