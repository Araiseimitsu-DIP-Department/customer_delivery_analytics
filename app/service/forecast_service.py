# -*- coding: utf-8 -*-
"""年次予測ロジック。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

# scikit-learn は PyInstaller 同梱が肥大化するため使わない。
# 加重最小二乗は numpy.linalg.lstsq（sqrt(sample_weight) で重み付け）で sklearn と同等。


@dataclass(frozen=True)
class ForecastModel:
    coefficients: np.ndarray
    intercept: float
    feature_names: tuple[str, ...]
    algorithm: str


@dataclass(frozen=True)
class ForecastBundle:
    comparison_df: pd.DataFrame
    chart_df: pd.DataFrame
    summary_lines: list[str]
    graph_note: str
    future_indicator_df: pd.DataFrame


LINEAR_KIND = "直線延長予測"
WEIGHTED_KIND = "重み付き回帰予測"
EXTERNAL_KIND = "外部要因予測"


def generate_weights(length: int) -> np.ndarray:
    """古い年は軽く、直近年を重くする。"""
    if length <= 0:
        return np.array([], dtype=float)
    if length == 1:
        return np.array([1.0], dtype=float)

    anchors = np.array([1.0, 1.2, 1.5, 2.0, 3.0, 5.0, 8.0], dtype=float)
    positions = np.linspace(0, len(anchors) - 1, num=length)
    return np.interp(positions, np.arange(len(anchors), dtype=float), anchors)


def fit_standard_model(
    years: Sequence[float],
    values: Sequence[float],
    weights: Sequence[float] | None = None,
) -> ForecastModel:
    x = np.asarray(years, dtype=float).reshape(-1, 1)
    y = np.asarray(values, dtype=float)
    w = _normalize_weights(len(y), weights)
    return _fit_linear_model(x, y, w, feature_names=("year",))


def fit_external_model(
    years: Sequence[float],
    indicator_values: pd.DataFrame | np.ndarray,
    values: Sequence[float],
    feature_names: Sequence[str],
    weights: Sequence[float] | None = None,
) -> ForecastModel:
    indicators = np.asarray(indicator_values, dtype=float)
    if indicators.ndim == 1:
        indicators = indicators.reshape(-1, 1)
    x = np.column_stack([np.asarray(years, dtype=float), indicators])
    y = np.asarray(values, dtype=float)
    w = _normalize_weights(len(y), weights)
    return _fit_linear_model(x, y, w, feature_names=("year", *tuple(feature_names)))


def predict(model: ForecastModel, features: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
    x = np.asarray(features, dtype=float)
    if x.ndim == 1:
        x = x.reshape(-1, len(model.feature_names))
    return np.asarray(x @ model.coefficients + model.intercept, dtype=float)


def build_future_iip_ci(
    indicator_yearly: pd.DataFrame,
    future_years: Sequence[int],
    user_inputs: pd.DataFrame | dict[int, dict[str, float]] | None = None,
) -> pd.DataFrame:
    future_years = np.asarray(list(future_years), dtype=int)
    out = pd.DataFrame({"年": future_years})
    history = indicator_yearly.copy() if indicator_yearly is not None else pd.DataFrame()
    if "年" in history.columns:
        history["年"] = pd.to_numeric(history["年"], errors="coerce")

    overrides = _normalize_future_inputs(user_inputs)
    for value_col in ("iip_avg", "ci_avg"):
        provided = overrides[["年", value_col]].dropna(subset=["年", value_col])
        provided_map = provided.drop_duplicates(subset=["年"]).set_index("年")[value_col]
        values = out["年"].map(provided_map)

        hist_part = history[["年", value_col]].dropna(subset=["年", value_col]).copy()
        if hist_part.empty:
            out[value_col] = values.fillna(0.0).to_numpy(dtype=float)
            continue

        missing_mask = values.isna()
        if missing_mask.any():
            values.loc[missing_mask] = _forecast_feature_series(
                hist_part["年"].to_numpy(dtype=float),
                hist_part[value_col].to_numpy(dtype=float),
                out.loc[missing_mask, "年"].to_numpy(dtype=float),
            )
        out[value_col] = values.to_numpy(dtype=float)
    return out


def run_yearly_forecast_bundle(
    actual_yearly: pd.DataFrame,
    indicator_yearly: pd.DataFrame,
    future_year_count: int,
    *,
    future_indicator_inputs: pd.DataFrame | dict[int, dict[str, float]] | None = None,
    macro_factors: float | pd.DataFrame | dict[int, float] | None = None,
) -> ForecastBundle:
    actual = _prepare_actual_yearly(actual_yearly)
    if actual.empty:
        empty = pd.DataFrame(
            columns=[
                "年",
                "実績\n納品数",
                "実績\n金額",
                "直線延長\n納品数",
                "直線延長\n金額",
                "重み付き回帰\n納品数",
                "重み付き回帰\n金額",
                "外部要因予測\n納品数",
                "外部要因予測\n金額",
            ]
        )
        return ForecastBundle(
            comparison_df=empty,
            chart_df=pd.DataFrame(columns=["年", "納品数", "金額", "種別"]),
            summary_lines=[
                "直線延長: データ不足のため計算できません",
                "重み付き回帰: データ不足のため計算できません",
                "外部要因予測: データ不足のため計算できません",
            ],
            graph_note="直線: 最小二乗 / 重み: 直近重視 / 外部: IIP・CI反映値なし",
            future_indicator_df=pd.DataFrame(columns=["年", "iip_avg", "ci_avg", "macro_factor"]),
        )

    future_years = np.arange(
        int(actual["年"].max()) + 1,
        int(actual["年"].max()) + 1 + future_year_count,
        dtype=int,
    )
    linear_qty_model = fit_standard_model(actual["年"], actual["納品数"], None)
    linear_amt_model = fit_standard_model(actual["年"], actual["金額"], None)
    linear_features = future_years.reshape(-1, 1)
    linear_qty = np.maximum(predict(linear_qty_model, linear_features), 0.0)
    linear_amt = np.maximum(predict(linear_amt_model, linear_features), 0.0)

    weights = generate_weights(len(actual.index))
    weighted_qty_model = fit_standard_model(actual["年"], actual["納品数"], weights)
    weighted_amt_model = fit_standard_model(actual["年"], actual["金額"], weights)
    weighted_features = future_years.reshape(-1, 1)
    weighted_qty = np.maximum(predict(weighted_qty_model, weighted_features), 0.0)
    weighted_amt = np.maximum(predict(weighted_amt_model, weighted_features), 0.0)

    future_indicator_df = build_future_iip_ci(
        indicator_yearly,
        future_years,
        user_inputs=future_indicator_inputs,
    )
    future_indicator_df["macro_factor"] = _resolve_macro_factors(future_years, macro_factors)

    external_source = ""
    external_feature_cols = _available_external_feature_columns(indicator_yearly, future_indicator_df)
    external_history = actual.merge(
        indicator_yearly[["年", "iip_avg", "ci_avg"]].copy(),
        on="年",
        how="left",
    )
    if external_feature_cols:
        external_history = external_history.dropna(subset=external_feature_cols)

    if external_feature_cols and len(external_history.index) >= 3:
        external_weights = generate_weights(len(external_history.index))
        external_qty_model = fit_external_model(
            external_history["年"],
            external_history[external_feature_cols],
            external_history["納品数"],
            external_feature_cols,
            external_weights,
        )
        external_amt_model = fit_external_model(
            external_history["年"],
            external_history[external_feature_cols],
            external_history["金額"],
            external_feature_cols,
            external_weights,
        )
        external_features = future_indicator_df[["年", *external_feature_cols]].to_numpy(dtype=float)
        external_qty = np.maximum(predict(external_qty_model, external_features), 0.0)
        external_amt = np.maximum(predict(external_amt_model, external_features), 0.0)
        external_source = _external_source_label(external_feature_cols)
    else:
        external_qty = weighted_qty.copy()
        external_amt = weighted_amt.copy()
        external_source = "外部指標不足のため重み付き回帰を代用"

    # 将来拡張: 高頻度 / 中頻度 / 低頻度のランク別係数をここへ乗せる。
    macro_factor_values = future_indicator_df["macro_factor"].to_numpy(dtype=float)
    external_qty = np.maximum(external_qty * macro_factor_values, 0.0)
    external_amt = np.maximum(external_amt * macro_factor_values, 0.0)

    actual_chart = actual.assign(種別="実績")
    linear_chart = pd.DataFrame(
        {
            "年": future_years,
            "納品数": linear_qty,
            "金額": linear_amt,
            "種別": LINEAR_KIND,
        }
    )
    weighted_chart = pd.DataFrame(
        {
            "年": future_years,
            "納品数": weighted_qty,
            "金額": weighted_amt,
            "種別": WEIGHTED_KIND,
        }
    )
    external_chart = pd.DataFrame(
        {
            "年": future_years,
            "納品数": external_qty,
            "金額": external_amt,
            "種別": EXTERNAL_KIND,
        }
    )
    chart_df = pd.concat(
        [actual_chart, linear_chart, weighted_chart, external_chart],
        ignore_index=True,
    )
    chart_df["納品数"] = pd.to_numeric(chart_df["納品数"], errors="coerce").round(0)
    chart_df["金額"] = pd.to_numeric(chart_df["金額"], errors="coerce").round(0)

    comparison_df = _build_comparison_table(
        actual_chart,
        linear_chart,
        weighted_chart,
        external_chart,
    )
    summary_lines = _build_summary_lines(
        actual,
        external_history,
        future_indicator_df,
        external_source=external_source,
        macro_factors=macro_factor_values,
    )
    return ForecastBundle(
        comparison_df=comparison_df,
        chart_df=chart_df,
        summary_lines=summary_lines,
        graph_note=_build_graph_note(external_history, future_indicator_df),
        future_indicator_df=future_indicator_df,
    )

def _fit_linear_model(
    features: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    *,
    feature_names: Iterable[str],
) -> ForecastModel:
    if values.size == 0:
        return ForecastModel(
            coefficients=np.zeros(features.shape[1], dtype=float),
            intercept=0.0,
            feature_names=tuple(feature_names),
            algorithm="empty",
        )

    if values.size == 1:
        return ForecastModel(
            coefficients=np.zeros(features.shape[1], dtype=float),
            intercept=float(values[0]),
            feature_names=tuple(feature_names),
            algorithm="flat",
        )

    weighted_features = np.column_stack([features, np.ones(len(values), dtype=float)])
    sqrt_weights = np.sqrt(weights).reshape(-1, 1)
    coef, *_ = np.linalg.lstsq(
        weighted_features * sqrt_weights,
        values * sqrt_weights.ravel(),
        rcond=None,
    )
    return ForecastModel(
        coefficients=np.asarray(coef[:-1], dtype=float),
        intercept=float(coef[-1]),
        feature_names=tuple(feature_names),
        algorithm="numpy",
    )


def _normalize_weights(length: int, weights: Sequence[float] | None) -> np.ndarray:
    if weights is None:
        return np.ones(length, dtype=float)
    arr = np.asarray(weights, dtype=float)
    if arr.size != length:
        raise ValueError("weights の件数がデータ件数と一致していません。")
    return arr


def _prepare_actual_yearly(actual_yearly: pd.DataFrame) -> pd.DataFrame:
    if actual_yearly is None or actual_yearly.empty:
        return pd.DataFrame(columns=["年", "納品数", "金額"])

    work = actual_yearly.copy()
    for col in ("年", "納品数", "金額"):
        if col not in work.columns:
            raise ValueError(f"年次予測に必要な列がありません: {col}")
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.dropna(subset=["年", "納品数", "金額"]).copy()
    work["年"] = work["年"].astype(int)
    work = work.sort_values("年").reset_index(drop=True)
    return work[["年", "納品数", "金額"]]


def _forecast_feature_series(
    history_years: np.ndarray,
    history_values: np.ndarray,
    future_years: np.ndarray,
) -> np.ndarray:
    if len(history_values) >= 2:
        model = fit_standard_model(history_years, history_values)
        return predict(model, future_years.reshape(-1, 1))
    if len(history_values) == 1:
        return np.full_like(future_years, fill_value=float(history_values[-1]), dtype=float)
    return np.zeros_like(future_years, dtype=float)


def _normalize_future_inputs(
    user_inputs: pd.DataFrame | dict[int, dict[str, float]] | None,
) -> pd.DataFrame:
    if user_inputs is None:
        return pd.DataFrame(columns=["年", "iip_avg", "ci_avg"])
    if isinstance(user_inputs, pd.DataFrame):
        out = user_inputs.copy()
    else:
        rows = []
        for year, values in user_inputs.items():
            rows.append(
                {
                    "年": int(year),
                    "iip_avg": values.get("iip_avg"),
                    "ci_avg": values.get("ci_avg"),
                }
            )
        out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["年", "iip_avg", "ci_avg"])
    for col in ("年", "iip_avg", "ci_avg"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out[[col for col in ("年", "iip_avg", "ci_avg") if col in out.columns]]


def _resolve_macro_factors(
    future_years: np.ndarray,
    macro_factors: float | pd.DataFrame | dict[int, float] | None,
) -> np.ndarray:
    if macro_factors is None:
        return np.ones_like(future_years, dtype=float)
    if isinstance(macro_factors, (int, float)):
        return np.full_like(future_years, fill_value=float(macro_factors), dtype=float)
    if isinstance(macro_factors, dict):
        values = [float(macro_factors.get(int(year), 1.0)) for year in future_years]
        return np.asarray(values, dtype=float)

    work = macro_factors.copy()
    if "年" not in work.columns or "macro_factor" not in work.columns:
        return np.ones_like(future_years, dtype=float)
    work["年"] = pd.to_numeric(work["年"], errors="coerce")
    work["macro_factor"] = pd.to_numeric(work["macro_factor"], errors="coerce")
    mapping = dict(zip(work["年"].dropna().astype(int), work["macro_factor"].fillna(1.0)))
    return np.asarray([float(mapping.get(int(year), 1.0)) for year in future_years], dtype=float)


def _build_comparison_table(
    actual_chart: pd.DataFrame,
    linear_chart: pd.DataFrame,
    weighted_chart: pd.DataFrame,
    external_chart: pd.DataFrame,
) -> pd.DataFrame:
    parts = [
        actual_chart[["年", "納品数", "金額"]]
        .rename(columns={"納品数": "実績\n納品数", "金額": "実績\n金額"})
        .set_index("年"),
        linear_chart[["年", "納品数", "金額"]]
        .rename(columns={"納品数": "直線延長\n納品数", "金額": "直線延長\n金額"})
        .set_index("年"),
        weighted_chart[["年", "納品数", "金額"]]
        .rename(columns={"納品数": "重み付き回帰\n納品数", "金額": "重み付き回帰\n金額"})
        .set_index("年"),
        external_chart[["年", "納品数", "金額"]]
        .rename(columns={"納品数": "外部要因予測\n納品数", "金額": "外部要因予測\n金額"})
        .set_index("年"),
    ]
    out = pd.concat(parts, axis=1).reset_index().sort_values("年").reset_index(drop=True)

    for col in out.columns:
        if col == "年":
            out[col] = out[col].astype(int)
            continue
        out[col] = pd.to_numeric(out[col], errors="coerce").round(0)
    return out


def _build_summary_lines(
    actual: pd.DataFrame,
    external_history: pd.DataFrame,
    future_indicator_df: pd.DataFrame,
    *,
    external_source: str,
    macro_factors: np.ndarray,
) -> list[str]:
    start_year = int(actual["年"].min())
    end_year = int(actual["年"].max())
    feature_cols = _available_external_feature_columns(external_history, future_indicator_df)
    external_line = f"外部要因予測: {_external_source_label(feature_cols)}で算出"
    if not feature_cols:
        external_line = "外部要因予測: 外部指標が未取得のため参考値として表示"

    return [
        f"直線延長: {start_year}〜{end_year}年の実績傾向から算出",
        "重み付き回帰: 直近年の実績を重視して算出",
        external_line,
        "注意: 予測は過去実績から見た目安です",
    ]


def _build_weight_summary_line(actual: pd.DataFrame) -> str:
    years = actual["年"].astype(int).tolist()
    weights = generate_weights(len(years))
    if not years:
        return "重み付き回帰: 重みなし"
    return (
        "重み付き回帰: "
        f"{years[0]}={weights[0]:.2f} → {years[-1]}={weights[-1]:.2f}（直近重視）"
    )


def _build_weight_detail_line(actual: pd.DataFrame) -> str:
    years = actual["年"].astype(int).tolist()
    weights = generate_weights(len(years))
    if not years:
        return "重み詳細: なし"
    parts = [f"{year}={weight:.2f}" for year, weight in zip(years, weights)]
    return "重み詳細: " + " / ".join(parts)


def _build_indicator_reflection_line(
    external_history: pd.DataFrame,
    future_indicator_df: pd.DataFrame,
) -> str:
    feature_cols = _available_external_feature_columns(external_history, future_indicator_df)
    if not feature_cols:
        return "反映値: 外部指標の年次値不足"
    history = external_history.dropna(subset=feature_cols).copy()
    future = future_indicator_df.dropna(subset=feature_cols).copy()
    if history.empty or future.empty:
        return "反映値: 外部指標の年次値不足"

    base_row = history.sort_values("年").iloc[-1]
    first_future = future.sort_values("年").iloc[0]
    last_future = future.sort_values("年").iloc[-1]
    values = []
    for col in feature_cols:
        label = _external_feature_label(col)
        values.append(
            f"{label}={float(first_future[col]):.1f}→{float(last_future[col]):.1f}"
        )
    return (
        "反映値: "
        f"基準 {int(base_row['年'])}年 / "
        f"将来 {int(first_future['年'])}年→{int(last_future['年'])}年 "
        + ", ".join(values)
    )


def _build_graph_note(
    external_history: pd.DataFrame,
    future_indicator_df: pd.DataFrame,
) -> str:
    feature_cols = _available_external_feature_columns(external_history, future_indicator_df)
    if not feature_cols:
        return "直線: 最小二乗 / 重み: 直近重視 / 外部: 指標値不足"
    history = external_history.dropna(subset=feature_cols).copy()
    future = future_indicator_df.dropna(subset=feature_cols).copy()
    if history.empty or future.empty:
        return "直線: 最小二乗 / 重み: 直近重視 / 外部: 指標値不足"

    first_future = future.sort_values("年").iloc[0]
    last_future = future.sort_values("年").iloc[-1]
    values = []
    for col in feature_cols:
        values.append(
            f"{_external_feature_label(col)} {float(first_future[col]):.1f}→{float(last_future[col]):.1f}"
        )
    return (
        "直線: 最小二乗 / 重み: 直近重視 / "
        "外部: " + ", ".join(values)
    )


def _available_external_feature_columns(*frames: pd.DataFrame) -> list[str]:
    cols = []
    for col in ("iip_avg", "ci_avg"):
        if all(
            frame is not None
            and col in frame.columns
            and pd.to_numeric(frame[col], errors="coerce").notna().any()
            for frame in frames
        ):
            cols.append(col)
    return cols


def _external_feature_label(column: str) -> str:
    return {"iip_avg": "IIP", "ci_avg": "CI"}.get(column, column)


def _external_source_label(columns: Sequence[str]) -> str:
    labels = [_external_feature_label(col) for col in columns]
    if not labels:
        return "外部指標なし"
    return " / ".join(labels)
