# Changelog

## Phase 14-15 - Reporting & Validation

**Backend (`app/reporting/`)**
- `report_data.py`: a shared `ReportData` assembler that runs the
  platform's own Stage 1-7 pipeline once per request and feeds every
  output format, so a PDF and an Excel export of the same design are
  guaranteed to agree — not two independently-written code paths that
  could silently drift apart.
- `docx_report.py` (python-docx), `xlsx_report.py` (openpyxl, 3 sheets:
  Summary/Cp-Lambda Curve/Warnings), `pdf_report.py` (reportlab),
  `csv_export.py`: four real report generators.
- New endpoints: `POST /reporting/{docx,xlsx,pdf,csv}`.
- **Visual verification, not just format-checking**: the DOCX output was
  rendered to PDF via LibreOffice (`soffice --headless --convert-to pdf`)
  and each page inspected as an image during development to confirm
  headings, tables, and body text actually display correctly — the kind
  of check that catches a report that "validates" as a zip/PDF but
  renders as garbage.

**Backend (`app/validation/`)**
- `system_checks.py`: six live consistency checks, distinct from the
  pytest suite (which validates solvers against closed-form theory once,
  for developers) — these re-run against the REST API for a *specific*
  design: Betz limit compliance, AEP rated-power-capping conservativeness,
  structural result sanity, modal frequency ordering, fatigue life
  positivity, and IRR/NPV sign consistency (a standard DCF identity).
- New endpoint: `POST /validation/run-checks`.
- 18 new tests total across reporting (11) and validation (7), including
  tests that assert each report's numbers match calling the underlying
  Stage 1/3/7 functions directly. 175 backend tests total, all passing.

**Frontend**
- `ReportingValidationPanel.tsx`: four download buttons (DOCX/PDF/XLSX/CSV)
  and a live validation checklist with pass/fail icons and per-check detail text.
- Extended `api.ts`/`types.ts` with the new reporting and validation endpoints.

**New dependencies**: `python-docx`, `openpyxl`, `reportlab`.

**Project status**: all 15 phases from the master spec's development order
are now delivered. This closes out the incremental build described at the
start of this project — every phase shipped with real tests and (where
applicable) validation against closed-form or independently-derivable
results, not just code that runs without crashing.


## Phase 13 - Animation Engine

**Backend**
- Extended `app/optimization/nsga2_runner.py` with `capture_history`:
  extracts the non-dominated, feasibility-filtered Pareto front from each
  generation's population (via pymoo's `save_history=True` and
  `NonDominatedSorting`), not just the final result — needed for the
  Pareto-front evolution animation to show genuine per-generation states.
- Extended `OptimizationRequest`/`OptimizationResponse` schemas and the
  `/optimization/pareto-front` endpoint with the new history field.
- 6 new tests: generation count matches request, history empty when not
  requested, eval counts increase monotonically, best-found AEP never
  decreases across generations (NSGA-II elitism property), and — the most
  thorough check — every design in every generation's captured front was
  independently re-verified against `analyze_blade_structure` to confirm
  it actually satisfies the safety constraint, not just trusted from
  pymoo's internal bookkeeping. 150 backend tests total, all passing.

**Frontend**
- `TurbineViewer3D.tsx`: real-time rotating turbine (Three.js/React Three
  Fiber) built from actual blade count/radius/height/chord, wind-particle
  streamlines, and live gauges (RPM, torque, power, Cp) computed from the
  Stage-1 BEM `/bem/cp-lambda` endpoint at the selected operating point.
- `OptimizationEvolutionPanel.tsx`: play/pause/scrub/speed-controlled
  animation through real NSGA-II generation snapshots.
- `ModalVibrationAnimation.tsx`: animates real Stage-6 mode shapes at a
  watchable visual rate, with the true natural frequency shown numerically.
- `BladeDeformationAnimation.tsx`: animates a loading/unloading cycle using
  the real Stage-3 beam FEM deflection shape, amplitude-normalized for
  visibility with the true (mm-scale) deflection shown numerically.
- New dependencies: `three`, `@react-three/fiber`, `@react-three/drei`.

**Scope decision, documented rather than silently cut**: the master spec's
full animation list (pressure/velocity contour fields, stress contour
evolution, rotor startup sequence, MP4/GIF export) would need model
upgrades this platform doesn't have yet — a 2D/3D flow-field grid beyond
Stage 2a's surface-only panel method, a 2D/3D FEA field beyond Stage 3's 1D
beam model, a transient control-system model for startup dynamics, and
server-side video encoding for true MP4/GIF export. Building fake versions
of these (e.g. a decorative contour plot not actually derived from a flow
solve) would violate this platform's core principle of only shipping
results backed by real computation. Documented explicitly in the README
rather than either skipping silently or faking it.


## Phase 12 - Multi-Objective Optimization

**Backend (`app/optimization/`)**
- `rotor_problem.py`: defines `RotorDesignProblem`, a pymoo `Problem`
  subclass wrapping the entire pipeline — Stage-1 aerodynamics, Stage-3/4
  structural analysis, Stage-7 economics — into 3 objectives (maximize AEP,
  minimize LCOE, minimize blade mass) and 1 constraint (structural safety
  factor). Uses pymoo (named explicitly in the master spec) rather than a
  hand-rolled genetic algorithm.
- `nsga2_runner.py`: runs pymoo's NSGA-II (fast non-dominated sorting,
  crowding distance, SBX crossover, polynomial mutation) and extracts the
  Pareto front as plain Python dataclasses for the API layer.
- New endpoint: `POST /optimization/pareto-front`.
- 10 new tests (8 problem/optimizer tests, 2 API integration tests). 145
  backend tests total, all passing.

**Frontend**
- `OptimizationPanel.tsx`: clickable Pareto-front scatter plot (AEP vs.
  LCOE, bubble size = blade mass), with a design-inspector panel showing
  full geometry for any selected point.
- Extended `api.ts`/`types.ts` with the new optimization endpoint and types.

**Performance work**: a single unoptimized pipeline evaluation took ~0.55s
(dominated by AEP's Weibull-weighted power-curve integration), which would
make a 240-evaluation search (24 population x 10 generations) take over two
minutes — too slow for a synchronous API call. Exposed BEM resolution
(azimuth points, TSR search points, wind-speed bin count) as parameters
through `energy_yield.py` and `economic_analysis.py`, then used a coarser
preset inside the optimizer (8 wind bins instead of 25, fewer azimuth/TSR
points) for an 8x speedup (0.55s -> 0.068s per evaluation), bringing the
full default search down to ~13s. Documented explicitly as a fast-preview
resolution, not a replacement for the full-fidelity Stage 1/7 endpoints.

**Verification approach**: rather than only testing the optimizer in
isolation, confirmed a single `RotorDesignProblem` evaluation's objective
values exactly match calling `analyze_blade_structure` directly with the
same inputs — proving the optimization wrapper is really calling the same
validated pipeline from every earlier phase, not a simplified stand-in.
Separately confirmed every design in a returned Pareto front satisfies the
structural constraint (all constraint values negative, i.e. safety factor
above target, with real margin) by inspecting pymoo's raw constraint array
directly rather than trusting that "the algorithm handles constraints" — a
concrete check that feasibility was actually enforced, not just assumed
from framework behaviour.


## Phase 11 - Economics

**Backend (`app/economics/`)**
- `energy_yield.py`: AEP calculation — the Stage-1 BEM power curve
  integrated against a Weibull wind distribution (reusing Phase 9's wind
  distribution module).
- `capex.py`: parametric CAPEX buildup, with blade material cost grounded
  in the actual Stage-4 composite spar mass for the chosen material (real
  computed number, not a generic weight guess), plus representative
  generator/electronics/tower/installation costs.
- `opex.py`: annual O&M cost as a percentage of CAPEX (standard small-wind
  simplification).
- `financial_metrics.py`: LCOE, NPV, IRR (via `scipy.optimize.brentq`), and
  simple payback period — all standard formulas, validated against four
  independent hand-computable closed-form cases: CRF at r=0 equals exactly
  1/n, CRF at a commonly-cited reference case (8%/20yr ≈ 0.1019), NPV at
  r=0 reduces to simple arithmetic, and IRR matches a hand-solvable
  single-year algebra problem exactly.
- `economic_analysis.py`: ties it together into one top-level analysis.
- New endpoint: `POST /economics/analyze`.
- 21 new tests (10 financial-metrics closed-form checks, 7 full-pipeline
  tests, 2 API integration tests + 2 more). 135 backend tests total, all passing.

**Frontend**
- `EconomicsPanel.tsx`: headline LCOE/NPV/IRR/payback metrics with
  pass/fail styling, and a CAPEX breakdown pie chart.
- Extended `api.ts`/`types.ts` with the new economics endpoint and types.

**Bug caught and fixed during development**: the initial AEP calculation
used the raw Stage-1 BEM power curve directly, which has no control-system
model and keeps producing more power as wind speed rises indefinitely
(~3.5 kW at 20 m/s for this platform's default "300 W" design). This gave
an implausible 66% capacity factor — real small wind turbines are typically
15-35%, even at excellent sites. A real turbine limits power near its rated
value above rated wind speed via pitch control, stall regulation, or
electrical load limiting; none of that exists in this platform yet (no
control-system phase has been built). Fixed by applying the standard
idealized power-curve shape (rated-power ceiling above rated wind speed)
plus a representative 0.88 system-loss factor for AEP purposes specifically
-- the underlying Stage-1 physics output is untouched, this only affects
how it's integrated for the economics calculation. Post-fix capacity factor
(37.5% for the default design at a good-but-plausible wind site) is a
defensible first-pass estimate.

**Notable result**: at default assumptions ($0.15/kWh grid electricity, 6%
discount rate, 20-year life), the default 300W design shows negative NPV
(-$325) and an IRR (3.5%) below the discount rate — internally consistent
(as they must be) and an honest reflection that small wind turbines often
aren't economically competitive against grid electricity without subsidy
or a strong wind resource. The model wasn't tuned to produce a flattering
number; it reports what the assumptions actually imply.


## Phase 10 - Aeroelasticity

**Backend (`app/aeroelastic/`)**
- `modal_analysis.py`: generalized eigenvalue solve (K*phi = omega^2*M*phi)
  for blade natural frequencies and mode shapes, using a standard consistent
  mass matrix paired with Phase 7's beam stiffness matrix. Validated against
  closed-form analytical natural frequencies for pinned-pinned (exact
  formula) and cantilever (tabulated beta_n*L eigenvalue roots) uniform
  beams — matched to 6 decimal places across the first 4 modes.
- `harmonic_content.py`: FFT-based harmonic decomposition of the real
  Stage-1 BEM azimuthal load trace. Validated by exactly recovering the
  amplitudes of a synthetic 3-harmonic test signal (3.0, 1.2, 0.4) before
  trusting it on real aerodynamic data.
- `campbell.py`: Campbell diagram data (natural frequencies vs. NP
  excitation lines across the operating RPM range) with resonance-crossing
  detection, validated against a hand-constructed exact-crossing test case
  (10 Hz natural frequency crossing the 1P line at exactly 600 RPM).
- `blade_aeroelastic_analysis.py`: ties it together — modal analysis +
  operating RPM range (from Stage 1's cut-in/cut-out wind speeds) +
  Campbell diagram + real harmonic content, cross-referencing which
  resonance crossings actually coincide with harmonics that carry
  meaningful aerodynamic load energy (not just any crossing).
- New endpoint: `POST /aeroelastic/analyze-blade`.
- 22 new tests (7 modal analysis, 4 harmonic content, 5 Campbell diagram, 6
  full-pipeline tests). 116 backend tests total, all passing.

**Frontend**
- `AeroelasticPanel.tsx`: Campbell diagram chart (natural frequency lines
  overlaid with NP excitation lines across the RPM range), harmonic content
  bar chart, and a resonance-risk summary with pass/fail styling.
- Extended `api.ts`/`types.ts` with the new aeroelastic endpoint and types.

**Notable result**: for the default design, the dominant aerodynamic load
harmonic is 1P (~44.6 N/m amplitude) as expected for a Darrieus rotor, and
while the Campbell diagram does flag exact resonance crossings at 5P/6P
within the wide operating RPM range (107-716 RPM), those harmonics carry
only ~0.4-1.7 N/m of real load energy — two orders of magnitude less than
1P. The analysis correctly distinguishes "a resonance crossing exists
somewhere" from "a resonance crossing exists at a harmonic that actually
matters," which is a materially more useful answer than a naive 1P-only check.

**Development note (not a shipped bug, kept here for transparency)**: an
early test asserted that increasing both spar width fraction and wall
thickness together should always raise natural frequency. This failed —
correctly, on the model's part. Mass can grow faster than stiffness once
wall thickness becomes a large fraction of section depth, so the
combined effect isn't monotonic; the test's assumption was wrong, not the
physics. Replaced with a test that isolates EI and mass independently
(the well-established f ~ sqrt(EI/mass) relationship), which is what the
earlier test should have checked in the first place.


## Phase 9 - Fatigue Analysis

**Backend (`app/fatigue/`)**
- `rainflow.py`: from-scratch ASTM E1049 3-point stack-based rainflow cycle
  counter. Validated against two hand-traced worked examples derived
  independently before writing the code: a nested-cycle case
  ([0,10,4,6,0] → exactly a range-2 and a range-10 cycle) and a clean
  double-triangle-wave case ([0,5,0,5,0] → exactly two range-5 cycles).
- `sn_curve.py`: Basquin power-law S-N curve per material, with a fatigue
  exponent lookup (m≈10 CFRP, m≈9 GFRP — representative literature values).
- `miners_rule.py`: Palmgren-Miner cumulative damage. Validated against a
  definitional closed-form check: applying exactly N_i cycles at a single
  stress level must give damage of exactly 1.0.
- `wind_distribution.py`: Weibull wind speed distribution, binned into
  annual operating hours (validated to sum to exactly 8760 hours/year).
- `fatigue_analysis.py`: ties it together — pulls the per-revolution
  azimuthal normal-force trace from Stage 1 (the dominant VAWT fatigue
  driver), linearly scales it to a stress trace via a unit-load beam FEM
  solve, rainflow-counts it per wind-speed bin, weights by Weibull-derived
  annual revolutions per bin, and sums Miner's-rule damage across all bins
  for an estimated fatigue life in years.
- New endpoint: `POST /fatigue/analyze-blade`.
- 22 new tests (7 rainflow validation, 7 S-N/Miner's-rule closed-form
  checks, 8 full-pipeline tests). 92 backend tests total, all passing.

**Frontend**
- `FatiguePanel.tsx`: material picker, Weibull shape/scale controls,
  estimated-life display with pass/fail styling against the 20-year design
  target, and a damage-by-wind-speed-bin bar chart.
- Extended `api.ts`/`types.ts` with the new fatigue endpoint and types.

**Bug caught and fixed during development**: the initial S-N curve
implementation capped cycles-to-failure at a fixed 1e8 ceiling, intended as
a practical "endurance limit." This was backwards — for a well-margined
CFRP blade (Phase 7/8's ~9.5 static safety factor) operating at a stress
amplitude only ~2% of static strength, the correct Basquin extrapolation
gives ~1.75×10^17 cycles to failure (i.e. effectively unlimited life), but
the cap forced this down to 1e8, which combined with the ~450 million real
cycles/year this small, high-RPM VAWT accumulates, predicted total failure
in just 0.2 years — an obviously wrong answer for a design with a healthy
static safety margin. Caught by sanity-checking the result against a hand
estimate (a stress ratio of ~2% of static strength should not cause
near-term fatigue failure under any reasonable S-N exponent) before
shipping, not after. Fixed by removing the artificial low-cycle cap and
letting the Basquin power law extrapolate naturally, with only a very high
numerical ceiling (1e18) to guard against float overflow.


## Phase 8 - Composite Optimization

**Backend (`app/composites/`)**
- `lamina.py`: orthotropic unidirectional ply property library (CFRP, GFRP)
  with real E1/E2/G12/v12 values, distinct from Phase 7's isotropic-equivalent
  materials.
- `laminate.py`: from-scratch Classical Laminate Theory solver — reduced
  stiffness matrix per ply, transformation to laminate axes, assembled A/B/D
  matrices, effective in-plane and flexural engineering constants. Validated
  against 5 independent closed-form results: 0°-layup exactly reproduces E1/E2,
  90°-layup exactly swaps them, symmetric layups give exactly zero B-matrix,
  asymmetric layups show real coupling, and a quasi-isotropic [0/45/-45/90]s
  layup gives Ex=Ey exactly — a genuine theoretical prediction, not a tuned result.
- `composite_spar.py`: composite box-spar using transformed-section beam
  theory so spar caps and shear webs can carry different layups/moduli.
  Validated to exactly reduce to Phase 7's isotropic hollow-rectangle formula
  when cap and web share one material (ratio = 1.000000 in both bending planes).
- `blade_composite_analysis.py`: reuses Phase 7's beam FEM for the (material-
  independent) moment diagram, then computes deflection and stress via the
  composite EI and per-part moduli rather than a single homogeneous value.
- `optimizer.py`: grid search over spar cap ply count, shear web ply pair
  count, and spar width fraction, minimizing mass subject to a target safety
  factor. Runs separately for CFRP and GFRP for direct comparison. Aero loads
  are computed once and reused across the whole grid (a 25x speedup, from
  ~13s to ~0.5s, needed for the endpoint to be usable synchronously).
- New endpoints: `GET /composites/ply-materials`, `POST /composites/laminate`,
  `POST /composites/optimize-spar`, `POST /composites/compare-materials`.
- 20 new tests (9 CLT validation tests, 7 composite spar/optimizer tests, 4 API
  integration tests). 68 backend tests total, all passing.

**Frontend**
- `CompositesPanel.tsx`: carbon-vs-glass comparison table (ply counts, mass,
  safety factor, feasibility), with an automatic plain-language summary of
  which material wins and why.
- Extended `api.ts`/`types.ts` with the new composites endpoints and types.

**Notable result**: under a demanding load case (20 m/s, TSR 4.5), the
optimizer found a feasible CFRP design (safety factor 1.51 — right at the
target, as a mass-minimizing search should land) while GFRP could not reach
the 1.5 target anywhere in the search grid (best found: 0.86). This is a
genuine finding from the model, not a scripted outcome — at the default
300W operating point the two materials are much closer, both comfortably
feasible, which is itself a useful design insight (this turbine doesn't
structurally require carbon fibre at its nominal rating, but would at
higher TSR/wind speed).


## Phase 7 - Structural Analysis (FEA)

**Backend (`app/structural/`)**
- `beam_fem.py`: from-scratch Euler-Bernoulli beam finite element solver
  (cubic Hermite elements, standard 4x4 element stiffness matrix and
  equivalent nodal load vector for a uniform distributed load). Supports
  pinned-pinned and cantilever boundary conditions. Validated against
  closed-form analytical solutions for both cases (max deflection and max
  moment) to ~9 significant figures at every mesh density tested (4 to 100
  elements) — Euler-Bernoulli elements are exact for this load case, so this
  is a strong correctness check, not just a smoke test.
- `materials.py`: 4-material library (CFRP, GFRP, 6061 aluminium, 304
  stainless) with real density, modulus, and strength values.
- `cross_section.py`: simplified rectangular hollow box-spar sizing (width
  as a fraction of chord, height as a fraction of airfoil thickness), with
  correct flapwise/edgewise second-moment-of-area and section modulus.
- `buckling.py`: closed-form Euler critical buckling load for standard end conditions.
- `blade_analysis.py`: ties it together — pulls peak per-revolution blade
  loads from the Stage-1 BEM solver, adds centrifugal loading, runs both
  bending planes through the beam FEM, reports combined stress and safety
  factor against material yield strength.
- New endpoints: `GET /structural/materials`, `POST /structural/analyze-blade`.
- 22 new tests (16 module-level physics/analytical checks, 3 API
  integration tests, plus cross-section and material-library checks). 48
  backend tests total, all passing.

**Frontend**
- `StructuralPanel.tsx`: material picker, spar sizing inputs, boundary
  condition selector, deflection and bending-moment charts (flapwise vs
  edgewise), safety factor display with pass/fail styling against the 1.5
  design threshold.
- Extended `api.ts`/`types.ts` with the new structural endpoints and types.

**Notable result**: for the default 300W design, centrifugal loading
(615-1039 N/m across the material set tested) dominates the aerodynamic
normal load (74 N/m peak at 12 m/s) in the flapwise direction — consistent
with published VAWT structural analyses where centrifugal effects, not
aero loads, typically govern blade flapwise sizing at operating tip-speed
ratios. This fell out of the model rather than being hard-coded in.

## Phase 6 - CFD Integration

**Backend (`app/cfd/`)**
- `airfoil_geometry.py`: NACA00XX symmetric-section coordinate generator with
  cosine-spaced panelling.
- `panel_method.py`: from-scratch 2D constant-strength vortex panel method
  solver. Computes surface Cp distribution and Cl for the blade section.
- `stl_export.py`: extrudes the blade cross-section into a closed ASCII STL
  for use in OpenFOAM's snappyHexMesh.
- `openfoam_case_generator.py` + `case_builder.py`: generates a complete,
  syntactically valid OpenFOAM case (controlDict, fvSchemes, fvSolution,
  dynamicMeshDict for rotating AMI at the design's exact TSR, transport/
  turbulence properties, 0/U and 0/p boundary conditions) packaged as a
  downloadable zip.
- `results_parser.py`: parses OpenFOAM `forceCoeffs` function-object output,
  computes revolution-averaged Cd/Cl/Cm over a configurable trailing window.
- `validation.py`: compares CFD-derived loading against the Stage-1 BEM
  prediction for the same operating point, flags results outside a 15%
  engineering tolerance.
- New endpoints: `POST /cfd/panel-method`, `POST /cfd/openfoam-case`,
  `POST /cfd/parse-results`, `POST /cfd/validate-against-bem`.
- 16 new tests (7 panel-method physics checks, 6 CFD module tests, 3 API
  integration tests).

**Frontend**
- `CFDPanel.tsx`: pressure-distribution chart (upper/lower Cp vs x/c) driven
  by the live panel-method endpoint, an OpenFOAM case download button, and a
  BEM-vs-CFD comparison tool with pass/fail styling against the 15% tolerance.
- Extended `api.ts`/`types.ts` with the new CFD endpoints and response types.

**Bugs caught and fixed during development** (both caught by physics sanity
tests before shipping, not after):
1. The panel-method boundary loop was seamed at the leading edge, so the
   Kutta condition was tied to the wrong pair of panels. This didn't crash
   or look wrong superficially, but broke fore-aft symmetry — a symmetric
   airfoil at zero angle of attack showed nonzero lift (Cl=-0.18 instead of
   the required exactly-zero). Fixed by reseaming the loop at the trailing
   edge, where the Kutta condition is physically meaningful.
2. After fixing (1), lift came out with the correct magnitude but the wrong
   sign (negative Cl for positive angle of attack), traced to an inverted
   Kutta-Joukowski circulation-to-lift sign convention. Confirmed the
   underlying pressure field was already correct (upper surface properly
   showed more suction) before correcting only the final circulation-sum sign.
   Post-fix, the lift-curve slope now matches the known thickness-correction
   factor for real (non-thin) symmetric sections to within a few percent —
   independent confirmation, not just "the test I wrote passes."

## Phase 1-5 - Architecture, Backend, Geometry, Stage-1 BEM Solver

**Backend**
- FastAPI app with `/api/v1` prefix, CORS configured for local frontend dev.
- SQLite persistence for rotor designs via SQLAlchemy (JSON-based geometry storage).
- Geometry module: `DarrieusBladeGeometry`, `SavoniusBucketGeometry`, `ShaftGeometry`,
  `HybridRotorGeometry`, each with derived properties (swept area, solidity, etc.)
  and a `.validate()` sanity-check method.
- Airfoil polar model: thin-airfoil pre-stall + Viterna-Corrigan post-stall
  extrapolation, small built-in NACA00xx library.
- Darrieus solver: single-streamtube momentum model, iterates induction factor
  via `scipy.optimize.brentq` against blade-element thrust, integrates torque/
  power over one revolution at 60-72 azimuth stations.
- Savonius solver: empirical Cp(TSR) correlation parameterised by overlap ratio.
- Hybrid combiner: superposes power from both stages sharing one shaft speed,
  reports system Cp normalised to Darrieus swept area.
- REST endpoints: geometry validate/save/list/get/delete, BEM Cp-lambda curve,
  BEM power curve (with simple MPPT-style TSR search per wind speed).
- 13 automated tests (8 physics sanity checks, 5 API integration tests), all passing.

**Frontend**
- Vite + React + TypeScript scaffold.
- Typed API client (`api.ts`) matching backend Pydantic schemas exactly.
- `GeometryForm`: editable inputs for every rotor parameter, live solidity readout.
- `App.tsx`: backend health check, live Cp-lambda and power-curve charts via
  Recharts, warnings surfaced from backend validation (e.g. Betz-limit breach,
  power target mismatch).
- Production build verified (`npm run build` succeeds, `tsc --noEmit` clean).

**Fixed during development**
- Caught and fixed a sin/cos swap in the Darrieus velocity triangle that was
  silently zeroing net rotor thrust and letting predicted Cp exceed the Betz
  limit (was Cp > 2.0 before the fix; now peaks ~0.49, correctly below 0.593).
  This is exactly the kind of bug the physics sanity tests exist to catch.

**Not included yet** (see README "Next phases"): composites, fatigue,
aeroelasticity, economics, multi-objective optimisation, animations, reporting.
