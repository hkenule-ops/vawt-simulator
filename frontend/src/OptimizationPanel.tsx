import { useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import type { HybridRotorIn, ParetoDesignOut } from "./types";
import { optimizeParetoFront, downloadOpenFOAMCase } from "./api";

interface Props {
  geometry: HybridRotorIn;
}

/**
 * Builds a full HybridRotorIn for a selected Pareto candidate: the optimiser
 * only searches rotor radius, blade height, chord, spar sizing, and blade
 * twist/helical sweep, so everything else (airfoil, blade count, thickness
 * ratio, Savonius stage, shaft, wind envelope) is carried over unchanged
 * from the base design used to launch the search.
 */
function geometryFromParetoDesign(base: HybridRotorIn, d: ParetoDesignOut): HybridRotorIn {
  return {
    ...base,
    name: `${base.name} (Pareto candidate)`,
    darrieus: {
      ...base.darrieus,
      rotor_radius_m: d.rotor_radius_m,
      blade_height_m: d.blade_height_m,
      chord_m: d.chord_m,
      twist_angle_deg: d.twist_angle_deg,
      helical_twist_deg: d.helical_twist_deg,
    },
  };
}

export default function OptimizationPanel({ geometry }: Props) {
  const [material, setMaterial] = useState("CFRP_UD");
  const [populationSize, setPopulationSize] = useState(24);
  const [generations, setGenerations] = useState(10);
  const [operatingTsr, setOperatingTsr] = useState(2.25);
  const [pareto, setPareto] = useState<ParetoDesignOut[]>([]);
  const [selected, setSelected] = useState<ParetoDesignOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [cfdWindSpeed, setCfdWindSpeed] = useState(geometry.rated_wind_speed_ms);
  const [downloadingCase, setDownloadingCase] = useState(false);

  const plyKeyFor = (mat: string) => (mat === "GFRP_UD" ? "GFRP_UD_PLY" : "CFRP_UD_PLY");

  const run = async () => {
    setLoading(true);
    const t0 = performance.now();
    try {
      const res = await optimizeParetoFront(
        geometry, material, plyKeyFor(material), populationSize, generations,
        1.5, operatingTsr,
      );
      setPareto(res.pareto_front);
      setElapsed((performance.now() - t0) / 1000);
      setSelected(null);
    } finally {
      setLoading(false);
    }
  };

  const downloadCaseForSelected = async () => {
    if (!selected) return;
    setDownloadingCase(true);
    try {
      const candidateGeometry = geometryFromParetoDesign(geometry, selected);
      await downloadOpenFOAMCase(candidateGeometry, cfdWindSpeed, operatingTsr);
    } finally {
      setDownloadingCase(false);
    }
  };

  const chartData = pareto.map((d) => ({
    aep: d.aep_kwh,
    lcoe: d.lcoe_usd_per_kwh,
    mass: d.blade_mass_kg,
    design: d,
  }));

  const selectedIsTwisted =
    !!selected && (selected.twist_angle_deg !== 0 || selected.helical_twist_deg !== 0);

  return (
    <div className="panel cfd-panel">
      <h2>
        Multi-Objective Optimization
        <span className="stage-badge">Stage 8</span>
      </h2>
      <p className="panel-desc">
        NSGA-II search over rotor radius, blade height, chord, spar sizing, and blade twist/helical
        sweep — maximise AEP, minimise LCOE and blade mass, subject to the Stage-3 structural safety
        constraint. Use as a fast preview; validate shortlisted designs with CFD (Stage 2) below.
      </p>

      <div className="row">
        <label className="field inline">
          <span>Material</span>
          <select value={material} onChange={(e) => setMaterial(e.target.value)}>
            <option value="CFRP_UD">Carbon Fibre (CFRP)</option>
            <option value="GFRP_UD">Glass Fibre (GFRP)</option>
          </select>
        </label>
        <label className="field inline">
          <span>Population size</span>
          <input type="number" step={4} min={8} max={60} value={populationSize}
            onChange={(e) => setPopulationSize(parseInt(e.target.value))} />
        </label>
        <label className="field inline">
          <span>Generations</span>
          <input type="number" step={1} min={2} max={30} value={generations}
            onChange={(e) => setGenerations(parseInt(e.target.value))} />
        </label>
        <label className="field inline">
          <span>Operating TSR</span>
          <input type="number" step={0.05} min={0.5} max={6} value={operatingTsr}
            onChange={(e) => setOperatingTsr(parseFloat(e.target.value))} />
        </label>
        <button onClick={run} disabled={loading}>{loading ? "Optimizing..." : "Run Optimization"}</button>
      </div>

      {pareto.length > 0 && (
        <>
          <p className="stat">
            Found <strong>{pareto.length}</strong> Pareto-optimal designs
            {elapsed !== null && ` in ${elapsed.toFixed(1)}s`}. Bubble size = blade mass. Click a point to inspect.
          </p>

          <ResponsiveContainer width="100%" height={340}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" dataKey="aep" name="AEP" unit=" kWh"
                label={{ value: "AEP (kWh/yr)", position: "insideBottom", offset: -10 }} />
              <YAxis type="number" dataKey="lcoe" name="LCOE" unit=" $/kWh"
                label={{ value: "LCOE ($/kWh)", angle: -90, position: "insideLeft" }} />
              <ZAxis type="number" dataKey="mass" range={[40, 300]} name="Blade mass" unit=" kg" />
              <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(v) => Number(v).toFixed(3)} />
              <Scatter
                data={chartData}
                onClick={(point: any) => setSelected(point.design)}
                fill="#38bdf8"
              >
                {chartData.map((_, i) => (
                  <Cell key={i} cursor="pointer" />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>

          {selected && (
            <>
              <div className="validation-result ok">
                <p><strong>Selected design</strong></p>
                <p>AEP: {selected.aep_kwh.toFixed(0)} kWh/yr · LCOE: ${selected.lcoe_usd_per_kwh.toFixed(3)}/kWh ·
                  {" "}Blade mass: {selected.blade_mass_kg.toFixed(3)} kg</p>
                <p>Rotor radius: {selected.rotor_radius_m.toFixed(3)} m · Blade height: {selected.blade_height_m.toFixed(3)} m ·
                  {" "}Chord: {selected.chord_m.toFixed(3)} m</p>
                <p>Spar width fraction: {selected.spar_width_fraction.toFixed(2)} ·
                  {" "}Spar wall thickness: {(selected.spar_wall_thickness_m * 1000).toFixed(2)} mm</p>
                <p>Twist (root→tip): {selected.twist_angle_deg.toFixed(1)}° ·
                  {" "}Helical sweep (root→tip): {selected.helical_twist_deg.toFixed(1)}°
                  {selectedIsTwisted ? "" : " (straight blade)"}</p>
              </div>

              <h3>Validate this candidate with CFD</h3>
              <p className="hint">
                The Pareto front above comes from the fast Stage-1 BEM model. Before trusting this
                candidate, generate a Stage-2 OpenFOAM case at its actual geometry and operating point
                {selectedIsTwisted && " — including its twisted/helical blade shape, lofted into the mesh STL"}.
                Run it externally, then paste the resulting force coefficients into the CFD Validation
                panel below to compare against this design's BEM prediction.
              </p>
              <div className="row">
                <label className="field inline">
                  <span>CFD wind speed (m/s)</span>
                  <input type="number" step={0.5} value={cfdWindSpeed}
                    onChange={(e) => setCfdWindSpeed(parseFloat(e.target.value))} />
                </label>
                <button onClick={downloadCaseForSelected} disabled={downloadingCase}>
                  {downloadingCase ? "Building case..." : "Download OpenFOAM Case for Selected Design (.zip)"}
                </button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}