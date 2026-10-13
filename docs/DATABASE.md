# データアクセス

## PostgreSQL（現行コードから確認）

- 納品実績接続とマスタ接続を別々に解決。環境変数の一覧は README.md。
- `CDA_*_DATABASE_URL` → 標準 `POSTGRES_*_URL` → 個別設定から URL 組み立ての優先順。
- 個別設定のパスワード未指定は例外。Access 接続への代替処理はない。
- 接続タイムアウトは設定定数の 8 秒。スキーマは既定 `public`、SQL Identifier で search_path に設定。
- 両 URL が同じなら接続を共有する。
- 異なる URL では、納品実績接続に `deliveries` がなく、マスタ接続に存在するとき、納品取得もマスタ接続を使用する。これは PostgreSQL 内の選択。
- 接続終了時は close。検索値はパラメータで渡す。

| テーブル | コードで参照するカラム |
|---|---|
| deliveries | delivery_date、product_no、delivery_qty、amount |
| product_master | product_no、customer_name |
| customer_master | code、customer |

アプリから PostgreSQL へは参照 SQL とセッションの search_path 設定のみ確認された。
設定済み環境で接続と主要3テーブルの列参照を読み取り専用で確認済み。完全な DDL、制約、実データ品質、権限一覧は未確認。ここに記載した列は完全な DB 定義ではない。

## SQLite

`LOCALAPPDATA/<アプリ表示名>/external_indicators.db`。LOCALAPPDATA 未指定ならホーム配下 `.customer_delivery_analytics`。
`IndicatorStore` が次を初期作成し、接続単位で commit / close する。

| テーブル | キー・用途 |
|---|---|
| indicator_master | indicator_code 主キー、指標名称・公開元 |
| indicator_monthly | indicator_code と year_month の複合主キー、指標値 |
| indicator_fetch_status | indicator_code 主キー、取得成否と日時 |

指標値は INSERT ON CONFLICT UPDATE。メソッド名 replace は全件削除を意味しない。空入力は書き込まない。
指標値更新と取得状態更新は別接続・別 commit。途中停止時の両者一括原子性は保証されていない。
DB・Excel 更新変更時は development-workflow の共通データ更新検証を適用する。
