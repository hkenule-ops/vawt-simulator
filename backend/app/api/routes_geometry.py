from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.design import DesignRecord
from app.schemas.geometry import HybridRotorIn, DesignSaveRequest, DesignOut
from app.geometry.models import (
    HybridRotorGeometry, DarrieusBladeGeometry, SavoniusBucketGeometry, ShaftGeometry,
)

router = APIRouter(prefix="/geometry", tags=["geometry"])


def to_domain(geom_in: HybridRotorIn) -> HybridRotorGeometry:
    return HybridRotorGeometry(
        name=geom_in.name,
        target_power_w=geom_in.target_power_w,
        darrieus=DarrieusBladeGeometry(**geom_in.darrieus.model_dump()),
        savonius=SavoniusBucketGeometry(**geom_in.savonius.model_dump()),
        shaft=ShaftGeometry(**geom_in.shaft.model_dump()),
        rated_wind_speed_ms=geom_in.rated_wind_speed_ms,
        cut_in_wind_speed_ms=geom_in.cut_in_wind_speed_ms,
        cut_out_wind_speed_ms=geom_in.cut_out_wind_speed_ms,
    )


@router.post("/validate", response_model=list[str])
def validate_geometry(geom_in: HybridRotorIn):
    """Run physical sanity checks without saving. Returns a list of warnings (empty = clean)."""
    domain = to_domain(geom_in)
    return domain.validate()


@router.post("/designs", response_model=DesignOut, status_code=201)
def save_design(payload: DesignSaveRequest, db: Session = Depends(get_db)):
    domain = to_domain(payload.geometry)
    warnings = domain.validate()
    record = DesignRecord(
        name=payload.geometry.name,
        geometry_json=payload.geometry.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return DesignOut(id=record.id, geometry=payload.geometry, warnings=warnings)


@router.get("/designs", response_model=list[DesignOut])
def list_designs(db: Session = Depends(get_db)):
    records = db.query(DesignRecord).order_by(DesignRecord.updated_at.desc()).all()
    out = []
    for r in records:
        geom_in = HybridRotorIn(**r.geometry_json)
        out.append(DesignOut(id=r.id, geometry=geom_in, warnings=to_domain(geom_in).validate()))
    return out


@router.get("/designs/{design_id}", response_model=DesignOut)
def get_design(design_id: int, db: Session = Depends(get_db)):
    record = db.query(DesignRecord).filter(DesignRecord.id == design_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Design not found")
    geom_in = HybridRotorIn(**record.geometry_json)
    return DesignOut(id=record.id, geometry=geom_in, warnings=to_domain(geom_in).validate())


@router.delete("/designs/{design_id}", status_code=204)
def delete_design(design_id: int, db: Session = Depends(get_db)):
    record = db.query(DesignRecord).filter(DesignRecord.id == design_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Design not found")
    db.delete(record)
    db.commit()
