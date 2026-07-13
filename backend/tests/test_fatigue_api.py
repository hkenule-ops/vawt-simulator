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


def test_analyze_fatigue_endpoint(client):
    r = client.post("/api/v1/fatigue/analyze-blade", json={
        "geometry": SAMPLE_GEOMETRY, "material": "CFRP_UD", "ply_material": "CFRP_UD_PLY",
        "operating_tsr": 2.25, "weibull_k": 2.0, "weibull_c": 7.0,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["estimated_life_years"] > 0
    assert body["total_cycles_per_year"] > 0
    assert len(body["wind_bins_ms"]) == len(body["damage_by_bin"])


def test_analyze_fatigue_unknown_material_returns_400(client):
    r = client.post("/api/v1/fatigue/analyze-blade", json={
        "geometry": SAMPLE_GEOMETRY, "material": "UNOBTANIUM", "ply_material": "CFRP_UD_PLY",
        "operating_tsr": 2.25,
    })
    assert r.status_code == 400
