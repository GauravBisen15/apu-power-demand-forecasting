"""Central settings: file paths, location and the date range the API can serve."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
FRONTEND_DIR = BASE_DIR / "frontend"

MODEL_PATH = MODEL_DIR / "forecast_models.pkl"
METRICS_PATH = MODEL_DIR / "metrics.json"
LOAD_FILE = DATA_DIR / "load_clean_30min.csv"
WEATHER_FILE = DATA_DIR / "weather_dhanbad_2017_hourly.csv"
WEATHER_LAST_DAY_FILE = DATA_DIR / "weather_dhanbad_2017-12-31.csv"
HOLIDAY_FILE = DATA_DIR / "holidays_dhanbad_2017.csv"

# Dhanbad, Jharkhand
LATITUDE = 23.80
LONGITUDE = 86.43
TIMEZONE = "Asia/Kolkata"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Forecast target name -> column in the load file
TARGET_COLUMNS = {
    "Total_Load": "Total_Load",
    "F1": "F1_132KV_PowerConsumption",
    "F2": "F2_132KV_PowerConsumption",
    "F3": "F3_132KV_PowerConsumption",
}

# The first day that has a full week of history for the 7-day lag, and the
# first day after the load data ends (30 Dec 2017), which is a real forecast.
FIRST_DATE = "2017-01-08"
LAST_DATE = "2017-12-31"
LAST_TIMESTAMP = "2017-12-31 23:30"