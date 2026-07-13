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


def test_report_docx_endpoint(client):
    r = client.post("/api/v1/reporting/docx", json={"geometry": SAMPLE_GEOMETRY})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(r.content) > 5000


def test_report_xlsx_endpoint(client):
    r = client.post("/api/v1/reporting/xlsx", json={"geometry": SAMPLE_GEOMETRY})
    assert r.status_code == 200
    assert len(r.content) > 1000


def test_report_pdf_endpoint(client):
    r = client.post("/api/v1/reporting/pdf", json={"geometry": SAMPLE_GEOMETRY})
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"


def test_report_csv_endpoint(client):
    r = client.post("/api/v1/reporting/csv", json={"geometry": SAMPLE_GEOMETRY})
    assert r.status_code == 200
    assert b"Peak Cp" in r.content


def test_report_unknown_material_returns_400(client):
    r = client.post("/api/v1/reporting/pdf", json={"geometry": SAMPLE_GEOMETRY, "material": "UNOBTANIUM"})
    assert r.status_code == 400


def test_validation_run_checks_endpoint(client):
    r = client.post("/api/v1/validation/run-checks", json={"geometry": SAMPLE_GEOMETRY})
    assert r.status_code == 200
    body = r.json()
    assert body["n_total"] == 6
    assert len(body["checks"]) == 6


def test_validation_unknown_material_returns_400(client):
    r = client.post("/api/v1/validation/run-checks", json={"geometry": SAMPLE_GEOMETRY, "material": "UNOBTANIUM"})
    assert r.status_code == 400
