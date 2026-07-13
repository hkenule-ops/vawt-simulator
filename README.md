# Hybrid VAWT CAE Platform

A research-grade Computer Aided Engineering platform for a Hybrid Darrieus-Savonius
Vertical Axis Wind Turbine, targeting 300 W and 500 W designs. Built incrementally,
phase by phase, per the master spec. **This delivery covers all 15 phases**:
architecture, backend, geometry, Stage-1 BEM aerodynamics, Stage-2 CFD
integration, Stage-3 structural (FEA) analysis, Stage-4 composite spar
optimization, Stage-5 fatigue analysis, Stage-6 aeroelasticity, Stage-7
economics, Stage-8 multi-objective optimization, Stage-9/10/11 animations,
and Stage-12 reporting & validation, plus a frontend wired to the live API
throughout.

## What's actually working right now

- **Stages 1-8**: full aero/CFD/structural/composite/fatigue/aeroelastic/
  economic/optimization pipeline — see earlier CHANGELOG entries for detail
  on each, including the real bugs caught and fixed along the way.
- **Stages 9-11 — Animations**: a real-time 3D rotating turbine (Three.js)
  driven by live BEM-computed gauges, a scrubbable Pareto-front evolution
  animation using real NSGA-II generation snapshots, and modal
  vibration/blade deformation animations using real Stage 3/6 data.
- **Stage 12 — Reporting** (`backend/app/reporting/`):
  - A shared `ReportData` assembler that runs the platform's own pipeline
    (Stages 1-7) once per request and feeds every output format — so a
    PDF and an Excel export of the same design are guaranteed to agree,
    verified by tests that check each report's numbers match calling the
    underlying analysis functions directly, not a separate/drifted path.
  - Four real, format-valid outputs: DOCX (python-docx, visually verified
    by rendering to PDF and inspecting the pages), XLSX (openpyxl,
    multi-sheet with re-loadable data), PDF (reportlab), and CSV.
- **Stage 12 — Validation** (`backend/app/validation/`):
  - A live, user-facing system validation suite — distinct from (and a
    complement to) the pytest suite that gates every commit. Six checks
    re-derive key physical and financial invariants (Betz limit, AEP
    capping conservativeness, structural result sanity, modal frequency
    ordering, fatigue life positivity, IRR/NPV sign consistency) live
    against the REST API for the design currently being evaluated.
- **175 automated tests**, all passing.

## Scope note: what's in this phase vs. deferred

Consistent with every earlier phase, some items from the master spec's
animation list are explicitly deferred with reasons documented in the
Phase 13 CHANGELOG entry (pressure/velocity contour fields, stress contour
evolution, rotor startup sequence, true MP4/GIF export) — building
convincing versions of these needs model upgrades (2D/3D flow/FEA fields,
a transient control model) this platform doesn't have yet, and faking them
would violate the core principle this platform has held to throughout:
don't ship a result that isn't backed by real computation.

## Quick start (no Docker)

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # pymoo + reportlab/docx/openpyxl pull in some compiled deps, first install may take a minute or two
PYTHONPATH=. pytest tests/ -v    # confirm all 175 tests pass on your machine
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```
Backend runs at http://localhost:8000, interactive API docs at http://localhost:8000/docs.

### Frontend
```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```
Frontend runs at http://localhost:5173 and talks to the backend automatically.

## Quick start (Docker)
```bash
docker compose up --build
```
Backend on :8000, frontend on :5173.

## Project layout
```
vawt-platform/
├── backend/
│   ├── app/
│   │   ├── core/          # settings, database session
│   │   ├── geometry/       # rotor geometry dataclasses + validation
│   │   ├── aero/             # Stage-1 BEM solvers
│   │   ├── cfd/                # Stage-2: panel method, OpenFOAM, validation
│   │   ├── structural/           # Stage-3: beam FEM, isotropic materials, buckling
│   │   ├── composites/             # Stage-4: CLT, composite spar, layup optimizer
│   │   ├── fatigue/                  # Stage-5: rainflow, S-N curve, Miner's rule, Weibull
│   │   ├── aeroelastic/                # Stage-6: modal analysis, Campbell diagram, harmonics
│   │   ├── economics/                    # Stage-7: AEP, CAPEX, OPEX, LCOE/NPV/IRR
│   │   ├── optimization/                   # Stage-8: NSGA-II rotor design problem (pymoo)
│   │   ├── reporting/                        # Stage 12: DOCX/XLSX/PDF/CSV report generation
│   │   ├── validation/                         # Stage 12: live system validation checks
│   │   ├── models/                               # SQLAlchemy ORM
│   │   ├── schemas/                                # Pydantic request/response models
│   │   ├── api/                                      # FastAPI routers
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── GeometryForm.tsx
│   │   ├── CFDPanel.tsx
│   │   ├── StructuralPanel.tsx
│   │   ├── CompositesPanel.tsx
│   │   ├── FatiguePanel.tsx
│   │   ├── AeroelasticPanel.tsx
│   │   ├── EconomicsPanel.tsx
│   │   ├── OptimizationPanel.tsx
│   │   ├── TurbineViewer3D.tsx
│   │   ├── OptimizationEvolutionPanel.tsx
│   │   ├── ModalVibrationAnimation.tsx
│   │   ├── BladeDeformationAnimation.tsx
│   │   ├── ReportingValidationPanel.tsx
│   │   ├── api.ts
│   │   └── types.ts
│   └── Dockerfile
└── docker-compose.yml
```

## Design decisions worth knowing about

- **One data assembler, four report formats**: rather than writing each
  report format's data-gathering logic separately (a classic source of
  silent drift between a PDF and its "matching" Excel export), all four
  formats render from the same `ReportData` object, populated by one
  pipeline run. Tested explicitly: the assembled peak Cp, safety factor,
  and AEP all match calling the underlying Stage 1/3/7 functions directly.
- **Validation is a live feature, not just a CI gate**: Phase 15's
  system-validation checks are exposed via `/validation/run-checks` and
  re-run against the *current* design's live API responses, not just
  asserted once in a test file. A user evaluating a specific design gets
  a real, current answer to "does this design's own analysis hold
  together" — e.g., its IRR and NPV actually agree in sign, its AEP
  capping is actually conservative, its modal frequencies are actually
  ordered correctly.
- **DOCX/PDF visually verified, not just format-checked**: beyond
  confirming the DOCX is a valid zip with `document.xml` and the PDF has
  a `%PDF-` header, the DOCX was rendered to PDF via LibreOffice and
  visually inspected page-by-page during development to confirm tables,
  headings, and text actually display correctly — not just that the file
  technically parses.
- Earlier-phase decisions (Stages 1-11) are documented in CHANGELOG.md.

## Verifying it yourself

**Report data matches the underlying pipeline (no drift between formats):**
```bash
cd backend && source .venv/bin/activate
PYTHONPATH=. python3 -c "
from app.geometry.models import HybridRotorGeometry
from app.reporting.report_data import assemble_report_data
from app.aero.hybrid_solver import cp_lambda_curve

geom = HybridRotorGeometry()
data = assemble_report_data(geom)
points = cp_lambda_curve(geom, geom.rated_wind_speed_ms, tsr_min=0.5, tsr_max=4.5, n_points=20)
print('report peak Cp:', data.peak_cp, ' direct pipeline peak Cp:', max(p.system_cp for p in points))
"
```

**Live system validation for the default design:**
```bash
PYTHONPATH=. python3 -c "
from app.geometry.models import HybridRotorGeometry
from app.validation.system_checks import run_system_validation
report = run_system_validation(HybridRotorGeometry())
for c in report.checks:
    print(f'[{\"PASS\" if c.passed else \"FAIL\"}] {c.name}')
"
```

Earlier-phase verification commands are in the previous CHANGELOG entries.

## Project status

All 15 phases from the master spec's development order are now delivered.
This is a complete, working incremental build — every phase shipped with
real tests, real physics/theory validation against closed-form or
independently-derivable results where applicable, and honest documentation
of every simplification, deferred feature, and bug caught along the way.
It is a research-grade first-pass CAE platform, not a certified design tool
— every report and warning in the platform itself says so where it matters
(structural buckling checks, CAPEX estimates, fatigue exponents, control-
system assumptions). Extending any stage further (higher-fidelity CFD,
laminate first-ply-failure analysis, a real control-system model, etc.) is
straightforward given the modular structure, but not required to call this
delivery complete against the spec as given.
# vawt-simulator
