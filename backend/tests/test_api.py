import os
import tempfile
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    # Use an isolated temp SQLite DB per test run so tests don't pollute the dev DB.
    tmp_dir = tempfile.mkdtemp()
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_dir}/test.db"
    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.main import app
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_geometry_validate_clean_design(client):
    payload = {
        "name": "Test 300W",
        "target_power_w": 300,
        "darrieus": {"num_blades": 3, "blade_height_m": 1.2, "rotor_radius_m": 0.6, "chord_m": 0.09},
        "savonius": {"num_buckets": 2, "bucket_height_m": 0.9, "bucket_diameter_m": 0.5},
        "shaft": {"length_m": 1.6},
    }
    r = client.post("/api/v1/geometry/validate", json=payload)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_geometry_save_and_retrieve(client):
    payload = {"geometry": {
        "name": "Test 300W",
        "target_power_w": 300,
        "darrieus": {"num_blades": 3, "blade_height_m": 1.2, "rotor_radius_m": 0.6, "chord_m": 0.09},
        "savonius": {"num_buckets": 2, "bucket_height_m": 0.9, "bucket_diameter_m": 0.5},
        "shaft": {"length_m": 1.6},
    }}
    r = client.post("/api/v1/geometry/designs", json=payload)
    assert r.status_code == 201
    design_id = r.json()["id"]

    r2 = client.get(f"/api/v1/geometry/designs/{design_id}")
    assert r2.status_code == 200
    assert r2.json()["geometry"]["name"] == "Test 300W"

    r3 = client.get("/api/v1/geometry/designs")
    assert r3.status_code == 200
    assert len(r3.json()) >= 1

    r4 = client.delete(f"/api/v1/geometry/designs/{design_id}")
    assert r4.status_code == 204

    r5 = client.get(f"/api/v1/geometry/designs/{design_id}")
    assert r5.status_code == 404


def test_cp_lambda_endpoint(client):
    payload = {
        "geometry": {
            "name": "Test 300W",
            "target_power_w": 300,
            "darrieus": {"num_blades": 3, "blade_height_m": 1.2, "rotor_radius_m": 0.6, "chord_m": 0.09},
            "savonius": {"num_buckets": 2, "bucket_height_m": 0.9, "bucket_diameter_m": 0.5},
            "shaft": {"length_m": 1.6},
        },
        "wind_speed_ms": 8.0,
        "tsr_min": 1.0,
        "tsr_max": 4.0,
        "n_points": 10,
    }
    r = client.post("/api/v1/bem/cp-lambda", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) == 10
    assert all(p["system_cp"] < 0.593 for p in body["points"])


def test_power_curve_endpoint(client):
    payload = {
        "geometry": {
            "name": "Test 300W",
            "target_power_w": 300,
            "darrieus": {"num_blades": 3, "blade_height_m": 1.2, "rotor_radius_m": 0.6, "chord_m": 0.09},
            "savonius": {"num_buckets": 2, "bucket_height_m": 0.9, "bucket_diameter_m": 0.5},
            "shaft": {"length_m": 1.6},
        },
        "wind_speeds_ms": [3, 5, 8, 10, 12],
    }
    r = client.post("/api/v1/bem/power-curve", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert len(body["curve"]) == 5
    assert body["rated_power_w"] > 0
