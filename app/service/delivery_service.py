# -*- coding: utf-8 -*-
"""納入実績の取得・集計（PostgreSQL から必要範囲のみ取得する）。"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

import pandas as pd

from app.db import postgres_connector


class AggregateMode(str, Enum):
    """一覧の集計単位。"""

    BY_CUSTOMER = "顧客別"
    BY_PRODUCT = "品番別"
    BY_CUSTOMER_PRODUCT = "顧客×品番別"


# 一覧表示カラム（仕様）
LIST_COLUMNS = ["顧客", "品番", "年", "月", "納品数", "金額"]


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _product_customer_map(conn) -> dict[str, str]:
    sql = """
    SELECT DISTINCT
        NULLIF(BTRIM(product_no), '') AS product_no,
        NULLIF(BTRIM(customer_name), '') AS customer_name
    FROM product_master
    WHERE product_no IS NOT NULL
      AND BTRIM(product_no) <> ''
    """
    rows = postgres_connector.fetch_all_dicts(conn, sql)
    return {
        _normalize_text(row.get("product_no")): _normalize_text(row.get("customer_name"))
        for row in rows
        if _normalize_text(row.get("product_no"))
    }


def _product_numbers_for_customer(conn, customer: str) -> list[str]:
    sql = """
    SELECT DISTINCT NULLIF(BTRIM(product_no), '') AS product_no
    FROM product_master
    WHERE product_no IS NOT NULL
      AND BTRIM(product_no) <> ''
      AND BTRIM(customer_name) = %s
    ORDER BY NULLIF(BTRIM(product_no), '')
    """
    rows = postgres_connector.fetch_all_dicts(conn, sql, [customer])
    return [_normalize_text(row.get("product_no")) for row in rows if _normalize_text(row.get("product_no"))]


def fetch_customer_names(conns: postgres_connector.PostgresConnections) -> List[str]:
    """製品マスタに現れる顧客名の一覧を DISTINCT で取得する。"""
    sql = """
    SELECT DISTINCT NULLIF(BTRIM(customer_name), '') AS customer_name
    FROM product_master
    WHERE customer_name IS NOT NULL AND BTRIM(customer_name) <> ''
    ORDER BY NULLIF(BTRIM(customer_name), '')
    """
    rows = postgres_connector.fetch_all_dicts(conns.masters, sql)
    return [_normalize_text(row.get("customer_name")) for row in rows if _normalize_text(row.get("customer_name"))]


def fetch_customer_code_name_pairs(conns: postgres_connector.PostgresConnections) -> list[tuple[str, str]]:
    """客先マスタから顧客コードと客先名の一覧を取得する。"""
    sql = """
    SELECT
        customer_code,
        customer_name
    FROM (
        SELECT
            NULLIF(BTRIM(code), '') AS customer_code,
            NULLIF(BTRIM(customer), '') AS customer_name,
            CASE WHEN BTRIM(code) ~ '^[0-9]+$' THEN BTRIM(code)::integer END AS customer_code_number
        FROM customer_master
        WHERE code IS NOT NULL
          AND customer IS NOT NULL
          AND BTRIM(code) <> ''
          AND BTRIM(customer) <> ''
    ) AS cleaned
    GROUP BY customer_code, customer_name
    ORDER BY
        MIN(customer_code_number) NULLS LAST,
        customer_code,
        customer_name
    """
    rows = postgres_connector.fetch_all_dicts(conns.masters, sql)
    return [
        (_normalize_text(row.get("customer_code")), _normalize_text(row.get("customer_name")))
        for row in rows
        if _normalize_text(row.get("customer_code")) and _normalize_text(row.get("customer_name"))
    ]


def fetch_distinct_hinban(conns: postgres_connector.PostgresConnections) -> List[str]:
    """納品テーブルに現れる品番の一覧（候補プルダウン用・重複除去）。"""
    sql = """
    SELECT DISTINCT NULLIF(BTRIM(product_no), '') AS product_no
    FROM deliveries
    WHERE product_no IS NOT NULL AND BTRIM(product_no) <> ''
    ORDER BY NULLIF(BTRIM(product_no), '')
    """
    rows = postgres_connector.fetch_all_dicts(conns.deliveries, sql)
    return [_normalize_text(row.get("product_no")) for row in rows if _normalize_text(row.get("product_no"))]


def fetch_distinct_hinban_for_customer(conns: postgres_connector.PostgresConnections, customer: str) -> List[str]:
    """
    指定顧客に紐づく品番のみ（納品×製品マスタの結合は fetch_deliveries と同じ考え方）。
    顧客名は製品マスタの客先名と完全一致（Trim 済み文字列）で比較する。
    """
    cust = (customer or "").strip()
    if not cust or cust == "（すべて）":
        return fetch_distinct_hinban(conns)
    return _product_numbers_for_customer(conns.masters, cust)


def fetch_deliveries(
    conns: postgres_connector.PostgresConnections,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    customer: Optional[str] = None,
    product_code_filter: Optional[str] = None,
) -> pd.DataFrame:
    """納入明細を取得。品番は部分一致（ILIKE）。"""
    if (date_from is None) ^ (date_to is None):
        raise ValueError("納入日の期間指定は開始日と終了日の両方が必要です。")

    cust = (customer or "").strip()
    has_customer = bool(cust and cust != "（すべて）")
    params: list = []
    where = ["1=1"]

    if date_from is not None and date_to is not None:
        where.append("d.delivery_date::date BETWEEN %s AND %s")
        params.extend([date_from, date_to])

    product_numbers: list[str] = []
    if has_customer:
        product_numbers = _product_numbers_for_customer(conns.masters, cust)
        if not product_numbers:
            return pd.DataFrame(columns=["納入日", "顧客", "品番", "納品数", "金額"])
        where.append("BTRIM(d.product_no) = ANY(%s)")
        params.append(product_numbers)

    prod = (product_code_filter or "").strip()
    if prod:
        where.append("BTRIM(d.product_no) ILIKE %s")
        params.append(f"%{prod}%")

    sql = f"""
    SELECT
        d.delivery_date AS 納入日,
        NULLIF(BTRIM(d.product_no), '') AS 品番,
        d.delivery_qty AS 納品数,
        d.amount AS 金額
    FROM deliveries AS d
    WHERE {' AND '.join(where)}
    ORDER BY d.delivery_date, NULLIF(BTRIM(d.product_no), '')
    """
    rows = postgres_connector.fetch_all_dicts(conns.deliveries, sql, params)
    if not rows:
        return pd.DataFrame(columns=["納入日", "顧客", "品番", "納品数", "金額"])

    df = pd.DataFrame(rows)
    # 型整備
    if "納入日" in df.columns:
        df["納入日"] = pd.to_datetime(df["納入日"], errors="coerce")
    for col in ("納品数", "金額"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["品番"] = df["品番"].fillna("").astype(str)
    product_map = _product_customer_map(conns.masters)
    df.insert(1, "顧客", df["品番"].map(product_map).fillna("（未設定）").astype(str))
    return df[["納入日", "顧客", "品番", "納品数", "金額"]]


def aggregate_for_list(df: pd.DataFrame, mode: AggregateMode) -> pd.DataFrame:
    """
    明細 DataFrame を一覧用に集計する。
    出力列: 顧客, 品番, 年, 月, 納品数, 金額
    """
    if df.empty:
        return pd.DataFrame(columns=LIST_COLUMNS)

    work = df.copy()
    work["年"] = work["納入日"].dt.year.astype(int)
    work["月"] = work["納入日"].dt.month.astype(int)

    if mode == AggregateMode.BY_CUSTOMER:
        g = work.groupby(["顧客", "年", "月"], as_index=False, sort=True).agg(
            納品数=("納品数", "sum"),
            金額=("金額", "sum"),
        )
        g.insert(1, "品番", "*")
    elif mode == AggregateMode.BY_PRODUCT:
        g = work.groupby(["品番", "年", "月"], as_index=False, sort=True).agg(
            納品数=("納品数", "sum"),
            金額=("金額", "sum"),
        )
        # 品番を先頭列付近にそろえるため顧客列を後付け
        g.insert(0, "顧客", "*")
    else:  # BY_CUSTOMER_PRODUCT
        g = work.groupby(["顧客", "品番", "年", "月"], as_index=False, sort=True).agg(
            納品数=("納品数", "sum"),
            金額=("金額", "sum"),
        )

    g = g.sort_values(by=["顧客", "品番", "年", "月"]).reset_index(drop=True)
    # 整数表示用
    g["年"] = g["年"].astype(int)
    g["月"] = g["月"].astype(int)
    return g[LIST_COLUMNS]


def yearly_totals_from_raw_deliveries(df: pd.DataFrame) -> pd.DataFrame:
    """
    検索で取得した明細 DataFrame から年次合計を作る（予測・年別グラフの入力用）。
    列: 年, 納品数, 金額。必須列が無い・空なら空の枠を返す。
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["年", "納品数", "金額"])
    needed = {"納入日", "納品数", "金額"}
    if not needed.issubset(df.columns):
        return pd.DataFrame(columns=["年", "納品数", "金額"])
    work = df.copy()
    work["年"] = work["納入日"].dt.year.astype(int)
    y = work.groupby("年", as_index=False, sort=True).agg(
        納品数=("納品数", "sum"),
        金額=("金額", "sum"),
    )
    y["年"] = y["年"].astype(int)
    return y.sort_values("年").reset_index(drop=True)


def monthly_totals_from_raw_deliveries(df: pd.DataFrame) -> pd.DataFrame:
    """
    検索で取得した明細 DataFrame から月次合計を作る。
    列: 年月, 納品数, 金額。年月は YYYY-MM 文字列。
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["年月", "納品数", "金額"])
    needed = {"納入日", "納品数", "金額"}
    if not needed.issubset(df.columns):
        return pd.DataFrame(columns=["年月", "納品数", "金額"])
    work = df.copy()
    work["年月"] = work["納入日"].dt.strftime("%Y-%m")
    m = work.groupby("年月", as_index=False, sort=True).agg(
        納品数=("納品数", "sum"),
        金額=("金額", "sum"),
    )
    return m.sort_values("年月").reset_index(drop=True)


def yearly_totals_for_customer(
    conns: postgres_connector.PostgresConnections,
    customer: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    product_code_filter: Optional[str] = None,
) -> pd.DataFrame:
    """指定顧客の年次集計（予測・グラフ用）。列: 年, 納品数, 金額。日付省略時は全期間。"""
    df = fetch_deliveries(conns, date_from, date_to, customer, product_code_filter)
    y = yearly_totals_from_raw_deliveries(df)
    if y.empty:
        return pd.DataFrame(columns=["年", "納品数", "金額", "種別"])
    y["種別"] = "実績"
    return y.sort_values("年").reset_index(drop=True)
