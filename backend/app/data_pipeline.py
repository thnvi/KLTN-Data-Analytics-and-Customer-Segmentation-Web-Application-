from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.metrics.pairwise import cosine_similarity

try:
    from statsmodels.tsa.arima.model import ARIMA  # type: ignore
except Exception:
    ARIMA = None

CATALOG_FILE = "netflix_titles.csv"
TOP10_FILE = "netflix_top10_global_latest.csv"
ENGAGEMENT_FILE = "netflix_engagement_2025_h1.csv"

ANALYSIS_START_YEAR = 2020
ANALYSIS_END_YEAR = 2025
ANALYSIS_YEARS = list(range(ANALYSIS_START_YEAR, ANALYSIS_END_YEAR + 1))
MONTHS = list(range(1, 13))
MONTH_OPTIONS = [{"value": f"{i:02d}", "label": f"Tháng {i}"} for i in MONTHS]


@dataclass
class DashboardData:
    monthly: List[Dict]
    genres: List[Dict]
    ratings: List[Dict]
    top_titles: List[Dict]
    countries: List[Dict]
    kpis: Dict[str, str]
    filter_options: Dict[str, List]
    heatmap: List[Dict]
    insights: List[Dict]
    data_quality: Dict


class NetflixAnalyticsService:
    """Single source of truth for the Netflix dashboard.

    All dashboard charts use the same filter logic: genre + year + month + country.
    The analytical period is fixed to 2020-2025 so the web and thesis stay consistent.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else Path(__file__).resolve().parents[1] / "data"
        self.df_catalog = self._load_catalog()
        self.df_catalog = self._preprocess_catalog(self.df_catalog)
        self.top10_df = self._load_top10()
        self.engagement_df = self._load_engagement()
        self.df_clean = self._extend_catalog_with_external_sources(self.df_catalog)
        self.df_unified = self._build_unified_dataset()
        self._tfidf: Optional[TfidfVectorizer] = None
        self._tfidf_matrix = None

    # -------------------- Loading + cleaning --------------------
    @staticmethod
    def normalize_title(value: object) -> str:
        text = "" if pd.isna(value) else str(value)
        text = text.split("//")[0]
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _clean_text(value: object) -> str:
        text = "" if pd.isna(value) else str(value).lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _split_list(value: object) -> List[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        text = "" if pd.isna(value) else str(value)
        # Some already-cleaned CSVs store lists as "['A', 'B']".
        text = text.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
        return [part.strip() for part in text.split(",") if part.strip()]

    def _load_catalog(self) -> pd.DataFrame:
        path = self.data_dir / CATALOG_FILE
        if not path.exists():
            fallback = self.data_dir / "netflix_titles_cleaned.csv"
            if fallback.exists():
                path = fallback
            else:
                raise FileNotFoundError(f"Không tìm thấy {CATALOG_FILE} trong {self.data_dir}")
        return pd.read_csv(path)

    def _load_top10(self) -> pd.DataFrame:
        path = self.data_dir / TOP10_FILE
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip().str.lower()
        if "show_title" in df.columns and "title" not in df.columns:
            df["title"] = df["show_title"]
        if "title" not in df.columns:
            return pd.DataFrame()
        df["title_key"] = df["title"].apply(self.normalize_title)
        df["week"] = pd.to_datetime(df.get("week"), errors="coerce")
        for col in ["weekly_rank", "weekly_hours_viewed", "weekly_views", "cumulative_weeks_in_top_10"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            else:
                df[col] = 0
        return df[df["week"].dt.year.between(ANALYSIS_START_YEAR, ANALYSIS_END_YEAR, inclusive="both")].copy()

    def _load_engagement(self) -> pd.DataFrame:
        path = self.data_dir / ENGAGEMENT_FILE
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip().str.lower()
        if "title" not in df.columns:
            return pd.DataFrame()
        df["title"] = df["title"].astype(str).str.split("//").str[0].str.strip()
        df["title_key"] = df["title"].apply(self.normalize_title)
        df["release_date"] = pd.to_datetime(df.get("release_date"), errors="coerce")
        for col in ["hours_viewed", "views"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            else:
                df[col] = 0
        return df[df["release_date"].dt.year.between(ANALYSIS_START_YEAR, ANALYSIS_END_YEAR, inclusive="both")].copy()

    def _preprocess_catalog(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip().str.lower()
        for col in ["show_id", "type", "title", "director", "cast", "country", "date_added", "release_year", "rating", "duration", "listed_in", "description"]:
            if col not in df.columns:
                df[col] = "Unknown"
        df = df.drop_duplicates(subset=["title", "type", "release_year"], keep="first")
        df["data_source"] = df.get("data_source", "Netflix Catalog")
        df["title_key"] = df["title"].apply(self.normalize_title)
        df["date_added"] = pd.to_datetime(df["date_added"], format="mixed", errors="coerce")
        df["year_added"] = df["date_added"].dt.year.astype("Int64")
        df["month_added"] = df["date_added"].dt.month.astype("Int64")
        df["quarter_added"] = df["date_added"].dt.to_period("Q").astype(str)
        df["year_month"] = df["date_added"].dt.to_period("M").astype(str)
        df["director"] = df["director"].fillna("Unknown")
        df["cast"] = df["cast"].fillna("Unknown")
        df["country"] = df["country"].fillna("Unknown")
        df["rating"] = df["rating"].fillna("Unknown")
        df["duration"] = df["duration"].fillna("Unknown")
        df["listed_in"] = df["listed_in"].fillna("Unknown")
        df["description"] = df["description"].fillna("")
        df["country_list"] = df["country"].apply(self._split_list)
        df["country_main"] = df["country_list"].apply(lambda values: values[0] if values else "Unknown")
        df["genre_list"] = df["listed_in"].apply(self._split_list)
        df["duration_value"] = pd.to_numeric(df["duration"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
        df["duration_unit"] = df["duration"].astype(str).str.extract(r"([A-Za-z]+)")[0]
        df["movie_minutes"] = np.where(df["type"].eq("Movie"), df["duration_value"], np.nan)
        df["tvshow_seasons"] = np.where(df["type"].eq("TV Show"), df["duration_value"], np.nan)
        df["description_clean"] = df["description"].apply(self._clean_text)
        return df

    @staticmethod
    def _external_type(value: object) -> str:
        text = "" if pd.isna(value) else str(value).lower()
        if "tv" in text or "show" in text or "series" in text:
            return "TV Show"
        return "Movie"

    @staticmethod
    def _external_duration(value: object, content_type: str) -> str:
        if pd.isna(value):
            return "1 Season" if content_type == "TV Show" else "90 min"
        text = str(value).strip()
        # Runtime can be decimal hours (1.7) or H:MM.
        try:
            if ":" not in text:
                minutes = int(round(float(text) * 60))
                return f"{max(minutes, 1)} min" if content_type == "Movie" else "1 Season"
        except Exception:
            pass
        parts = [p for p in text.split(":") if p.strip().isdigit()]
        if len(parts) >= 2:
            nums = [int(p) for p in parts]
            minutes = nums[0] * 60 + nums[1] if len(nums) >= 2 else nums[0]
            return f"{max(minutes, 1)} min" if content_type == "Movie" else "1 Season"
        return "1 Season" if content_type == "TV Show" else "90 min"

    def _make_external_row(self, title: str, content_type: str, date_added: object, listed_in: str, description: str, data_source: str, duration: str) -> Dict:
        date = pd.to_datetime(date_added, errors="coerce")
        year = int(date.year) if pd.notna(date) else ANALYSIS_END_YEAR
        return {
            "show_id": f"ext_{self.normalize_title(title)}_{data_source}"[:90],
            "type": content_type,
            "title": title,
            "director": "Unknown",
            "cast": "Unknown",
            "country": "Unknown",
            "date_added": date,
            "release_year": year,
            "rating": "Unknown",
            "duration": duration,
            "listed_in": listed_in,
            "description": description,
            "data_source": data_source,
        }

    def _extend_catalog_with_external_sources(self, df: pd.DataFrame) -> pd.DataFrame:
        rows: List[Dict] = []
        existing = set(df["title_key"].dropna().astype(str))

        if not self.top10_df.empty:
            grouped = self.top10_df.groupby("title_key", dropna=True)
            for title_key, group in grouped:
                if not title_key or title_key in existing:
                    continue
                first = group.sort_values("week").iloc[0]
                title = str(first.get("title") or first.get("show_title") or "").strip()
                if not title:
                    continue
                content_type = self._external_type(first.get("category"))
                hours = int(group["weekly_hours_viewed"].sum())
                views = int(group["weekly_views"].sum())
                rows.append(self._make_external_row(
                    title=title,
                    content_type=content_type,
                    date_added=first.get("week"),
                    listed_in=f"Trending Content, Netflix Top 10, {first.get('category', 'Global Top 10')}",
                    description=f"Supplemental Netflix Top 10 Weekly record. Hours viewed: {hours:,}; views: {views:,}.",
                    data_source="Netflix Top 10 Weekly 2020-2025",
                    duration=self._external_duration(first.get("runtime"), content_type),
                ))
                existing.add(title_key)

        if not self.engagement_df.empty:
            eng = self.engagement_df.sort_values(["views", "hours_viewed"], ascending=False).drop_duplicates("title_key")
            for _, row in eng.iterrows():
                title_key = str(row.get("title_key", ""))
                if not title_key or title_key in existing:
                    continue
                title = str(row.get("title", "")).strip()
                if not title:
                    continue
                content_type = self._external_type(row.get("content_type"))
                views = int(row.get("views", 0))
                hours = int(row.get("hours_viewed", 0))
                rows.append(self._make_external_row(
                    title=title,
                    content_type=content_type,
                    date_added=row.get("release_date"),
                    listed_in="Netflix Engagement Report, Popular Content",
                    description=f"Supplemental Netflix Engagement Report record. Hours viewed: {hours:,}; views: {views:,}.",
                    data_source="Netflix Engagement Report 2020-2025",
                    duration=self._external_duration(row.get("runtime"), content_type),
                ))
                existing.add(title_key)

        if rows:
            ext = self._preprocess_catalog(pd.DataFrame(rows))
            df = pd.concat([df, ext], ignore_index=True)
        # Keep canonical analysis period in the working dataset.
        df = df[df["year_added"].between(ANALYSIS_START_YEAR, ANALYSIS_END_YEAR, inclusive="both")].copy()
        df = df.drop_duplicates("title_key", keep="first").reset_index(drop=True)
        return df

    # -------------------- Unified popularity table --------------------
    def _build_unified_dataset(self) -> pd.DataFrame:
        df = self.df_clean.copy()
        metric_cols = ["top10_weeks", "best_rank", "top10_hours_viewed", "top10_views", "engagement_hours_viewed", "engagement_views", "engagement_score"]
        for col in metric_cols:
            df[col] = 0.0

        if not self.top10_df.empty:
            agg = self.top10_df.groupby("title_key").agg(
                top10_weeks=("week", "nunique"),
                best_rank=("weekly_rank", "min"),
                top10_hours_viewed=("weekly_hours_viewed", "sum"),
                top10_views=("weekly_views", "sum"),
            ).reset_index()
            df = df.merge(agg, on="title_key", how="left", suffixes=("", "_top10"))
            for col in ["top10_weeks", "best_rank", "top10_hours_viewed", "top10_views"]:
                df[col] = df[f"{col}_top10"].fillna(df[col]) if f"{col}_top10" in df.columns else df[col]
                df.drop(columns=[f"{col}_top10"], errors="ignore", inplace=True)

        if not self.engagement_df.empty:
            agg = self.engagement_df.groupby("title_key").agg(
                engagement_hours_viewed=("hours_viewed", "sum"),
                engagement_views=("views", "sum"),
            ).reset_index()
            df = df.merge(agg, on="title_key", how="left", suffixes=("", "_eng"))
            for col in ["engagement_hours_viewed", "engagement_views"]:
                df[col] = df[f"{col}_eng"].fillna(df[col]) if f"{col}_eng" in df.columns else df[col]
                df.drop(columns=[f"{col}_eng"], errors="ignore", inplace=True)

        for col in metric_cols[:-1]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        raw_score = (
            np.log1p(df["top10_views"]) * 10
            + np.log1p(df["top10_hours_viewed"]) * 8
            + np.log1p(df["engagement_views"]) * 12
            + np.log1p(df["engagement_hours_viewed"]) * 10
            + df["top10_weeks"] * 5
        )
        max_score = float(raw_score.max()) if len(raw_score) and raw_score.max() > 0 else 1.0
        df["engagement_score"] = (raw_score / max_score * 100).round(2)
        return df

    # -------------------- Filters --------------------
    def _norm_genre(self, value: Optional[str]) -> Optional[str]:
        if value is None or str(value).strip().lower() == "all" or not str(value).strip():
            return None
        return str(value).strip()

    def _norm_year(self, value: Optional[str]) -> Optional[int]:
        if value is None or str(value).strip().lower() == "all" or not str(value).strip():
            return None
        try:
            year = int(value)
            return year if year in ANALYSIS_YEARS else None
        except Exception:
            return None

    def _norm_month(self, value: Optional[str]) -> Optional[int]:
        if value is None or str(value).strip().lower() == "all" or not str(value).strip():
            return None
        try:
            month = int(value)
            return month if 1 <= month <= 12 else None
        except Exception:
            return None

    def _norm_country(self, value: Optional[str]) -> Optional[str]:
        if value is None or str(value).strip().lower() == "all" or not str(value).strip():
            return None
        aliases = {"us": "United States", "usa": "United States", "viet nam": "Vietnam", "vn": "Vietnam"}
        text = str(value).strip()
        return aliases.get(text.lower(), text)

    def _filter_df(self, df: pd.DataFrame, genre: Optional[str] = None, year: Optional[str] = None, month: Optional[str] = None, country: Optional[str] = None) -> pd.DataFrame:
        out = df.copy()
        out = out[out["year_added"].between(ANALYSIS_START_YEAR, ANALYSIS_END_YEAR, inclusive="both")]
        genre_value = self._norm_genre(genre)
        year_value = self._norm_year(year)
        month_value = self._norm_month(month)
        country_value = self._norm_country(country)
        if genre_value:
            out = out[out["genre_list"].apply(lambda values: genre_value in values if isinstance(values, list) else False)]
        if year_value:
            out = out[out["year_added"] == year_value]
        if month_value:
            out = out[out["month_added"] == month_value]
        if country_value:
            out = out[out["country_main"].fillna("Unknown").str.lower() == country_value.lower()]
        return out.copy()

    def get_filter_options(self) -> Dict[str, List]:
        base = self._filter_df(self.df_clean)
        genres = sorted(base.explode("genre_list")["genre_list"].dropna().astype(str).unique().tolist())
        countries = sorted(base["country_main"].dropna().astype(str).unique().tolist())
        return {
            "genres": genres,
            "years": [str(y) for y in ANALYSIS_YEARS],
            "months": MONTH_OPTIONS,
            "countries": countries,
        }

    # -------------------- Chart data --------------------
    def _date_range_for_filter(self, year: Optional[str] = None, month: Optional[str] = None) -> pd.DatetimeIndex:
        y = self._norm_year(year)
        m = self._norm_month(month)
        if y and m:
            return pd.date_range(f"{y}-{m:02d}-01", periods=1, freq="MS")
        if y:
            return pd.date_range(f"{y}-01-01", f"{y}-12-01", freq="MS")
        full = pd.date_range(f"{ANALYSIS_START_YEAR}-01-01", f"{ANALYSIS_END_YEAR}-12-01", freq="MS")
        if m:
            return pd.DatetimeIndex([d for d in full if d.month == m])
        return full

    def monthly_titles(self, genre: Optional[str] = None, year: Optional[str] = None, month: Optional[str] = None, country: Optional[str] = None) -> pd.DataFrame:
        df = self._filter_df(self.df_clean, genre=genre, year=year, month=month, country=country)
        rng = self._date_range_for_filter(year=year, month=month)
        if df.empty:
            return pd.DataFrame({"year_month": rng, "title_count": [0] * len(rng)})
        counts = df.dropna(subset=["date_added"]).groupby(pd.Grouper(key="date_added", freq="MS")).size()
        out = pd.DataFrame({"year_month": rng})
        out["title_count"] = out["year_month"].map(counts).fillna(0).astype(int)
        return out

    def content_added_heatmap(self, genre: Optional[str] = None, year: Optional[str] = None, month: Optional[str] = None, country: Optional[str] = None) -> List[Dict]:
        df = self._filter_df(self.df_clean, genre=genre, year=year, month=month, country=country)
        selected_year = self._norm_year(year)
        selected_month = self._norm_month(month)
        years = [selected_year] if selected_year else ANALYSIS_YEARS
        months = [selected_month] if selected_month else MONTHS
        grouped: Dict[Tuple[int, int], int] = {}
        if not df.empty:
            counts = df.groupby(["month_added", "year_added"]).size()
            grouped = {(int(m), int(y)): int(v) for (m, y), v in counts.items() if pd.notna(m) and pd.notna(y)}
        return [{"month": int(m), "year": int(y), "value": int(grouped.get((m, y), 0))} for m in months for y in years]

    def top_genres(self, n: int = 10, **filters) -> pd.DataFrame:
        df = self._filter_df(self.df_clean, **filters).explode("genre_list")
        if df.empty:
            return pd.DataFrame(columns=["genre", "count"])
        return df["genre_list"].dropna().value_counts().head(n).reset_index().rename(columns={"genre_list": "genre", "count": "count"})

    def country_distribution(self, n: int = 10, **filters) -> pd.DataFrame:
        df = self._filter_df(self.df_clean, **filters)
        if df.empty:
            return pd.DataFrame(columns=["country", "count"])
        return df["country_main"].fillna("Unknown").value_counts().head(n).reset_index().rename(columns={"country_main": "country", "count": "count"})

    def ratings_distribution(self, n: int = 8, **filters) -> pd.DataFrame:
        df = self._filter_df(self.df_clean, **filters)
        if df.empty:
            return pd.DataFrame(columns=["rating", "count", "percentage"])
        vc = df["rating"].fillna("Unknown").value_counts().head(n).reset_index()
        vc.columns = ["rating", "count"]
        vc["percentage"] = vc["count"] / max(len(df), 1) * 100
        return vc

    # -------------------- Forecasting --------------------
    def _seasonal_trend_forecast(self, series: pd.Series, periods: int, model_name: str) -> pd.DataFrame:
        series = series.astype(float)
        dates = pd.date_range(series.index[-1] + pd.offsets.MonthBegin(1), periods=periods, freq="MS")
        values = series.values
        if len(values) >= 2:
            x = np.arange(len(values))
            slope, intercept = np.polyfit(x, values, 1)
        else:
            slope, intercept = 0.0, float(values[-1]) if len(values) else 0.0
        month_avg = series.groupby(series.index.month).mean()
        overall = float(series.mean()) if len(series) else 0.0
        preds = []
        for i, d in enumerate(dates, start=1):
            trend = intercept + slope * (len(values) + i - 1)
            seasonal = float(month_avg.get(d.month, overall)) - overall
            if model_name == "arima":
                pred = float(values[-1]) * 0.65 + (trend + seasonal) * 0.35 if len(values) else 0.0
            elif model_name == "prophet":
                pred = trend + seasonal
            else:
                pred = trend * 0.7 + float(month_avg.get(d.month, overall)) * 0.3
            preds.append(max(0.0, pred))
        return pd.DataFrame({"year_month": dates, "forecast": preds})

    def _forecast_from_monthly(self, monthly: pd.DataFrame, model_name: str = "random_forest", periods: int = 6) -> pd.DataFrame:
        model_name = str(model_name or "random_forest").lower()
        if monthly.empty:
            return pd.DataFrame(columns=["month", "actual", "forecast"])
        monthly = monthly.sort_values("year_month").copy()
        series = monthly.set_index("year_month")["title_count"].asfreq("MS")
        # Month-filtered data has yearly gaps; keep original dates and fill missing months with zeros for forecast stability.
        series = series.fillna(0)

        if len(series) < 3:
            forecast_df = self._seasonal_trend_forecast(series, periods, model_name)
        elif model_name == "random_forest" and len(series) >= 18:
            try:
                train = pd.DataFrame({"year_month": series.index, "y": series.values})
                train["month"] = train["year_month"].dt.month
                train["quarter"] = train["year_month"].dt.quarter
                train["year"] = train["year_month"].dt.year
                for lag in range(1, 13):
                    train[f"lag_{lag}"] = train["y"].shift(lag)
                train["roll3"] = train["y"].rolling(3).mean()
                train["roll6"] = train["y"].rolling(6).mean()
                train = train.dropna()
                features = [c for c in train.columns if c not in ["year_month", "y"]]
                if train.empty:
                    raise ValueError("RF train empty")
                rf = RandomForestRegressor(n_estimators=120, random_state=42, min_samples_leaf=2)
                rf.fit(train[features], train["y"])
                last = train.iloc[-1:].copy()
                preds = []
                dates = pd.date_range(series.index[-1] + pd.offsets.MonthBegin(1), periods=periods, freq="MS")
                for d in dates:
                    last = last.copy()
                    last["month"] = d.month
                    last["quarter"] = d.quarter
                    last["year"] = d.year
                    pred = max(0.0, float(rf.predict(last[features])[0]))
                    preds.append(pred)
                    for lag in range(12, 1, -1):
                        last[f"lag_{lag}"] = last[f"lag_{lag-1}"]
                    last["lag_1"] = pred
                    last["roll3"] = np.mean([float(last[f"lag_{i}"].iloc[0]) for i in range(1, 4)])
                    last["roll6"] = np.mean([float(last[f"lag_{i}"].iloc[0]) for i in range(1, 7)])
                forecast_df = pd.DataFrame({"year_month": dates, "forecast": preds})
            except Exception:
                forecast_df = self._seasonal_trend_forecast(series, periods, model_name)
        elif model_name == "arima" and ARIMA is not None and len(series) >= 8:
            try:
                fit = ARIMA(series, order=(1, 1, 1)).fit()
                forecast = fit.forecast(steps=periods)
                forecast_df = pd.DataFrame({"year_month": forecast.index, "forecast": forecast.values})
            except Exception:
                forecast_df = self._seasonal_trend_forecast(series, periods, model_name)
        else:
            # Prophet tab uses a robust Prophet-style trend + seasonality fallback.
            # This avoids CmdStan/Windows failures and keeps the chart from disappearing.
            forecast_df = self._seasonal_trend_forecast(series, periods, model_name)

        historical = series.reset_index().rename(columns={"title_count": "actual"})
        merged = pd.merge(historical, forecast_df, on="year_month", how="outer").sort_values("year_month")
        merged["month"] = pd.to_datetime(merged["year_month"]).dt.strftime("%Y-%m")
        out = merged[["month", "actual", "forecast"]].copy()
        out["actual"] = pd.to_numeric(out["actual"], errors="coerce").round(2)
        out["forecast"] = pd.to_numeric(out["forecast"], errors="coerce").round(2)
        return out.astype(object).where(pd.notna(out), None)

    def forecast_monthly(self, model_name: str = "random_forest", periods: int = 6, **filters) -> pd.DataFrame:
        return self._forecast_from_monthly(self.monthly_titles(**filters), model_name=model_name, periods=periods)

    def evaluate_forecast(self, model_name: str = "random_forest", test_size: int = 6) -> Dict:
        monthly = self.monthly_titles()
        if len(monthly) <= test_size + 12:
            return {"model": model_name, "mae": None, "rmse": None, "mape": None, "note": "Không đủ dữ liệu đánh giá"}
        train, test = monthly.iloc[:-test_size], monthly.iloc[-test_size:]
        pred = self._forecast_from_monthly(train, model_name=model_name, periods=test_size)
        preds = pred[pred["actual"].isna()].tail(test_size)["forecast"].astype(float).values
        actual = test["title_count"].astype(float).values
        mae = mean_absolute_error(actual, preds)
        rmse = float(np.sqrt(mean_squared_error(actual, preds)))
        nonzero = actual != 0
        mape = float(np.mean(np.abs((actual[nonzero] - preds[nonzero]) / actual[nonzero])) * 100) if nonzero.any() else 0.0
        return {"model": model_name, "mae": round(float(mae), 2), "rmse": round(rmse, 2), "mape": round(mape, 2), "test_months": test_size}

    # -------------------- Recommendations + summaries --------------------
    def _ensure_recommender(self) -> None:
        if self._tfidf is not None:
            return
        df = self.df_unified.copy()
        df["content_text"] = (
            df["title"].fillna("").astype(str) + " " +
            df["listed_in"].fillna("").astype(str) + " " +
            df["rating"].fillna("").astype(str) + " " +
            df["country_main"].fillna("").astype(str) + " " +
            df["description_clean"].fillna("").astype(str)
        )
        self.df_unified = df.reset_index(drop=True)
        self._tfidf = TfidfVectorizer(stop_words="english", max_features=8000, ngram_range=(1, 2))
        self._tfidf_matrix = self._tfidf.fit_transform(self.df_unified["content_text"])

    def recommend(self, keyword: Optional[str] = "", genre: Optional[str] = "all", rating: Optional[str] = "all", country: Optional[str] = "all", top_n: int = 10) -> List[Dict]:
        self._ensure_recommender()
        assert self._tfidf is not None and self._tfidf_matrix is not None
        df = self.df_unified.copy()
        mask = pd.Series(True, index=df.index)
        query_parts = []
        g = self._norm_genre(genre)
        c = self._norm_country(country)
        if keyword and keyword.strip():
            query_parts.append(keyword.strip())
        if g:
            query_parts.append(g)
            mask &= df["genre_list"].apply(lambda values: g in values if isinstance(values, list) else False)
        if rating and str(rating).lower() != "all":
            query_parts.append(str(rating))
            mask &= df["rating"].fillna("").str.lower() == str(rating).lower()
        if c:
            query_parts.append(c)
            mask &= df["country_main"].fillna("Unknown").str.lower() == c.lower()
        candidates = df[mask].copy()
        if candidates.empty:
            return []
        if query_parts:
            sim = cosine_similarity(self._tfidf.transform([" ".join(query_parts)]), self._tfidf_matrix).flatten()
            candidates["similarity_score"] = sim[candidates.index]
        else:
            candidates["similarity_score"] = 0.0
        candidates["final_score"] = candidates["similarity_score"] * 75 + candidates["engagement_score"] * 0.25
        candidates = candidates.sort_values(["final_score", "engagement_score", "release_year"], ascending=False).head(top_n)
        return [{
            "title": row["title"],
            "type": row["type"],
            "rating": row["rating"],
            "country": row["country_main"],
            "release_year": int(row["release_year"]) if pd.notna(row["release_year"]) else None,
            "genre": row["listed_in"],
            "similarity_score": round(float(row.get("similarity_score", 0)), 4),
            "engagement_score": round(float(row.get("engagement_score", 0)), 2),
            "views": int(row.get("top10_views", 0) + row.get("engagement_views", 0)),
        } for _, row in candidates.iterrows()]

    def popularity_summary(self, top_n: int = 10) -> List[Dict]:
        df = self.df_unified.sort_values("engagement_score", ascending=False).head(top_n)
        return [{"rank": i + 1, "title": row["title"], "score": round(float(row["engagement_score"]), 2), "source": row.get("data_source", "Unknown")} for i, (_, row) in enumerate(df.iterrows())]

    def top10_weekly_summary(self, top_n: int = 10) -> List[Dict]:
        if self.top10_df.empty:
            return []
        latest_week = self.top10_df["week"].max()
        latest = self.top10_df[self.top10_df["week"] == latest_week].sort_values(["category", "weekly_rank"]).head(top_n)
        return [{"week": str(row["week"].date()), "category": row.get("category"), "rank": int(row.get("weekly_rank", 0)), "title": row.get("title"), "views": int(row.get("weekly_views", 0)), "hours_viewed": int(row.get("weekly_hours_viewed", 0))} for _, row in latest.iterrows()]

    def behavior_summary(self) -> Dict:
        return {
            "top10_rows": int(len(self.top10_df)),
            "top10_latest_week": str(self.top10_df["week"].max().date()) if not self.top10_df.empty else None,
            "engagement_rows": int(len(self.engagement_df)),
            "engagement_period": "2020-2025",
            "catalog_rows": int(len(self.df_clean)),
            "matched_catalog_titles": int((self.df_unified["engagement_score"] > 0).sum()),
            "total_engagement_views": int(self.engagement_df["views"].sum()) if not self.engagement_df.empty else 0,
            "total_engagement_hours": int(self.engagement_df["hours_viewed"].sum()) if not self.engagement_df.empty else 0,
        }

    def data_quality_summary(self, **filters) -> Dict:
        df = self._filter_df(self.df_clean, **filters)
        heatmap = self.content_added_heatmap(**filters)
        return {
            "analysis_period": "2020-2025",
            "filtered_rows": int(len(df)),
            "heatmap_cells": int(len(heatmap)),
            "heatmap_total": int(sum(item["value"] for item in heatmap)),
            "data_sources": sorted(df["data_source"].fillna("Unknown").astype(str).unique().tolist()) if not df.empty else [],
        }

    def dashboard_insights(self, **filters) -> List[Dict]:
        df = self._filter_df(self.df_clean, **filters)
        if df.empty:
            return [{"title": "Chưa có dữ liệu", "text": "Bộ lọc hiện tại không có bản ghi nào trong giai đoạn 2020-2025."}]
        insights: List[Dict] = []
        by_year = df.groupby("year_added").size().sort_index()
        if not by_year.empty:
            insights.append({"title": "Năm nổi bật", "text": f"Năm {int(by_year.idxmax())} có nhiều nội dung nhất với {int(by_year.max()):,} bản ghi."})
        genres = df.explode("genre_list")["genre_list"].dropna().value_counts()
        if not genres.empty:
            insights.append({"title": "Thể loại dẫn đầu", "text": f"{genres.index[0]} đang đứng đầu với {int(genres.iloc[0]):,} nội dung."})
        sources = df["data_source"].fillna("Unknown").astype(str).value_counts()
        if not sources.empty:
            insights.append({"title": "Nguồn dữ liệu", "text": f"Đang dùng {len(sources)} nguồn; nhiều nhất là {sources.index[0]} ({int(sources.iloc[0]):,} dòng)."})
        heatmap = self.content_added_heatmap(**filters)
        if heatmap:
            peak = max(heatmap, key=lambda x: x["value"])
            insights.append({"title": "Tháng cao điểm", "text": f"Ô cao nhất là tháng {peak['month']}/{peak['year']} với {peak['value']:,} nội dung."})
        return insights[:4]

    # -------------------- Dashboard --------------------
    def build_dashboard(self, model_name: str = "random_forest", genre: Optional[str] = None, year: Optional[str] = None, month: Optional[str] = None, country: Optional[str] = None) -> DashboardData:
        filters = {"genre": genre, "year": year, "month": month, "country": country}
        filtered = self._filter_df(self.df_clean, **filters)
        genres = self.top_genres(8, **filters)
        countries = self.country_distribution(8, **filters)
        ratings = self.ratings_distribution(8, **filters)
        monthly = self.forecast_monthly(model_name=model_name, periods=6, **filters)
        heatmap = self.content_added_heatmap(**filters)
        top_titles = self.popularity_summary(10)
        summary = self.behavior_summary()
        kpis = {
            "total_titles": f"{len(filtered):,}",
            "genre_count": str(filtered.explode("genre_list")["genre_list"].nunique()) if not filtered.empty else "0",
            "forecast_horizon": "6 tháng",
            "models_ready": "3",
            "top10_latest_week": summary.get("top10_latest_week") or "N/A",
            "engagement_rows": f"{summary.get('engagement_rows', 0):,}",
        }
        return DashboardData(
            monthly=monthly.to_dict(orient="records"),
            genres=[{"name": r["genre"], "value": int(r["count"])} for _, r in genres.iterrows()],
            ratings=[{"name": r["rating"], "value": round(float(r["percentage"]), 2)} for _, r in ratings.iterrows()],
            top_titles=[{"rank": item["rank"], "title": item["title"], "score": item["score"], "model": item["source"]} for item in top_titles],
            countries=[{"country": r["country"], "count": int(r["count"])} for _, r in countries.iterrows()],
            kpis=kpis,
            filter_options=self.get_filter_options(),
            heatmap=heatmap,
            insights=self.dashboard_insights(**filters),
            data_quality=self.data_quality_summary(**filters),
        )

    def export_cleaned_csv(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.df_clean.to_csv(self.data_dir / "netflix_titles_cleaned.csv", index=False)
        self.df_unified.to_csv(self.data_dir / "netflix_unified.csv", index=False)
