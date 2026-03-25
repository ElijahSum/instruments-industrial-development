import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from threading import RLock

import pandas as pd
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator

from dashboard_shared import CSV_COLUMNS, DATA_COLUMNS, DATETIME_FORMAT

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = BACKEND_DIR / "data.csv"
DEFAULT_SEED_PATH = (
    BACKEND_DIR / "RU_Electricity_Market_PZ_dayahead_price_volume.csv"
)
NUMERIC_COLUMNS = DATA_COLUMNS[1:]
WRITE_LOCK = RLock()


def _resolve_path(env_name: str, default: Path) -> Path:
    raw_value = os.getenv(env_name)
    if not raw_value:
        return default

    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate
    return (BACKEND_DIR / candidate).resolve()


DATA_PATH = _resolve_path("DATA_PATH", DEFAULT_DATA_PATH)
SEED_DATA_PATH = _resolve_path("SEED_DATA_PATH", DEFAULT_SEED_PATH)


def _get_cors_origins() -> list[str]:
    """Build the allowed CORS origins list from the environment."""
    raw_value = os.getenv("CORS_ORIGINS")
    if raw_value:
        origins = [
            origin.strip()
            for origin in raw_value.split(",")
            if origin.strip()
        ]
        if origins:
            return origins

    return [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]


class RecordCreate(BaseModel):
    timestep: datetime
    consumption_eur: float
    consumption_sib: float
    price_eur: float
    price_sib: float

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestep": "2011-11-23 00:00",
                "consumption_eur": 72100,
                "consumption_sib": 21450,
                "price_eur": 980.35,
                "price_sib": 615.20,
            }
        }
    )

    @field_validator("timestep", mode="before")
    @classmethod
    def validate_timestep(cls, value: object) -> datetime:
        """Accept only the assignment timestamp format."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.strptime(value, DATETIME_FORMAT)
            except ValueError as exc:
                raise ValueError(
                    f"timestep must use the format {DATETIME_FORMAT}"
                ) from exc
        raise ValueError("timestep must be a datetime string")

    @field_validator(*NUMERIC_COLUMNS)
    @classmethod
    def validate_non_negative(cls, value: float) -> float:
        """Reject negative numeric values in incoming payloads."""
        if value < 0:
            raise ValueError("value must be non-negative")
        return float(value)


class RecordResponse(BaseModel):
    id: int
    timestep: str
    consumption_eur: float
    consumption_sib: float
    price_eur: float
    price_sib: float


app = FastAPI(
    title="RU Electricity Market Dashboard API",
    version="1.0.0",
    description="CRUD API for the electricity market dashboard assignment.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the CSV shape and normalize types/order."""
    missing_columns = [
        column for column in DATA_COLUMNS if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"Missing columns in CSV: {', '.join(missing_columns)}"
        )

    unexpected_columns = [
        column for column in df.columns if column not in set(CSV_COLUMNS)
    ]
    if unexpected_columns:
        raise ValueError(
            f"Unexpected columns in CSV: {', '.join(unexpected_columns)}"
        )

    normalized = df.copy()
    if "id" not in normalized.columns:
        normalized.insert(0, "id", range(1, len(normalized) + 1))

    normalized["id"] = pd.to_numeric(
        normalized["id"], errors="raise"
    ).astype("int64")
    if (normalized["id"] < 1).any():
        raise ValueError("id values must be positive integers")
    if normalized["id"].duplicated().any():
        raise ValueError("Duplicate id values found in CSV")

    normalized["timestep"] = pd.to_datetime(
        normalized["timestep"], format=DATETIME_FORMAT, errors="raise"
    )
    if normalized["timestep"].duplicated().any():
        raise ValueError("Duplicate timestep values found in CSV")

    for column in NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(
            normalized[column], errors="raise"
        )
        if (normalized[column] < 0).any():
            raise ValueError(f"{column} contains negative values")

    normalized = normalized.sort_values(
        ["timestep", "id"]
    ).reset_index(drop=True)
    normalized["timestep"] = normalized["timestep"].dt.strftime(
        DATETIME_FORMAT
    )
    return normalized[CSV_COLUMNS]


def _read_csv(path: Path) -> pd.DataFrame:
    """Read CSV data and convert parser issues into ValueError."""
    try:
        return pd.read_csv(path)
    except FileNotFoundError as exc:
        raise ValueError(f"CSV file not found: {path.name}") from exc
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"CSV file is empty: {path.name}") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"CSV file is corrupted: {path.name}") from exc


def _write_dataframe(df: pd.DataFrame) -> None:
    """Persist the dataframe atomically to the configured CSV path."""
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=DATA_PATH.parent,
        suffix=".csv",
    ) as temporary_file:
        temp_path = Path(temporary_file.name)
        df.to_csv(temporary_file, index=False)

    temp_path.replace(DATA_PATH)


def _ensure_storage_ready() -> None:
    """Create the normalized working CSV if only seed data exists."""
    with WRITE_LOCK:
        source_path = DATA_PATH if DATA_PATH.exists() else SEED_DATA_PATH
        if not source_path.exists():
            raise ValueError(
                (
                    "No source CSV found. Expected backend/data.csv or "
                    "the seed CSV file."
                )
            )

        raw_dataframe = _read_csv(source_path)
        normalized = _normalize_dataframe(raw_dataframe)
        needs_write = (
            source_path != DATA_PATH
            or not DATA_PATH.exists()
            or "id" not in raw_dataframe.columns
            or list(raw_dataframe.columns) != CSV_COLUMNS
        )
        if needs_write:
            _write_dataframe(normalized)


def _load_records() -> pd.DataFrame:
    """Load the persisted CSV as a validated dataframe."""
    _ensure_storage_ready()
    return _normalize_dataframe(_read_csv(DATA_PATH))


def _serialize_records(df: pd.DataFrame) -> list[dict]:
    """Convert dataframe rows into API response dictionaries."""
    records: list[dict] = []
    for record in df.to_dict(orient="records"):
        records.append(RecordResponse.model_validate(record).model_dump())
    return records


def _storage_error(exc: Exception) -> HTTPException:
    logger.exception("Storage operation failed", exc_info=exc)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to read or write the CSV storage.",
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    """Return consistent JSON responses for unhandled exceptions."""
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    logger.exception("Unhandled server error", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )


@app.get("/")
def root() -> dict[str, str]:
    """Return a simple service description."""
    return {"message": "RU Electricity Market Dashboard API"}


@app.get("/ping")
def ping() -> dict[str, str]:
    """Return a health-check response for monitoring."""
    return {"status": "ok"}


@app.get("/records", response_model=list[RecordResponse])
def get_records() -> list[dict]:
    """Return all records stored in the CSV file."""
    try:
        dataframe = _load_records()
    except ValueError as exc:
        raise _storage_error(exc) from exc

    return _serialize_records(dataframe)


@app.post(
    "/records",
    response_model=RecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_record(record: RecordCreate) -> dict:
    """Add a new record and persist it to CSV storage."""
    try:
        with WRITE_LOCK:
            dataframe = _load_records()
            normalized_timestep = record.timestep.strftime(DATETIME_FORMAT)
            if normalized_timestep in set(dataframe["timestep"].tolist()):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A record with this timestep already exists.",
                )

            next_id = 1 if dataframe.empty else int(dataframe["id"].max()) + 1
            new_row = {
                "id": next_id,
                "timestep": normalized_timestep,
                "consumption_eur": record.consumption_eur,
                "consumption_sib": record.consumption_sib,
                "price_eur": record.price_eur,
                "price_sib": record.price_sib,
            }

            updated = pd.concat(
                [dataframe, pd.DataFrame([new_row])], ignore_index=True
            )
            updated = _normalize_dataframe(updated)
            _write_dataframe(updated)
    except ValueError as exc:
        raise _storage_error(exc) from exc

    return RecordResponse.model_validate(new_row).model_dump()


@app.delete("/records/{record_id}")
def delete_record(record_id: int) -> dict[str, int]:
    """Delete a record by id and persist the updated CSV."""
    try:
        with WRITE_LOCK:
            dataframe = _load_records()
            if record_id not in set(dataframe["id"].tolist()):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Record with id={record_id} was not found.",
                )

            updated = dataframe[dataframe["id"] != record_id].reset_index(
                drop=True
            )
            _write_dataframe(updated)
    except ValueError as exc:
        raise _storage_error(exc) from exc

    return {"deleted_id": record_id}
