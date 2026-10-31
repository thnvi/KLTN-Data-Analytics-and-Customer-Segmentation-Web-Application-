from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .data_pipeline import NetflixAnalyticsService

app = FastAPI(title="Netflix Trend Dashboard API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service: NetflixAnalyticsService | None = None


@app.on_event("startup")
def startup_event() -> None:
    global service
    service = NetflixAnalyticsService(data_dir=Path(__file__).resolve().parents[1] / "data")
    service.export_cleaned_csv()


def _svc() -> NetflixAnalyticsService:
    if service is None:
        raise HTTPException(status_code=500, detail="Backend chưa nạp dữ liệu. Kiểm tra folder backend/data.")
    return service


@app.get("/")
def root() -> dict:
    return {
        "message": "Netflix Trend Dashboard API is running",
        "version": "3.0.0",
        "analysis_period": "2020-2025",
        "main_endpoints": ["/api/health", "/api/dashboard", "/api/heatmap", "/api/evaluation", "/api/recommend"],
    }


@app.get("/api/health")
def health() -> dict:
    svc = _svc()
    return {
        "status": "ok",
        "analysis_period": "2020-2025",
        "rows": len(svc.df_clean),
        "heatmap_cells": len(svc.content_added_heatmap()),
        "heatmap_total": sum(item["value"] for item in svc.content_added_heatmap()),
    }


@app.get("/api/dashboard")
def get_dashboard(
    model: Literal["random_forest", "prophet", "arima"] = Query(default="random_forest"),
    genre: Optional[str] = Query(default="all"),
    year: Optional[str] = Query(default="all"),
    month: Optional[str] = Query(default="all"),
    country: Optional[str] = Query(default="all"),
) -> dict:
    svc = _svc()
    dashboard = svc.build_dashboard(model_name=model, genre=genre, year=year, month=month, country=country)
    return {
        "monthly": dashboard.monthly,
        "genres": dashboard.genres,
        "ratings": dashboard.ratings,
        "topTitles": dashboard.top_titles,
        "countries": dashboard.countries,
        "kpis": dashboard.kpis,
        "filterOptions": dashboard.filter_options,
        "heatmap": dashboard.heatmap,
        "insights": dashboard.insights,
        "dataQuality": dashboard.data_quality,
    }


@app.get("/api/forecast")
def get_forecast(
    model: Literal["random_forest", "prophet", "arima"] = Query(default="random_forest"),
    genre: Optional[str] = Query(default="all"),
    year: Optional[str] = Query(default="all"),
    month: Optional[str] = Query(default="all"),
    country: Optional[str] = Query(default="all"),
) -> list[dict]:
    svc = _svc()
    return svc.forecast_monthly(model_name=model, genre=genre, year=year, month=month, country=country).to_dict(orient="records")


@app.get("/api/heatmap")
def get_heatmap(
    genre: Optional[str] = Query(default="all"),
    year: Optional[str] = Query(default="all"),
    month: Optional[str] = Query(default="all"),
    country: Optional[str] = Query(default="all"),
) -> list[dict]:
    svc = _svc()
    return svc.content_added_heatmap(genre=genre, year=year, month=month, country=country)


@app.get("/api/evaluation")
def get_evaluation() -> dict:
    svc = _svc()
    return {
        "prophet": svc.evaluate_forecast("prophet"),
        "arima": svc.evaluate_forecast("arima"),
        "random_forest": svc.evaluate_forecast("random_forest"),
    }


@app.get("/api/recommend")
def recommend_titles(
    keyword: Optional[str] = Query(default=""),
    genre: Optional[str] = Query(default="all"),
    rating: Optional[str] = Query(default="all"),
    country: Optional[str] = Query(default="all"),
    top_n: int = Query(default=10, ge=1, le=50),
) -> list[dict]:
    svc = _svc()
    return svc.recommend(keyword=keyword, genre=genre, rating=rating, country=country, top_n=top_n)


@app.get("/api/popularity")
def get_popularity(top_n: int = Query(default=10, ge=1, le=50)) -> list[dict]:
    return _svc().popularity_summary(top_n=top_n)


@app.get("/api/top10-weekly")
def get_top10_weekly(top_n: int = Query(default=10, ge=1, le=40)) -> list[dict]:
    return _svc().top10_weekly_summary(top_n=top_n)


@app.get("/api/behavior-summary")
def get_behavior_summary() -> dict:
    return _svc().behavior_summary()


@app.get("/api/genres")
def get_genres(
    genre: Optional[str] = Query(default="all"),
    year: Optional[str] = Query(default="all"),
    month: Optional[str] = Query(default="all"),
    country: Optional[str] = Query(default="all"),
) -> list[dict]:
    return _svc().top_genres(10, genre=genre, year=year, month=month, country=country).to_dict(orient="records")


@app.get("/api/countries")
def get_countries(
    genre: Optional[str] = Query(default="all"),
    year: Optional[str] = Query(default="all"),
    month: Optional[str] = Query(default="all"),
    country: Optional[str] = Query(default="all"),
) -> list[dict]:
    return _svc().country_distribution(10, genre=genre, year=year, month=month, country=country).to_dict(orient="records")
