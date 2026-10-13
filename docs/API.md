# 画面 API と外部サービス

`WebviewApi` は pywebview の JS API。公開 HTTP サーバー API を運用する構成ではない。
主要操作は bootstrap、load_master_choices、get_products、search、forecast、export_actual、export_forecast、chart、forecast_details。
操作結果は辞書で返し、失敗は ok=false とメッセージを返す。画面 API の例外は LOGGER.exception で記録する。
native window は `_set_window` で保持し、公開 JS API に直接渡さない。

外部指標の参照先はコードの IIP_SOURCE_URL（経済産業省 Excel）と CI_PAGE_URL（内閣府ページ）。
CI はページの Excel リンクを解決し、解決できなければ CI_SOURCE_URL を使う。
urllib.request のダウンロードタイムアウトは 20 秒。自動認証情報は設定しない。
当月取得成功済みで指標値がある場合はキャッシュを利用。取得失敗時は既存キャッシュを使用し、なければ missing。
状態・日時・失敗理由は SQLite に保存する。外部ダウンロード内容やネットワーク経路は今回未検証。
