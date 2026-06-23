# -*- coding: utf-8 -*-
"""外部指標の取得・保存・年次化。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pandas as pd

from app.infrastructure.appdata_paths import AppDataPaths
from app.infrastructure.indicator_store import IndicatorMaster, IndicatorStore

IIP_CODE = "IIP"
CI_CODE = "CI"

IIP_SOURCE_URL = "https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_gsm1j.xlsx"
CI_PAGE_URL = "https://www.esri.cao.go.jp/jp/stat/di/di.html"
CI_SOURCE_URL = "https://www.esri.cao.go.jp/jp/stat/di/0605ci.xlsx"
DOWNLOAD_TIMEOUT_SECONDS = 20


@dataclass
class IndicatorStatus:
    code: str
    status: str
    detail: str
    fetched_at: str = ""


class ExternalIndicatorFetchError(Exception):
    """外部指標の取得失敗。"""


class _ExcelLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


class ExternalIndicatorService:
    """IIP / CI の取得、SQLite 保存、年次化。"""

    def __init__(self) -> None:
        self._paths = AppDataPaths()
        self._store = IndicatorStore(self._paths.indicators_db_path())
        self._store.initialize()
        self._store.upsert_masters(
            [
                IndicatorMaster(
                    IIP_CODE,
                    "鉱工業生産指数",
                    "index",
                    "METI",
                    IIP_SOURCE_URL,
                ),
                IndicatorMaster(
                    CI_CODE,
                    "景気動向指数（一致指数）",
                    "index",
                    "内閣府",
                    CI_SOURCE_URL,
                ),
            ]
        )

    @property
    def db_path(self) -> str:
        return str(self._paths.indicators_db_path())

    def refresh_if_needed(self) -> dict[str, IndicatorStatus]:
        results: dict[str, IndicatorStatus] = {}
        for code in (IIP_CODE, CI_CODE):
            results[code] = self._refresh_one_if_needed(code)
        return results

    def _refresh_one_if_needed(self, code: str) -> IndicatorStatus:
        now = datetime.now()
        status = self._store.get_fetch_status(code)
        last_success = (status or {}).get("last_success_at", "")
        should_refresh = True
        if last_success:
            try:
                dt = datetime.fromisoformat(last_success)
                should_refresh = (dt.year, dt.month) != (now.year, now.month)
            except ValueError:
                should_refresh = True
        if not should_refresh and self._store.has_monthly_values(code):
            return IndicatorStatus(code, "latest", "当月取得済み", last_success)

        try:
            frame = self._fetch_indicator(code)
            fetched_at = now.isoformat(timespec="seconds")
            frame["fetched_at"] = fetched_at
            self._store.replace_monthly_values(code, frame)
            latest_pub = str(frame["published_date"].dropna().iloc[-1]) if "published_date" in frame.columns and not frame.empty else ""
            self._store.update_fetch_status(
                code,
                last_success_at=fetched_at,
                last_attempt_at=fetched_at,
                last_error="",
                source_last_published_date=latest_pub,
            )
            return IndicatorStatus(code, "updated", "最新値を取得", fetched_at)
        except Exception as e:  # noqa: BLE001
            attempted_at = now.isoformat(timespec="seconds")
            self._store.update_fetch_status(
                code,
                last_attempt_at=attempted_at,
                last_error=str(e),
            )
            if self._store.has_monthly_values(code):
                return IndicatorStatus(code, "cached", f"取得失敗のためキャッシュ利用: {e}", last_success)
            return IndicatorStatus(code, "missing", f"未取得: {e}", "")

    def build_yearly_indicator_frame(self, year_from: int, year_to: int) -> pd.DataFrame:
        from_ym = f"{year_from:04d}-01"
        to_ym = f"{year_to:04d}-12"
        iip = self._store.get_monthly_values(IIP_CODE, from_ym=from_ym, to_ym=to_ym)
        ci = self._store.get_monthly_values(CI_CODE, from_ym=from_ym, to_ym=to_ym)

        def to_yearly(frame: pd.DataFrame, value_name: str) -> pd.DataFrame:
            if frame.empty:
                return pd.DataFrame(columns=["年", value_name])
            out = pd.DataFrame(
                {
                    "年": pd.to_numeric(frame["year_month"].str.slice(0, 4), errors="coerce"),
                    value_name: pd.to_numeric(frame["value"], errors="coerce"),
                }
            ).dropna(subset=["年", value_name])
            out["年"] = out["年"].astype(int)
            out = out.groupby("年", as_index=False, sort=True).agg(**{value_name: (value_name, "mean")})
            return out

        out = pd.DataFrame({"年": list(range(year_from, year_to + 1))})
        out = out.merge(to_yearly(iip, "iip_avg"), on="年", how="left")
        out = out.merge(to_yearly(ci, "ci_avg"), on="年", how="left")
        return out

    def summarize_statuses(self, statuses: dict[str, IndicatorStatus]) -> str:
        labels = {
            IIP_CODE: "IIP",
            CI_CODE: "CI",
        }
        parts = []
        for code in (IIP_CODE, CI_CODE):
            status = statuses.get(code)
            if status is None:
                continue
            label = labels.get(code, code)
            if status.status == "updated":
                parts.append(f"{label}: 最新取得")
            elif status.status == "latest":
                parts.append(f"{label}: 当月取得済み")
            elif status.status == "cached":
                parts.append(f"{label}: キャッシュ利用")
            else:
                parts.append(f"{label}: 未取得")
        return " / ".join(parts)

    def _fetch_indicator(self, code: str) -> pd.DataFrame:
        if code == IIP_CODE:
            return self._fetch_iip()
        if code == CI_CODE:
            return self._fetch_ci()
        raise ExternalIndicatorFetchError(f"未対応の指標です: {code}")

    @staticmethod
    def _download_excel(url: str) -> bytes:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.read()

    @staticmethod
    def _download_text(url: str) -> str:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.read().decode("utf-8", errors="replace")

    def _resolve_latest_ci_url(self) -> str:
        try:
            html = self._download_text(CI_PAGE_URL)
            parser = _ExcelLinkParser()
            parser.feed(html)
            candidates = [
                urljoin(CI_PAGE_URL, href)
                for href in parser.hrefs
                if href.lower().endswith("ci.xlsx")
            ]
            if candidates:
                return sorted(candidates)[-1]
        except Exception:
            pass
        return CI_SOURCE_URL

    def _fetch_iip(self) -> pd.DataFrame:
        content = self._download_excel(IIP_SOURCE_URL)
        sheet = pd.read_excel(BytesIO(content), sheet_name="生産", header=None)
        if sheet.shape[0] < 4:
            raise ExternalIndicatorFetchError("IIP の Excel 形式を解析できません。")

        monthly_codes = sheet.iloc[2, 3:]
        target = sheet[sheet.iloc[:, 0].astype(str) == "1000000000"]
        if target.empty:
            target = sheet[sheet.iloc[:, 1].astype(str) == "鉱工業"]
        if target.empty:
            raise ExternalIndicatorFetchError("IIP の鉱工業行が見つかりません。")
        values = target.iloc[0, 3:]
        rows = pd.DataFrame({"raw_ym": monthly_codes.to_numpy(), "value": values.to_numpy()})
        rows["year_month"] = rows["raw_ym"].map(self._normalize_yyyymm)
        rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
        rows = rows.dropna(subset=["year_month", "value"])[["year_month", "value"]].copy()
        if rows.empty:
            raise ExternalIndicatorFetchError("IIP の月次データを取り出せませんでした。")
        rows["published_date"] = datetime.now().date().isoformat()
        return rows

    def _fetch_ci(self) -> pd.DataFrame:
        content = self._download_excel(self._resolve_latest_ci_url())
        frame = pd.read_excel(BytesIO(content), sheet_name="指数 Indexes", header=None)
        if frame.shape[0] < 7:
            raise ExternalIndicatorFetchError("CI の Excel 形式を解析できません。")
        work = frame.iloc[6:, [1, 2, 4]].copy()
        work.columns = ["year", "month", "value"]
        work["year"] = pd.to_numeric(work["year"], errors="coerce")
        work["month"] = pd.to_numeric(work["month"], errors="coerce")
        work["value"] = pd.to_numeric(work["value"], errors="coerce")
        work = work.dropna(subset=["year", "month", "value"]).copy()
        work["year"] = work["year"].astype(int)
        work["month"] = work["month"].astype(int)
        work = work[work["month"].between(1, 12)]
        if work.empty:
            raise ExternalIndicatorFetchError("CI の月次データを取り出せませんでした。")
        out = pd.DataFrame(
            {
                "year_month": work["year"].astype(str).str.zfill(4)
                + "-"
                + work["month"].astype(str).str.zfill(2),
                "value": work["value"].to_numpy(dtype=float),
            }
        )
        out["published_date"] = datetime.now().date().isoformat()
        return out

    @staticmethod
    def _normalize_yyyymm(value: object) -> Optional[str]:
        if pd.isna(value):
            return None
        text = str(value).strip()
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) < 6:
            return None
        digits = digits[:6]
        year = int(digits[:4])
        month = int(digits[4:6])
        if month < 1 or month > 12:
            return None
        return f"{year:04d}-{month:02d}"
