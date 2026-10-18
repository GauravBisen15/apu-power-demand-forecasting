"""FastAPI application: forecast, weather and holiday endpoints."""
from datetime import date as Date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import config
from backend.service import ForecastService

app = FastAPI(
    title="APU Power Demand Forecasting API",
    description="24-hour load forecast for Apex Power & Utilities, with Dhanbad weather and local holidays.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

service = ForecastService()   # models and data are loaded once, when the server starts


def check_date(day: Date) -> Date:
    """Only dates with a full set of lag data can be forecast."""
    if not (config.FIRST_DATE <= str(day) <= config.LAST_DATE):
        raise HTTPException(
            status_code=400,
            detail=f"date must be between {config.FIRST_DATE} and {config.LAST_DATE}",
        )
    return day


@app.get("/health")
def health():
    """Health check: confirms the server is running."""
    return {"status": "ok", "message": "APU forecasting API is running"}


@app.get("/meta")
def meta():
    """What the API can serve: date range, targets and model accuracy."""
    return {
        "first_date": config.FIRST_DATE,
        "last_date": config.LAST_DATE,
        "default_date": config.LAST_DATE,
        "targets": list(config.TARGET_COLUMNS),
        "selected_feature_set": service.metrics["selected_feature_set"],
        "test_metrics": service.metrics["test_metrics"],
        "baseline_best_mape_pct": service.metrics["baseline_best_mape"],
    }


@app.get("/forecast")
def forecast(
    date: Date = Query(Date.fromisoformat(config.LAST_DATE), description="Day to forecast (YYYY-MM-DD)"),
    target: str = Query("Total_Load", description="Total_Load, F1, F2 or F3"),
    interval: int = Query(30, description="30 = 48 blocks, 15 = 96 blocks (interpolated)"),
):
    """Forecast for the 24 hours of the given day."""
    check_date(date)
    if target not in config.TARGET_COLUMNS:
        raise HTTPException(status_code=400, detail=f"target must be one of {list(config.TARGET_COLUMNS)}")
    if interval not in (30, 15):
        raise HTTPException(status_code=400, detail="interval must be 30 or 15")
    return service.forecast(date, target, interval)


@app.get("/weather")
def weather(date: Date = Query(Date.fromisoformat(config.LAST_DATE), description="Day (YYYY-MM-DD)")):
    """Dhanbad weather (temperature, humidity, cloud cover, wind) for the forecast day."""
    check_date(date)
    return service.weather(date)


@app.get("/holidays")
def holidays(
    date: Date = Query(Date.fromisoformat(config.LAST_DATE), description="Day (YYYY-MM-DD)"),
    window_days: int = Query(7, ge=0, le=30, description="Also list holidays this many days before/after"),
):
    """Localized holidays on, and around, the forecast day."""
    check_date(date)
    return service.holidays_near(date, window_days)
# The dashboard is served by the same app, so the page and the API share one address
app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="dashboard")