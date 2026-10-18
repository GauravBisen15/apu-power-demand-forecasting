"""Dhanbad weather for the API.

The training weather (Open-Meteo, 2017) is saved in data/. The load data ends on
30 Dec 2017, so the forecast for 31 Dec 2017 also needs that day's weather:
we fetch it once from Open-Meteo and cache it. If there is no internet, the
previous day's weather is reused and the response says so.
"""
import pandas as pd
import requests

from backend import config

COLUMN_NAMES = {
    "temperature_2m": "temp_c",
    "relative_humidity_2m": "humidity_pct",
    "cloud_cover": "cloud_cover_pct",
    "wind_speed_10m": "wind_kmh",
}


def _prepare(raw: pd.DataFrame) -> pd.DataFrame:
    """Rename columns and use the time as the index."""
    df = raw.rename(columns=COLUMN_NAMES)
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time")


def _fetch_last_day() -> pd.DataFrame:
    """Download 31 Dec 2017 (hourly) from Open-Meteo."""
    params = {
        "latitude": config.LATITUDE,
        "longitude": config.LONGITUDE,
        "start_date": config.LAST_DATE,
        "end_date": config.LAST_DATE,
        "hourly": ",".join(COLUMN_NAMES),
        "timezone": config.TIMEZONE,
    }
    response = requests.get(config.ARCHIVE_URL, params=params, timeout=15)
    response.raise_for_status()
    return pd.DataFrame(response.json()["hourly"])


def _last_day_hourly(hourly: pd.DataFrame):
    """Return (hourly weather for 31 Dec, text describing its source)."""
    if config.WEATHER_LAST_DAY_FILE.exists():
        raw = pd.read_csv(config.WEATHER_LAST_DAY_FILE)
        return _prepare(raw), "saved Open-Meteo file"
    try:
        raw = _fetch_last_day()
        raw.to_csv(config.WEATHER_LAST_DAY_FILE, index=False)
        return _prepare(raw), "Open-Meteo archive API"
    except Exception:
        # No internet: reuse the previous day, moved forward by 24 hours
        previous_day = hourly.loc["2017-12-30"].copy()
        previous_day.index = previous_day.index + pd.Timedelta(days=1)
        return previous_day, "fallback: copy of the previous day (no internet)"


def load_weather30():
    """Return (30-minute weather for all of 2017, description of the 31 Dec source)."""
    hourly = _prepare(pd.read_csv(config.WEATHER_FILE))
    last_day, source = _last_day_hourly(hourly)
    hourly = pd.concat([hourly, last_day])

    # Hourly -> 30 minutes, exactly as in Notebook 2
    weather30 = hourly.resample("30min").interpolate("time")
    full_index = pd.date_range("2017-01-01 00:00", config.LAST_TIMESTAMP, freq="30min")
    weather30 = weather30.reindex(full_index).interpolate("time").ffill()
    weather30.index.name = "Datetime"
    return weather30, source