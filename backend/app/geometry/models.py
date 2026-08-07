"""
Geometry data models for the Hybrid Darrieus-Savonius VAWT.

These are plain, validated dataclasses (wrapped as Pydantic schemas at the API
boundary in app/schemas). Keeping geometry as simple dataclasses here means the
aero, structural, and FEA modules in later phases can all import from a single
source of truth without depending on FastAPI/Pydantic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import math


@dataclass
class DarrieusBladeGeometry:
    """A single straight/helical Darrieus blade."""
    num_blades: int = 3
    blade_height_m: float = 1.2          # H
    rotor_radius_m: float = 0.6          # R (swept radius)
    chord_m: float = 0.09                # c
    airfoil: str = "NACA0018"
    twist_angle_deg: float = 0.0
    helical_twist_deg: float = 0.0       # total helical sweep top-to-bottom
    blade_thickness_ratio: float = 0.18  # t/c, informational (matches NACA00xx)

    @property
    def swept_area_m2(self) -> float:
        return 2.0 * self.rotor_radius_m * self.blade_height_m

    @property
    def solidity(self) -> float:
        """Classic Darrieus solidity sigma = N*c / R"""
        return self.num_blades * self.chord_m / self.rotor_radius_m


@dataclass
class BladeSpanStation:
    """
    One spanwise element of a discretised Darrieus blade, root (index 0) to
    tip (index n-1). This is the single source of truth for how twist/helical
    parameters are distributed along the span -- the aero (BEM), CFD
    (STL export), and (future) structural modules all discretise the blade
    the same way by calling `spanwise_stations()` below, so a twisted/helical
    blade always means the same physical shape everywhere in the platform.
    """
    span_fraction: float       # s in [0,1], root=0, tip=1 (station midpoint)
    height_m: float            # height of this element (blade_height_m / n_stations)
    z_start_m: float           # element's start height above the root
    z_end_m: float             # element's end height above the root
    local_twist_deg: float     # local geometric pitch/twist relative to root chord
    local_azimuth_offset_deg: float  # local helical sweep relative to the root


def spanwise_stations(geom: "DarrieusBladeGeometry", n_stations: int = 1) -> List[BladeSpanStation]:
    """
    Discretise a (possibly twisted/helical) blade into `n_stations` equal-
    height elements from root to tip.

    Convention (documented here once, relied on everywhere else):
      - `twist_angle_deg` is the TOTAL geometric twist from root to tip,
        distributed linearly along the span (root sees 0 deg local twist,
        the tip sees the full `twist_angle_deg`). This is the standard
        "linear twist distribution" convention used for research-grade wind
        turbine blades.
      - `helical_twist_deg` is the TOTAL azimuthal sweep from root to tip,
        also distributed linearly, giving the classic helical/"eggbeater"
        Darrieus shape (a straight blade is the degenerate helical_twist_deg=0
        case). Physically this rotates each spanwise station's instantaneous
        blade-fixed azimuth relative to the root by that amount.

    With n_stations=1 and both angles at 0 (the defaults), this returns a
    single station spanning the full blade height with zero twist/offset --
    i.e. exactly the straight-blade behaviour the rest of the platform
    already assumed, so existing callers are unaffected unless they opt in.
    """
    n = max(1, int(n_stations))
    H = geom.blade_height_m
    dz = H / n
    stations = []
    for i in range(n):
        z0, z1 = i * dz, (i + 1) * dz
        s = (z0 + z1) / 2.0 / H if H > 0 else 0.0
        stations.append(BladeSpanStation(
            span_fraction=s,
            height_m=dz,
            z_start_m=z0,
            z_end_m=z1,
            local_twist_deg=geom.twist_angle_deg * s,
            local_azimuth_offset_deg=geom.helical_twist_deg * s,
        ))
    return stations


@dataclass
class SavoniusBucketGeometry:
    """Savonius rotor nested on the same shaft (drives low-TSR startup torque)."""
    num_buckets: int = 2
    bucket_height_m: float = 0.9
    bucket_diameter_m: float = 0.5       # d, single bucket diameter
    overlap_ratio: float = 0.15          # e/d
    end_plate_diameter_m: float = 0.55

    @property
    def rotor_diameter_m(self) -> float:
        """Overall Savonius rotor diameter D = 2d - e"""
        e = self.overlap_ratio * self.bucket_diameter_m
        return 2 * self.bucket_diameter_m - e

    @property
    def swept_area_m2(self) -> float:
        return self.rotor_diameter_m * self.bucket_height_m


@dataclass
class ShaftGeometry:
    length_m: float = 1.6
    outer_diameter_mm: float = 40.0
    wall_thickness_mm: float = 4.0
    material: str = "AISI_304_Stainless"


@dataclass
class HybridRotorGeometry:
    """Full hybrid rotor: Darrieus blades wrap around a central Savonius rotor."""
    name: str = "Hybrid VAWT"
    target_power_w: float = 300.0
    darrieus: DarrieusBladeGeometry = field(default_factory=DarrieusBladeGeometry)
    savonius: SavoniusBucketGeometry = field(default_factory=SavoniusBucketGeometry)
    shaft: ShaftGeometry = field(default_factory=ShaftGeometry)
    rated_wind_speed_ms: float = 10.0
    cut_in_wind_speed_ms: float = 3.0
    cut_out_wind_speed_ms: float = 20.0

    @property
    def total_swept_area_m2(self) -> float:
        """
        Darrieus blades sweep the outer envelope; the nested Savonius sits
        inside that envelope and mostly contributes torque, not extra frontal
        area, so total swept area for power/Cp normalisation is taken as the
        Darrieus swept area (the standard convention for hybrid rotors in
        literature, e.g. Wakui et al., Bhuyan & Biswas).
        """
        return self.darrieus.swept_area_m2

    def validate(self) -> List[str]:
        """Basic physical sanity checks. Returns list of warning strings."""
        warnings = []
        if self.darrieus.solidity < 0.1 or self.darrieus.solidity > 1.0:
            warnings.append(
                f"Darrieus solidity {self.darrieus.solidity:.2f} is outside the "
                f"typical practical range (0.1-1.0); results may be unreliable."
            )
        if self.savonius.rotor_diameter_m > 2 * self.darrieus.rotor_radius_m:
            warnings.append(
                "Savonius rotor diameter exceeds Darrieus swept diameter; "
                "the Savonius stage would protrude beyond the Darrieus blades."
            )
        if self.darrieus.blade_height_m <= 0 or self.darrieus.rotor_radius_m <= 0:
            warnings.append("Blade height and rotor radius must be positive.")
        return warnings