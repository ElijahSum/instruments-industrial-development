import importlib
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from dashboard_shared import CSV_COLUMNS

ROOT_DIR = Path(__file__).resolve().parents[1]
SEED_SOURCE = (
    ROOT_DIR / "backend" / "RU_Electricity_Market_PZ_dayahead_price_volume.csv"
)


@pytest.fixture(name="backend_client")
def backend_client_fixture(tmp_path, monkeypatch):
    """Create an isolated backend client backed by temporary CSV files."""
    seed_path = tmp_path / "seed.csv"
    data_path = tmp_path / "data.csv"
    shutil.copyfile(SEED_SOURCE, seed_path)

    monkeypatch.setenv("SEED_DATA_PATH", str(seed_path))
    monkeypatch.setenv("DATA_PATH", str(data_path))

    if "backend.main" in sys.modules:
        del sys.modules["backend.main"]

    module = importlib.import_module("backend.main")
    module = importlib.reload(module)

    with TestClient(module.app) as client:
        yield client, data_path


def test_get_records_initializes_storage(backend_client):
    """Ensure GET initializes the working CSV and returns the dataset."""
    client, data_path = backend_client

    response = client.get("/records")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 45816
    assert payload[0]["id"] == 1
    assert data_path.exists()

    dataframe = pd.read_csv(data_path)
    assert list(dataframe.columns) == CSV_COLUMNS


def test_post_persists_record_and_rejects_duplicate_timestep(backend_client):
    """Ensure POST persists a row and rejects a duplicate timestamp."""
    client, data_path = backend_client
    payload = {
        "timestep": "2011-11-23 00:00",
        "consumption_eur": 72100,
        "consumption_sib": 21450,
        "price_eur": 980.35,
        "price_sib": 615.2,
    }

    create_response = client.post("/records", json=payload)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"] == 45817

    dataframe = pd.read_csv(data_path)
    assert len(dataframe) == 45817
    assert (dataframe["timestep"] == payload["timestep"]).sum() == 1

    duplicate_response = client.post("/records", json=payload)
    assert duplicate_response.status_code == 409


def test_delete_and_validation_errors(backend_client):
    """Ensure validation errors and delete behavior are handled correctly."""
    client, data_path = backend_client

    invalid_response = client.post(
        "/records",
        json={
            "timestep": "2011-11-23 01:00",
            "consumption_eur": -1,
            "consumption_sib": 1,
            "price_eur": 1,
            "price_sib": 1,
        },
    )
    assert invalid_response.status_code == 422

    create_response = client.post(
        "/records",
        json={
            "timestep": "2011-11-23 02:00",
            "consumption_eur": 70000,
            "consumption_sib": 22000,
            "price_eur": 950.1,
            "price_sib": 610.5,
        },
    )
    created_id = create_response.json()["id"]

    delete_response = client.delete(f"/records/{created_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted_id": created_id}

    second_delete = client.delete(f"/records/{created_id}")
    assert second_delete.status_code == 404

    dataframe = pd.read_csv(data_path)
    assert created_id not in set(dataframe["id"].tolist())
