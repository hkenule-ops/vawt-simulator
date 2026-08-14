from pydantic import BaseModel, Field


class DarrieusBladeIn(BaseModel):
    num_blades: int = Field(3, ge=2, le=6)
    blade_height_m: float = Field(1.2, gt=0, le=10)
    rotor_radius_m: float = Field(0.6, gt=0, le=10)
    chord_m: float = Field(0.09, gt=0, le=2)
    airfoil: str = "NACA0018"
    twist_angle_deg: float = 0.0
    helical_twist_deg: float = Field(0.0, ge=0, le=360)
    blade_thickness_ratio: float = Field(0.18, gt=0, le=0.4)


class SavoniusBucketIn(BaseModel):
    num_buckets: int = Field(2, ge=2, le=3)
    bucket_height_m: float = Field(0.9, gt=0, le=10)
    bucket_diameter_m: float = Field(0.5, gt=0, le=5)
    overlap_ratio: float = Field(0.15, ge=0, le=0.5)
    end_plate_diameter_m: float = Field(0.55, gt=0, le=5)


class ShaftIn(BaseModel):
    length_m: float = Field(1.6, gt=0, le=15)
    outer_diameter_mm: float = Field(40.0, gt=0, le=500)
    wall_thickness_mm: float = Field(4.0, gt=0, le=50)
    material: str = "AISI_304_Stainless"


class GeneratorIn(BaseModel):
    pole_pairs: int = Field(8, ge=1, le=60)
    phase_resistance_ohm: float = Field(0.15, gt=0, le=50)
    synchronous_reactance_ohm: float = Field(0.08, ge=0, le=50)
    torque_constant_nm_per_a: float = Field(0.8, gt=0, le=20)
    voltage_constant_v_per_rad_s: float | None = Field(None, gt=0, le=20)
    load_resistance_ohm: float = Field(3.0, gt=0, le=500)
    core_loss_coefficient: float = Field(0.01, ge=0, le=5)
    cogging_torque_peak_nm: float = Field(0.15, ge=0, le=50)
    slot_count: int = Field(24, ge=3, le=180)


class TowerIn(BaseModel):
    height_m: float = Field(1.0, gt=0, le=100)
    reference_height_m: float = Field(10.0, gt=0, le=200)
    wind_shear_exponent: float = Field(0.20, ge=0, le=0.6)
    apply_wind_shear: bool = False


class HybridRotorIn(BaseModel):
    name: str = "Hybrid VAWT"
    target_power_w: float = Field(300.0, gt=0, le=100000)
    darrieus: DarrieusBladeIn = DarrieusBladeIn()
    savonius: SavoniusBucketIn = SavoniusBucketIn()
    shaft: ShaftIn = ShaftIn()
    generator: GeneratorIn = GeneratorIn()
    tower: TowerIn = TowerIn()
    rated_wind_speed_ms: float = Field(10.0, gt=0, le=60)
    cut_in_wind_speed_ms: float = Field(3.0, gt=0, le=20)
    cut_out_wind_speed_ms: float = Field(20.0, gt=0, le=80)


class DesignSaveRequest(BaseModel):
    geometry: HybridRotorIn


class DesignOut(BaseModel):
    id: int
    geometry: HybridRotorIn
    warnings: list[str]

    class Config:
        from_attributes = True