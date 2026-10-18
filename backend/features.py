"""Feature engineering for the API. Mirrors Notebook 2 exactly, so that the model
receives the same inputs at forecast time as it saw during training."""
import numpy as np
import pandas as pd

from backend.holidays import holiday_flags


def add_weather_features(weather30: pd.DataFrame) -> pd.DataFrame:
    """Rolling temperature features, computed once on the whole weather series."""
    out = weather30.copy()
    out["temp_roll_3h"] = out["temp_c"].rolling(6, min_periods=1).mean()
    out["temp_roll_24h"] = out["temp_c"].rolling(48, min_periods=1).mean()
    out["temp_x_humidity"] = out["temp_c"] * out["humidity_pct"] / 100
    return out


def lag_features(series: pd.Series) -> pd.DataFrame:
    """Past load values. The smallest lag is 24 hours, so a 24-hour-ahead
    forecast never needs data that would not yet exist (no data leakage)."""
    return pd.DataFrame({
        "lag_48": series.shift(48),                                 # same time yesterday
        "lag_96": series.shift(96),                                 # two days ago
        "lag_336": series.shift(336),                               # same time last week
        "mean_prev_24h": series.shift(48).rolling(48).mean(),       # average of the previous 24 h
    })


def calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    df = pd.DataFrame(index=index)
    df["block"] = index.hour * 2 + index.minute // 30
    df["dayofweek"] = index.dayofweek
    df["month"] = index.month
    df["dayofyear"] = index.dayofyear
    df["is_weekend"] = (index.dayofweek >= 5).astype(int)

    # Cyclical encoding: 23:30 and 00:00 are neighbours, December and January too
    df["block_sin"] = np.sin(2 * np.pi * df["block"] / 48)
    df["block_cos"] = np.cos(2 * np.pi * df["block"] / 48)
    df["dow_sin"] = np.sin(2 * np.pi * df["dayofweek"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dayofweek"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df


def build_features(index, load_history, weather_features, holidays) -> pd.DataFrame:
    """All model inputs for the given timestamps."""
    features = calendar_features(index)
    features = features.join(holiday_flags(index, holidays))
    features = features.join(weather_features.reindex(index))
    features = features.join(lag_features(load_history).reindex(index))
    return features