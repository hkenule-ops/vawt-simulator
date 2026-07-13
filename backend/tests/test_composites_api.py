import os
import tempfile
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    tmp_dir = tempfile.mkdtemp()
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_dir}/test.db"
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    with TestClient(app) as c:
        yield c


SAMPLE_GEOMETRY = {
    "name": "Test 300W",
    "target_power_w": 300,
    "darrieus": {"num_blades": 3, "blade_height_m": 1.2, "rotor_radius_m": 0.6, "chord_m": 0.09,
                 "airfoil": "NACA0018", "twist_angle_deg": 0, "helical_twist_deg": 0, "blade_thickness_ratio": 0.18},
    "savonius": {"num_buckets": 2, "bucket_height_m": 0.9, "bucket_diameter_m": 0.5,
                 "overlap_ratio": 0.15, "end_plate_diameter_m": 0.55},
    "shaft": {"length_m": 1.6, "outer_diameter_mm": 40, "wall_thickness_mm": 4, "material": "AISI_304_Stainless"},
    "rated_wind_speed_ms": 10, "cut_in_wind_speed_ms": 3, "cut_out_wind_speed_ms": 20,
}


def test_list_ply_materials(client):
    r = client.get("/api/v1/composites/ply-materials")
    assert r.status_code == 200
    keys = [m["key"] for m in r.json()]
    assert "CFRP_UD_PLY" in keys
    assert "GFRP_UD_PLY" in keys


def test_laminate_endpoint_quasi_isotropic(client):
    r = client.post("/api/v1/composites/laminate", json={
        "ply_material": "CFRP_UD_PLY", "angles_deg": [0, 45, -45, 90, 90, -45, 45, 0],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ex_pa"] == pytest.approx(body["ey_pa"], rel=1e-6)


def test_optimize_spar_endpoint(client):
    r = client.post("/api/v1/composites/optimize-spar", json={
        "geometry": SAMPLE_GEOMETRY, "material": "CFRP_UD_PLY",
        "wind_speed_ms": 12.0, "tip_speed_ratio": 2.25, "target_safety_factor": 1.5,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["feasible"] is True
    assert body["safety_factor"] >= 1.5


def test_compare_materials_endpoint(client):
    r = client.post("/api/v1/composites/compare-materials", json={
        "geometry": SAMPLE_GEOMETRY, "wind_speed_ms": 12.0, "tip_speed_ratio": 2.25,
        "target_safety_factor": 1.5,
    })
    assert r.status_code == 200
    body = r.json()
    assert "cfrp" in body and "gfrp" in body
    assert body["cfrp"]["safety_factor"] > 0
    assert body["gfrp"]["safety_factor"] > 0
