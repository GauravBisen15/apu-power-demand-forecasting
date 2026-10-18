"""Forecasting logic: loads the models and data once, then answers requests."""
import json
from datetime import date as Date

import joblib
import numpy as np
import pandas as pd

from backend import config
from backend.features import add_weather_features, build_features
from backend.holidays import load_holidays
from backend.weather import load_weather30


def _clean(value):
    """Round numbers and turn NaN into None so that it becomes JSON null."""
    return None if pd.isna(value) else round(float(value), 1)


def day_index(day: Date) -> pd.DatetimeIndex:
    """The 48 half-hour timestamps of one day."""
    return pd.date_range(pd.Timestamp(day), periods=48, freq="30min")


class ForecastService:
    def __init__(self):
        self.models = joblib.load(config.MODEL_PATH)
        self.metrics = json.loads(config.METRICS_PATH.read_text())
        self.holidays = load_holidays()

        # Load history, extended with empty rows up to the end of 31 Dec 2017
        load = pd.read_csv(config.LOAD_FILE, index_col="Datetime", parse_dates=True)
        full_index = pd.date_range(load.index.min(), config.LAST_TIMESTAMP, freq="30min")
        self.history = load.reindex(full_index)

        weather30, self.last_day_weather_source = load_weather30()
        self.weather30 = weather30
        self.weather_features = add_weather_features(weather30)

    # ------------------------------------------------------------------ forecast
    def forecast(self, day: Date, target: str, interval: int = 30) -> dict:
        index = day_index(day)
        series = self.history[config.TARGET_COLUMNS[target]]

        entry = self.models[target]
        features = build_features(index, series, self.weather_features, self.holidays)
        predicted = pd.Series(entry["model"].predict(features[entry["features"]]), index=index)
        actual = series.reindex(index)

        if interval == 15:
            # 96 points: linear interpolation of the 30-minute forecast
            fine_index = pd.date_range(index[0], periods=96, freq="15min")
            predicted = predicted.reindex(fine_index).interpolate("time").ffill()
            actual = actual.reindex(fine_index).interpolate("time").ffill()

        has_actual = bool(actual.notna().all())
        rows = [
            {"timestamp": t.strftime("%Y-%m-%dT%H:%M"),
             "forecast_kw": _clean(predicted[t]),
             "actual_kw": _clean(actual[t])}
            for t in predicted.index
        ]

        peak_time = predicted.idxmax()
        summary = {
            "peak_kw": _clean(predicted.max()),
            "peak_time": peak_time.strftime("%H:%M"),
            "lowest_kw": _clean(predicted.min()),
            "lowest_time": predicted.idxmin().strftime("%H:%M"),
            "average_kw": _clean(predicted.mean()),
        }
        if has_actual:
            summary["day_mape_pct"] = round(float(np.mean(np.abs((actual - predicted) / actual)) * 100), 2)

        return {
            "target": target,
            "date": str(day),
            "interval_minutes": interval,
            "unit": "kW",
            "mode": "backtest" if has_actual else "forecast",
            "note": ("Actual load is known for this day. The final model was trained on all of 2017, "
                     "so this comparison is in-sample." if has_actual else
                     "Real forecast: the load data ends on 30 Dec 2017, so no actual load exists for this day."),
            "model_test_mape_pct": self.metrics["test_metrics"][target]["MAPE %"],
            "summary": summary,
            "forecast": rows,
        }

    # ------------------------------------------------------------------- weather
    def weather(self, day: Date) -> dict:
        index = day_index(day)
        data = self.weather30.reindex(index)
        rows = [
            {"timestamp": t.strftime("%Y-%m-%dT%H:%M"),
             "temperature_c": _clean(r.temp_c),
             "humidity_pct": _clean(r.humidity_pct),
             "cloud_cover_pct": _clean(r.cloud_cover_pct),
             "wind_speed_kmh": _clean(r.wind_kmh)}
            for t, r in data.iterrows()
        ]
        source = "Open-Meteo archive (Dhanbad)"
        if str(day) == config.LAST_DATE:
            source += f"; this day: {self.last_day_weather_source}"
        return {
            "date": str(day),
            "location": "Dhanbad, Jharkhand",
            "source": source,
            "interval_minutes": 30,
            "summary": {
                "temperature_min_c": _clean(data["temp_c"].min()),
                "temperature_max_c": _clean(data["temp_c"].max()),
                "humidity_avg_pct": _clean(data["humidity_pct"].mean()),
                "cloud_cover_avg_pct": _clean(data["cloud_cover_pct"].mean()),
            },
            "weather": rows,
        }

    # ------------------------------------------------------------------ holidays
    def holidays_near(self, day: Date, window_days: int = 7) -> dict:
        day_ts = pd.Timestamp(day)
        distance = (self.holidays["date"] - day_ts).dt.days
        nearby = self.holidays[distance.abs() <= window_days]
        rows = [
            {"date": h.date.strftime("%Y-%m-%d"),
             "holiday": h.holiday,
             "category": h.category,
             "weekday": h.weekday,
             "days_from_forecast_date": int((h.date - day_ts).days),
             "on_forecast_date": bool(h.date == day_ts)}
            for h in nearby.itertuples()
        ]
        return {
            "date": str(day),
            "location": "Dhanbad / Jharkhand",
            "window_days": window_days,
            "is_holiday": any(r["on_forecast_date"] for r in rows),
            "holidays": rows,
        }