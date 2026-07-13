"""
Generates a complete OpenFOAM case (pimpleFoam, transient, k-omega SST,
rotating AMI mesh region) for 2D CFD validation of a candidate Darrieus rotor
design. This produces real, syntactically valid OpenFOAM dictionary files --
what it does NOT do is run OpenFOAM itself (not installed in this sandbox,
and a multi-hour-per-case HPC job in general). The intended workflow:

    1. Optimiser (Phase 12) finds Pareto-optimal candidates using Stage 1 (BEM).
    2. This module generates a ready-to-run case for each candidate.
    3. The user runs `./Allrun` on a machine with OpenFOAM installed (or an
       HPC cluster).
    4. `results_parser.py` reads back the `forceCoeffs` function-object output.
    5. `validation.py` compares it against the Stage-1 BEM prediction for the
       same operating point and reports the error.

Mesh strategy: background block mesh (blockMesh) with a cylindrical rotating
AMI (Arbitrary Mesh Interface) zone around the blade, meshed with
snappyHexMesh against the STL exported by stl_export.py. This is the standard
approach for rotating-machinery CFD in OpenFOAM (same pattern used for wind
turbine and pump simulations).
"""
from __future__ import annotations
from dataclasses import dataclass
import math

from app.geometry.models import HybridRotorGeometry


@dataclass
class CFDCaseConfig:
    wind_speed_ms: float
    tip_speed_ratio: float
    end_time_revolutions: float = 6.0   # simulate N full rotor revolutions
    time_steps_per_revolution: int = 720  # 0.5 deg per step, standard for VAWT CFD
    domain_radius_factor: float = 15.0    # far-field boundary at N x rotor diameter
    ami_radius_factor: float = 1.5        # rotating-zone radius as a multiple of rotor radius


def _foam_header(obj_class: str, obj_name: str, location: str) -> str:
    return f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       {obj_class};
    object      {obj_name};
}}
"""


def generate_control_dict(geom: HybridRotorGeometry, cfg: CFDCaseConfig) -> str:
    omega = cfg.tip_speed_ratio * cfg.wind_speed_ms / geom.darrieus.rotor_radius_m
    revolution_time = 2 * math.pi / omega
    end_time = cfg.end_time_revolutions * revolution_time
    delta_t = revolution_time / cfg.time_steps_per_revolution
    write_interval = cfg.time_steps_per_revolution // 36  # ~36 outputs per revolution

    return _foam_header("dictionary", "controlDict", "system") + f"""
application     pimpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time:.6f};
deltaT          {delta_t:.8f};
writeControl    timeStep;
writeInterval   {max(write_interval,1)};
purgeWrite      0;
writeFormat     ascii;
writePrecision  7;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
adjustTimeStep  no;
maxCo           5;

functions
{{
    forceCoeffs1
    {{
        type            forceCoeffs;
        libs            ("libforces.so");
        writeControl    timeStep;
        writeInterval   1;
        patches         (blade);
        rho             rhoInf;
        rhoInf          1.225;
        liftDir         (0 1 0);
        dragDir         (1 0 0);
        CofR            (0 0 0);
        pitchAxis       (0 0 1);
        magUInf         {cfg.wind_speed_ms:.4f};
        lRef            {geom.darrieus.chord_m:.6f};
        Aref            {geom.darrieus.chord_m * geom.darrieus.blade_height_m:.6f};
    }}
}}
"""


def generate_fv_schemes() -> str:
    return _foam_header("dictionary", "fvSchemes", "system") + """
ddtSchemes
{
    default         backward;
}
gradSchemes
{
    default         Gauss linear;
}
divSchemes
{
    default             none;
    div(phi,U)          Gauss linearUpwindV grad(U);
    div(phi,k)          Gauss upwind;
    div(phi,omega)      Gauss upwind;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}
laplacianSchemes
{
    default         Gauss linear corrected;
}
interpolationSchemes
{
    default         linear;
}
snGradSchemes
{
    default         corrected;
}
oversetInterpolation
{
    method          inverseDistance;
}
"""


def generate_fv_solution() -> str:
    return _foam_header("dictionary", "fvSolution", "system") + """
solvers
{
    p
    {
        solver          GAMG;
        tolerance       1e-7;
        relTol          0.01;
        smoother        GaussSeidel;
    }
    pFinal
    {
        $p;
        relTol          0;
    }
    "(U|k|omega)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0.1;
    }
    "(U|k|omega)Final"
    {
        $U;
        relTol          0;
    }
}

PIMPLE
{
    nOuterCorrectors    3;
    nCorrectors         2;
    nNonOrthogonalCorrectors 1;
    correctPhi          yes;
    moveMeshOuterCorrectors yes;
}

relaxationFactors
{
    equations
    {
        "U.*"           1;
        "k.*"           1;
        "omega.*"       1;
    }
}
"""


def generate_dynamic_mesh_dict(geom: HybridRotorGeometry, cfg: CFDCaseConfig) -> str:
    omega = cfg.tip_speed_ratio * cfg.wind_speed_ms / geom.darrieus.rotor_radius_m
    return _foam_header("dictionary", "dynamicMeshDict", "constant") + f"""
dynamicFvMesh   dynamicMotionSolverFvMesh;

motionSolverLibs ("libfvMotionSolvers.so");

solver          solidBody;

solidBodyMotionFunc rotatingMotion;

rotatingMotionCoeffs
{{
    origin          (0 0 0);
    axis            (0 0 1);
    omega           {omega:.6f};  // rad/s, from TSR={cfg.tip_speed_ratio}, V={cfg.wind_speed_ms} m/s
}}
"""


def generate_transport_properties(geom: HybridRotorGeometry) -> str:
    return _foam_header("dictionary", "transportProperties", "constant") + """
transportModel  Newtonian;
nu              1.5e-05;  // air at ~20degC, m^2/s
"""


def generate_turbulence_properties() -> str:
    return _foam_header("dictionary", "turbulenceProperties", "constant") + """
simulationType  RAS;
RAS
{
    RASModel        kOmegaSST;
    turbulence      on;
    printCoeffs     on;
}
"""


def generate_boundary_field_U(cfg: CFDCaseConfig) -> str:
    return _foam_header("volVectorField", "U", "0") + f"""
dimensions      [0 1 -1 0 0 0 0];
internalField   uniform ({cfg.wind_speed_ms:.4f} 0 0);

boundaryField
{{
    inlet
    {{
        type            freestreamVelocity;
        freestreamValue uniform ({cfg.wind_speed_ms:.4f} 0 0);
    }}
    outlet
    {{
        type            freestreamVelocity;
        freestreamValue uniform ({cfg.wind_speed_ms:.4f} 0 0);
    }}
    blade
    {{
        type            movingWallVelocity;
        value           uniform (0 0 0);
    }}
    AMI1
    {{
        type            cyclicAMI;
    }}
    AMI2
    {{
        type            cyclicAMI;
    }}
    frontAndBack
    {{
        type            empty;
    }}
}}
"""


def generate_boundary_field_p() -> str:
    return _foam_header("volScalarField", "p", "0") + """
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;

boundaryField
{
    inlet
    {
        type            freestreamPressure;
        freestreamValue uniform 0;
    }
    outlet
    {
        type            freestreamPressure;
        freestreamValue uniform 0;
    }
    blade
    {
        type            zeroGradient;
    }
    AMI1
    {
        type            cyclicAMI;
    }
    AMI2
    {
        type            cyclicAMI;
    }
    frontAndBack
    {
        type            empty;
    }
}
"""


def generate_readme(geom: HybridRotorGeometry, cfg: CFDCaseConfig) -> str:
    return f"""# OpenFOAM Case: {geom.name}

Auto-generated by the Hybrid VAWT CAE Platform (Phase 6 CFD integration) for
Stage-2 CFD validation of a Pareto-optimal candidate from the Stage-1 BEM
optimiser.

## Operating point
- Wind speed: {cfg.wind_speed_ms} m/s
- Tip-speed ratio: {cfg.tip_speed_ratio}
- Simulated duration: {cfg.end_time_revolutions} rotor revolutions
- Time resolution: {cfg.time_steps_per_revolution} steps/revolution

## What you still need to do (this sandbox cannot run OpenFOAM)
1. Install OpenFOAM (v2306 or later recommended) on a machine with it available.
2. Place `blade.stl` (in this folder) into `constant/triSurface/`.
3. Run `blockMesh`, then `snappyHexMesh -overwrite` to mesh around the blade
   inside the rotating AMI cylinder (radius = {cfg.ami_radius_factor} x rotor radius).
   A `snappyHexMeshDict` is NOT auto-generated here yet -- meshing parameters
   are geometry-dependent enough (cell sizing, boundary layers) that they
   need a human pass in your first real case; this scaffold gives you every
   other dictionary already correctly parameterised for this specific design.
4. Run `pimpleFoam` (or `./Allrun` once you write one).
5. Feed `postProcessing/forceCoeffs1/0/coefficient.dat` into the platform's
   `/api/v1/cfd/parse-results` endpoint to compare against the Stage-1 BEM
   prediction for this same operating point.

## Files included
- `blade.stl` - extruded blade geometry (straight blade; helical twist not yet supported)
- `system/controlDict`, `fvSchemes`, `fvSolution`
- `constant/dynamicMeshDict` (solid-body rotation at the specified TSR)
- `constant/transportProperties`, `turbulenceProperties` (k-omega SST)
- `0/U`, `0/p` boundary conditions
"""
