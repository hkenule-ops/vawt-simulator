import { useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import type { HybridRotorIn, ParetoDesignOut } from "./types";
import { optimizeParetoFront } from "./api";

interface Props {
  geometry: HybridRotorIn;
}

export default function OptimizationPanel({ geometry }: Props) {
  const [material, setMaterial] = useState("CFRP_UD");
  const [populationSize, setPopulationSize] = useState(24);
  const [generations, setGenerations] = useState(10);
  const [pareto, setPareto] = useState<ParetoDesignOut[]>([]);
  const [selected, setSelected] = useState<ParetoDesignOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);

  const plyKeyFor = (mat: string) => (mat === "GFRP_UD" ? "GFRP_UD_PLY" : "CFRP_UD_PLY");

  const run = async () => {
    setLoading(true);
    const t0 = performance.now();
    try {
      const res = await optimizeParetoFront(geometry, material, plyKeyFor(material), populationSize, generations);
      setPareto(res.pareto_front);
      setElapsed((performance.now() - t0) / 1000);
      setSelected(null);
    } finally {
      setLoading(false);
    }
  };

  const chartData = pareto.map((d) => ({
    aep: d.aep_kwh,
    lcoe: d.lcoe_usd_per_kwh,
    mass: d.blade_mass_kg,
    design: d,
  }));

  return (
    <div className="panel cfd-panel">
      <h2>Stage 8 - Multi-Objective Optimization</h2>
      <p className="hint">
        NSGA-II (pymoo) search over rotor radius, blade height, chord, and spar sizing — maximizing
        AEP, minimizing LCOE and blade mass, subject to the Stage-3 structural safety constraint.
        Fast preview search: promising designs should still go through the full pipeline before
        being trusted for a final decision.
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
            <div className="validation-result ok">
              <p><strong>Selected design</strong></p>
              <p>AEP: {selected.aep_kwh.toFixed(0)} kWh/yr · LCOE: ${selected.lcoe_usd_per_kwh.toFixed(3)}/kWh ·
                {" "}Blade mass: {selected.blade_mass_kg.toFixed(3)} kg</p>
              <p>Rotor radius: {selected.rotor_radius_m.toFixed(3)} m · Blade height: {selected.blade_height_m.toFixed(3)} m ·
                {" "}Chord: {selected.chord_m.toFixed(3)} m</p>
              <p>Spar width fraction: {selected.spar_width_fraction.toFixed(2)} ·
                {" "}Spar wall thickness: {(selected.spar_wall_thickness_m * 1000).toFixed(2)} mm</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
