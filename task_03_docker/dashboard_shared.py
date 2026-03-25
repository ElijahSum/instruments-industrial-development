"""Shared constants used by the dashboard services and tests."""

DATETIME_FORMAT = "%Y-%m-%d %H:%M"
DATA_COLUMNS = [
    "timestep",
    "consumption_eur",
    "consumption_sib",
    "price_eur",
    "price_sib",
]
CSV_COLUMNS = ["id", *DATA_COLUMNS]
