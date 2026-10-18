"""Localized holidays for Dhanbad / Jharkhand (compiled in Notebook 2)."""
import pandas as pd

from backend import config

CATEGORIES = ["national", "festival", "tribal", "industrial"]


def load_holidays() -> pd.DataFrame:
    holidays = pd.read_csv(config.HOLIDAY_FILE, parse_dates=["date"])
    return holidays


def holiday_flags(index: pd.DatetimeIndex, holidays: pd.DataFrame) -> pd.DataFrame:
    """Holiday features for every timestamp (same definition as Notebook 2)."""
    dates = pd.Series(index.normalize(), index=index)
    flags = pd.DataFrame(index=index)

    flags["is_holiday"] = dates.isin(holidays["date"]).astype(int)
    for category in CATEGORIES:
        category_dates = holidays.loc[holidays["category"] == category, "date"]
        flags["is_" + category] = dates.isin(category_dates).astype(int)

    flags["is_day_before_holiday"] = dates.isin(holidays["date"] - pd.Timedelta(days=1)).astype(int)
    flags["is_day_after_holiday"] = dates.isin(holidays["date"] + pd.Timedelta(days=1)).astype(int)
    return flags