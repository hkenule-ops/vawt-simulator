from sqlalchemy import Column, Integer, String, JSON, DateTime, func
from app.core.database import Base


class DesignRecord(Base):
    """
    Persisted rotor design. Geometry is stored as JSON (validated on the way
    in/out via the Pydantic schemas in app.schemas.geometry) rather than
    normalised into many columns -- geometry parameters will keep growing
    through later phases (composites layup, FEA mesh settings, etc.) and a
    flexible JSON column avoids a migration every time a new field is added.
    Results of expensive analyses (BEM curves, CFD, FEA) are cached the same
    way, keyed by design id, in later phases.
    """
    __tablename__ = "designs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    geometry_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
