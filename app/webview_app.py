# -*- coding: utf-8 -*-
"""pywebview implementation for the customer delivery analytics app."""

from __future__ import annotations

import base64
import io
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = [
    "Meiryo",
    "Yu Gothic",
    "MS Gothic",
    "sans-serif",
]
matplotlib.rcParams["axes.unicode_minus"] = False

import pandas as pd
import webview
from matplotlib.figure import Figure
from matplotlib.ticker import StrMethodFormatter

from app.config import settings
from app.db import postgres_connector
from app.service import delivery_service, export_service, external_indicator_service, forecast_service

LOGGER = logging.getLogger(__name__)
ALL_LABEL = "（すべて）"
AGGREGATE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("顧客別", delivery_service.AggregateMode.BY_CUSTOMER.name),
    ("品番別", delivery_service.AggregateMode.BY_PRODUCT.name),
    ("顧客別 + 品番別", delivery_service.AggregateMode.BY_CUSTOMER_PRODUCT.name),
)


def _web_dir() -> Path:
    return settings.resource_path("app", "web")


def _parse_date(text: str) -> Optional[date]:
    raw = (text or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"日付の形式が正しくありません: {raw}")


def _default_date_range() -> tuple[date, date]:
    start = date(settings.DEFAULT_YEAR_START, 1, 1)
    today = date.today()
    end = date(today.year - 1, 12, 31)
    return start, end


def _safe_records(df: Optional[pd.DataFrame]) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    clean = df.copy().where(pd.notna(df), None)
    return json.loads(clean.to_json(orient="records", force_ascii=False, date_format="iso"))


def _dataframe_payload(df: Optional[pd.DataFrame]) -> dict[str, Any]:
    return {
        "columns": [] if df is None else [str(col) for col in df.columns],
        "rows": _safe_records(df),
        "rowCount": 0 if df is None else int(len(df.index)),
    }


def _ensure_xlsx(path: str) -> str:
    return path if path.lower().endswith(".xlsx") else f"{path}.xlsx"


def _sanitize_filename_part(text: str) -> str:
    trans = str.maketrans({
        "\\": "￥",
        "/": "／",
        ":": "：",
        "*": "＊",
        "?": "？",
        '"': "”",
        "<": "＜",
        ">": "＞",
        "|": "｜",
    })
    return (text or "").strip().translate(trans)


def _logo_data_uri() -> str:
    logo_path = settings.resource_path("docs", "DESIGN", "arai_logo.png")
    if not logo_path.exists():
        return ""
    data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


class WebviewApi:
    """JavaScript から呼ばれるアプリ操作 API。"""

    def __init__(self) -> None:
        self._window: Any = None
        self._customer_display_to_name: dict[str, str] = {}
        self._customer_code_to_name: dict[str, str] = {}
        self._customer_name_to_display: dict[str, str] = {}
        self._all_hinbans: list[str] = []
        self._last_raw_df: Optional[pd.DataFrame] = None
        self._last_result_df: Optional[pd.DataFrame] = None
        self._last_forecast_comparison: Optional[pd.DataFrame] = None
        self._last_forecast_chart: Optional[pd.DataFrame] = None
        self._last_forecast_summary_lines: list[str] = []
        self._last_forecast_graph_note = ""
        self._last_search_meta: dict[str, str] = {}

    def _set_window(self, window: Any) -> None:
        self._window = window

    def bootstrap(self) -> dict[str, Any]:
        try:
            start, end = _default_date_range()
            return {
                "ok": True,
                "appName": settings.APP_DISPLAY_NAME,
                "databaseSummary": settings.database_summary(),
                "aggregateOptions": [
                    {"label": label, "value": value} for label, value in AGGREGATE_OPTIONS
                ],
                "customers": [],
                "products": [],
                "defaults": {
                    "dateFrom": start.isoformat(),
                    "dateTo": end.isoformat(),
                    "aggregateMode": delivery_service.AggregateMode.BY_CUSTOMER.name,
                },
                "logoDataUri": _logo_data_uri(),
            }
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("初期データの読み込みに失敗しました")
            return self._error("初期データの読み込みに失敗しました。", exc)

    def load_master_choices(self) -> dict[str, Any]:
        try:
            customer_items, hinbans = self._load_master_choices()
            return {
                "ok": True,
                "customers": customer_items,
                "products": hinbans,
                "status": (
                    f"顧客件数: {len(customer_items):,} 件 / "
                    f"品番候補: {len(hinbans):,} 件を読み込みました。"
                ),
            }
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("候補データの読み込みに失敗しました")
            return self._error("候補データの読み込みに失敗しました。", exc)

    def get_products(self, customer: str) -> dict[str, Any]:
        try:
            customer_name = self._resolve_customer_name(customer)
            with postgres_connector.open_app_connections() as conns:
                products = delivery_service.fetch_distinct_hinban_for_customer(conns, customer_name or ALL_LABEL)
            return {"ok": True, "products": products}
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("品番候補の取得に失敗しました")
            return self._error("品番候補の取得に失敗しました。", exc)

    def search(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            mode = delivery_service.AggregateMode[str(params.get("aggregateMode") or "")]
            date_from = _parse_date(str(params.get("dateFrom") or ""))
            date_to = _parse_date(str(params.get("dateTo") or ""))
            if date_from and date_to and date_from > date_to:
                raise ValueError("開始日は終了日以前の日付を指定してください。")

            customer = self._resolve_customer_name(str(params.get("customer") or ""))
            product = str(params.get("product") or "").strip()
            if mode == delivery_service.AggregateMode.BY_PRODUCT:
                customer = None
            if mode == delivery_service.AggregateMode.BY_CUSTOMER:
                product = ""

            with postgres_connector.open_app_connections() as conns:
                raw = delivery_service.fetch_deliveries(conns, date_from, date_to, customer, product)
                result = delivery_service.aggregate_for_list(raw, mode)

            self._last_raw_df = raw
            self._last_result_df = result
            self._last_forecast_comparison = None
            self._last_forecast_chart = None
            self._last_forecast_summary_lines = []
            self._last_forecast_graph_note = ""
            self._last_search_meta = {
                "customer": self._customer_display_label(str(params.get("customer") or "")),
                "product": product or "全品番",
                "period": self._period_label(date_from, date_to),
            }

            payload = _dataframe_payload(result)
            payload.update({
                "ok": True,
                "rawCount": int(len(raw.index)),
                "status": f"検索完了: 明細 {len(raw.index):,} 件 / 集計 {len(result.index):,} 件",
            })
            return payload
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("検索に失敗しました")
            return self._error("検索に失敗しました。", exc)

    def forecast(self, years: int) -> dict[str, Any]:
        try:
            raw = self._last_raw_df
            if raw is None or raw.empty:
                raise ValueError("先に検索を実行してください。")
            n_years = max(1, min(5, int(years)))
            yearly = delivery_service.yearly_totals_from_raw_deliveries(raw)
            if yearly.empty:
                raise ValueError("年次集計できる明細がありません。")

            indicator_service = external_indicator_service.ExternalIndicatorService()
            statuses = indicator_service.refresh_if_needed()
            status_summary = indicator_service.summarize_statuses(statuses)
            year_from = int(yearly["年"].min())
            year_to = int(yearly["年"].max()) + n_years
            indicator_yearly = indicator_service.build_yearly_indicator_frame(year_from, year_to)
            bundle = forecast_service.run_yearly_forecast_bundle(yearly, indicator_yearly, n_years)

            self._last_forecast_comparison = bundle.comparison_df
            self._last_forecast_chart = bundle.chart_df
            self._last_forecast_summary_lines = bundle.summary_lines
            self._last_forecast_graph_note = bundle.graph_note

            payload = _dataframe_payload(bundle.comparison_df)
            payload.update({
                "ok": True,
                "summaryLines": bundle.summary_lines,
                "status": f"予測完了: {status_summary}",
            })
            return payload
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("予測に失敗しました")
            return self._error("予測に失敗しました。", exc)

    def export_actual(self) -> dict[str, Any]:
        try:
            if self._last_result_df is None or self._last_result_df.empty:
                raise ValueError("出力する一覧がありません。先に検索してください。")
            path = self._choose_save_path(self._default_export_name(False))
            if not path:
                return {"ok": False, "cancelled": True}
            yearly = delivery_service.yearly_totals_from_raw_deliveries(self._last_raw_df)
            export_service.export_dataframe(
                _ensure_xlsx(path),
                self._last_result_df,
                sheet_name="一覧",
                table_name="顧客別納入分析システム / 実績一覧",
                yearly_chart_df=yearly,
                chart_title="年別推移（検索結果）",
                chart_subtitle=self._chart_subtitle(),
            )
            return {"ok": True, "path": _ensure_xlsx(path), "status": "Excel を保存しました。"}
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("実績Excel出力に失敗しました")
            return self._error("Excel 出力に失敗しました。", exc)

    def export_forecast(self) -> dict[str, Any]:
        try:
            if self._last_forecast_comparison is None or self._last_forecast_comparison.empty:
                raise ValueError("先に予測を実行してください。")
            path = self._choose_save_path(self._default_export_name(True))
            if not path:
                return {"ok": False, "cancelled": True}
            export_service.export_forecast_workbook(
                _ensure_xlsx(path),
                self._last_forecast_comparison,
                meta_lines=self._last_forecast_summary_lines,
                chart_subtitle=self._forecast_chart_subtitle(),
            )
            return {"ok": True, "path": _ensure_xlsx(path), "status": "Excel を保存しました。"}
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("予測Excel出力に失敗しました")
            return self._error("予測 Excel 出力に失敗しました。", exc)

    def chart(self, kind: str) -> dict[str, Any]:
        try:
            if kind == "yearly":
                if self._last_raw_df is None or self._last_raw_df.empty:
                    raise ValueError("先に検索を実行してください。")
                df = delivery_service.yearly_totals_from_raw_deliveries(self._last_raw_df)
                df = df.copy()
                df["種別"] = "実績"
                title = "年別推移（検索結果）"
                image = _yearly_chart_data_uri(df, title, self._chart_subtitle())
            elif kind == "monthly":
                if self._last_raw_df is None or self._last_raw_df.empty:
                    raise ValueError("先に検索を実行してください。")
                df = delivery_service.monthly_totals_from_raw_deliveries(self._last_raw_df)
                title = "月別推移（検索結果）"
                image = _monthly_chart_data_uri(df, title, self._chart_subtitle())
            elif kind == "forecast":
                if self._last_forecast_chart is None or self._last_forecast_chart.empty:
                    raise ValueError("先に予測を実行してください。")
                title = "年別推移（実績・直線延長・重み付き回帰・外部要因）"
                image = _yearly_chart_data_uri(
                    self._last_forecast_chart,
                    title,
                    self._forecast_chart_subtitle(),
                )
            else:
                raise ValueError("未対応のグラフ種別です。")
            return {"ok": True, "title": title, "image": image}
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("グラフ作成に失敗しました")
            return self._error("グラフ作成に失敗しました。", exc)

    def forecast_details(self) -> dict[str, Any]:
        return {"ok": True, "sections": FORECAST_DETAIL_SECTIONS}

    def _load_master_choices(self) -> tuple[list[str], list[str]]:
        with postgres_connector.open_app_connections() as conns:
            customer_pairs = delivery_service.fetch_customer_code_name_pairs(conns)
            hinbans = delivery_service.fetch_distinct_hinban(conns)

        customer_items: list[str] = []
        self._customer_display_to_name = {}
        self._customer_code_to_name = {}
        self._customer_name_to_display = {}
        for code, name in customer_pairs:
            item = f"{code}  {name}"
            customer_items.append(item)
            self._customer_display_to_name[item] = name
            self._customer_code_to_name[code] = name
            self._customer_name_to_display[name] = item
        self._all_hinbans = list(hinbans)
        return customer_items, self._all_hinbans

    def _resolve_customer_name(self, raw_text: str) -> Optional[str]:
        text = (raw_text or "").strip()
        if text in ("", ALL_LABEL):
            return None
        if text in self._customer_display_to_name:
            return self._customer_display_to_name[text]
        if text in self._customer_code_to_name:
            return self._customer_code_to_name[text]
        mapped = self._customer_name_to_display.get(text)
        if mapped is not None:
            return self._customer_display_to_name.get(mapped, text)
        return text

    def _customer_display_label(self, raw_text: str) -> str:
        text = (raw_text or "").strip()
        if text in ("", ALL_LABEL):
            return "全顧客"
        if text in self._customer_display_to_name:
            return text
        if text in self._customer_code_to_name:
            name = self._customer_code_to_name[text]
            return self._customer_name_to_display.get(name, f"{text}  {name}")
        return self._customer_name_to_display.get(text, text)

    def _period_label(self, date_from: Optional[date], date_to: Optional[date]) -> str:
        if date_from and date_to:
            return f"{date_from:%Y/%m/%d} - {date_to:%Y/%m/%d}"
        return "全期間"

    def _chart_subtitle(self) -> str:
        return (
            f"顧客: {self._last_search_meta.get('customer', '全顧客')} / "
            f"品番: {self._last_search_meta.get('product', '全品番')} / "
            f"対象期間: {self._last_search_meta.get('period', '全期間')}"
        )

    def _forecast_chart_subtitle(self) -> str:
        base = self._chart_subtitle()
        return f"{base}\n{self._last_forecast_graph_note}" if self._last_forecast_graph_note else base

    def _default_export_name(self, include_forecast: bool) -> str:
        customer = _sanitize_filename_part(self._last_search_meta.get("customer", "全顧客"))
        product = _sanitize_filename_part(self._last_search_meta.get("product", "全品番"))
        subject = "_".join(part for part in (customer, product) if part and part not in ("全顧客", "全品番"))
        suffix = "納品実績・予測データ" if include_forecast else "納品実績データ"
        return f"{subject or '検索結果'}{suffix}.xlsx"

    def _choose_save_path(self, default_name: str) -> str:
        if self._window is None:
            return default_name
        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=default_name,
            file_types=("Excel ファイル (*.xlsx)",),
        )
        if not result:
            return ""
        if isinstance(result, (list, tuple)):
            return str(result[0]) if result else ""
        return str(result)

    def _error(self, message: str, exc: BaseException) -> dict[str, Any]:
        return {"ok": False, "message": f"{message}\n{type(exc).__name__}: {exc}"}


def _yearly_chart_data_uri(df: pd.DataFrame, title: str, subtitle: str) -> str:
    fig = Figure(figsize=(10, 6), facecolor="#ffffff")
    ax1 = fig.add_subplot(2, 1, 1)
    ax2 = fig.add_subplot(2, 1, 2)
    _style_axes(ax1)
    _style_axes(ax2)
    work = df.copy()
    if work.empty:
        _empty_axes(ax1)
        _empty_axes(ax2)
    else:
        if "種別" not in work.columns:
            work["種別"] = "実績"
        all_years = sorted({int(y) for y in work["年"].dropna().tolist()})
        styles = {
            "実績": ("o", "-", "#1e88e5"),
            "予測": ("s", "--", "#f59e0b"),
            "直線延長予測": ("s", ":", "#c2410c"),
            "重み付き回帰予測": ("D", "--", "#ea580c"),
            "外部要因予測": ("^", "-.", "#10b981"),
        }

        def plot_pair(ax, col: str, ylabel: str) -> None:
            for kind in work["種別"].dropna().unique().tolist():
                part = work[work["種別"] == kind]
                if part.empty:
                    continue
                marker, linestyle, color = styles.get(kind, ("o", "-", "#646b75"))
                ax.plot(part["年"], part[col], marker=marker, linestyle=linestyle, color=color, label=str(kind))
            ax.set_ylabel(ylabel)
            ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
            if all_years:
                ax.set_xticks(all_years)
            ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=8)

        plot_pair(ax1, "納品数", "納品数")
        plot_pair(ax2, "金額", "金額")
        ax2.set_xlabel("年")
    fig.suptitle(f"{title}\n{subtitle}" if subtitle else title, fontsize=11, color="#2b2f36")
    fig.tight_layout(rect=(0, 0, 0.88, 0.92))
    return _figure_to_data_uri(fig)


def _monthly_chart_data_uri(df: pd.DataFrame, title: str, subtitle: str) -> str:
    fig = Figure(figsize=(10, 6), facecolor="#ffffff")
    ax1 = fig.add_subplot(2, 1, 1)
    ax2 = fig.add_subplot(2, 1, 2)
    _style_axes(ax1)
    _style_axes(ax2)
    work = df.copy()
    if work.empty:
        _empty_axes(ax1)
        _empty_axes(ax2)
    else:
        labels = work["年月"].astype(str).tolist()
        positions = list(range(len(labels)))
        tick_step = max(1, len(labels) // 12)
        tick_positions = positions[::tick_step] or positions
        if positions and tick_positions[-1] != positions[-1]:
            tick_positions.append(positions[-1])

        def plot_month(ax, col: str, ylabel: str) -> None:
            ax.plot(positions, work[col], marker="o", color="#1e88e5", label="実績")
            ax.set_ylabel(ylabel)
            ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
            ax.set_xticks(tick_positions)
            ax.set_xticklabels([labels[idx] for idx in tick_positions], rotation=45, ha="right")
            ax.legend(loc="upper left", frameon=False, fontsize=8)

        plot_month(ax1, "納品数", "納品数")
        plot_month(ax2, "金額", "金額")
        ax2.set_xlabel("年月")
    fig.suptitle(f"{title}\n{subtitle}" if subtitle else title, fontsize=11, color="#2b2f36")
    fig.tight_layout(rect=(0, 0, 1.0, 0.92))
    return _figure_to_data_uri(fig)


def _style_axes(ax) -> None:
    ax.set_facecolor("#f4f8fc")
    ax.grid(True, alpha=0.28)
    ax.ticklabel_format(style="plain", axis="y", useOffset=False)


def _empty_axes(ax) -> None:
    ax.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center", color="#646b75")


def _figure_to_data_uri(fig: Figure) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=130)
    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{data}"


FORECAST_DETAIL_SECTIONS = [
    {
        "title": "1. この予測がしていること",
        "body": "検索で取り出した納品実績を年ごとに合計し、これまでの増え方・減り方から先の年の目安を出しています。",
    },
    {
        "title": "2. 3つの予測のちがい",
        "body": "直線延長は全体の流れ、重み付き回帰は最近の動き、外部要因予測は IIP・CI も参考にします。",
    },
    {
        "title": "3. 表とグラフの見方",
        "body": "3つの予測が近い数字なら方向感はそろっています。差が大きい場合は読み切れない要素がある目安です。",
    },
    {
        "title": "4. 注意点",
        "body": "単発案件、価格改定、取引先の増減、新製品の開始や終了は過去データだけでは十分に反映できない場合があります。",
    },
]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    api = WebviewApi()
    index_path = _web_dir() / "index.html"
    window = webview.create_window(
        settings.WINDOW_TITLE,
        url=index_path.as_uri(),
        js_api=api,
        width=1280,
        height=780,
        min_size=(1100, 620),
    )
    api._set_window(window)
    webview.start(lambda: window.maximize(), gui="edgechromium", debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
