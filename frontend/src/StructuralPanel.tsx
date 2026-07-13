import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import type { HybridRotorIn, StructuralAnalysisResponse, MaterialOut } from "./types";
import { listMaterials, analyzeBladeStructure } from "./api";

interface Props {
  geometry: HybridRotorIn;
  windSpeed: number;
  tipSpeedRatio: number;
}

export default function StructuralPanel({ geometry, windSpeed, tipSpeedRatio }: Props) {
  const [materials, setMaterials] = useState<MaterialOut[]>([]);
  const [material, setMaterial] = useState("CFRP_UD");
  const [sparWidthFraction, setSparWidthFraction] = useState(0.5);
  const [wallThicknessMm, setWallThicknessMm] = useState(3.0);
  const [boundary, setBoundary] = useState<"pinned-pinned" | "cantilever">("pinned-pinned");
  const [result, setResult] = useState<StructuralAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listMaterials().then(setMaterials).catch(() => {});
  }, []);

  const runAnalysis = async () => {
    setLoading(true);
    try {
      const res = await analyzeBladeStructure(
        geometry, material, windSpeed, tipSpeedRatio,
        sparWidthFraction, wallThicknessMm / 1000, boundary
      );
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  const deflectionData = result
    ? result.flapwise.x_m.map((x, i) => ({
        x,
        flapwise_mm: result.flapwise.deflection_m[i] * 1000,
        edgewise_mm: result.edgewise.deflection_m[i] * 1000,
      }))
    : [];

  const momentData = result
    ? result.flapwise.x_m.map((x, i) => ({
        x,
        flapwise_nm: result.flapwise.bending_moment_nm[i],
        edgewise_nm: result.edgewise.bending_moment_nm[i],
      }))
    : [];

  return (
    <div className="panel cfd-panel">
      <h2>Stage 3 - Structural Analysis (FEA)</h2>
      <p className="hint">
        Euler-Bernoulli beam finite element analysis of the blade spar under peak aerodynamic
        loading (from Stage 1) plus centrifugal loading, at V={windSpeed} m/s, TSR={tipSpeedRatio}.
      </p>

      <div className="row">
        <label className="field inline">
          <span>Material</span>
          <select value={material} onChange={(e) => setMaterial(e.target.value)}>
            {materials.map((m) => (
              <option key={m.key} value={m.key}>{m.name}</option>
            ))}
          </select>
        </label>
        <label className="field inline">
          <span>Spar width (fraction of chord)</span>
          <input type="number" step={0.05} min={0.1} max={0.9} value={sparWidthFraction}
            onChange={(e) => setSparWidthFraction(parseFloat(e.target.value))} />
        </label>
        <label className="field inline">
          <span>Spar wall thickness (mm)</span>
          <input type="number" step={0.5} min={0.5} value={wallThicknessMm}
            onChange={(e) => setWallThicknessMm(parseFloat(e.target.value))} />
        </label>
        <label className="field inline">
          <span>Boundary condition</span>
          <select value={boundary} onChange={(e) => setBoundary(e.target.value as any)}>
            <option value="pinned-pinned">Pinned-pinned (strut-supported)</option>
            <option value="cantilever">Cantilever</option>
          </select>
        </label>
        <button onClick={runAnalysis} disabled={loading}>{loading ? "Solving..." : "Run FEA"}</button>
      </div>

      {result && (
        <>
          <div className={`validation-result ${result.safety_factor >= 1.5 ? "ok" : "warn"}`}>
            <p>Spar mass: <strong>{result.spar_mass_kg.toFixed(2)} kg</strong> ·
              {" "}Combined max stress: <strong>{(result.combined_max_stress_pa / 1e6).toFixed(1)} MPa</strong> ·
              {" "}Yield: {(result.yield_strength_pa / 1e6).toFixed(0)} MPa</p>
            <p>Safety factor: <strong>{result.safety_factor.toFixed(2)}</strong>{" "}
              ({result.safety_factor >= 1.5 ? "meets" : "below"} the 1.5 design threshold) ·
              {" "}Buckling SF: {result.buckling_safety_factor.toFixed(1)}</p>
            <p>Flapwise load: {result.flapwise_distributed_load_n_m.toFixed(1)} N/m
              (centrifugal: {result.centrifugal_distributed_load_n_m.toFixed(1)} N/m) ·
              {" "}Edgewise load: {result.edgewise_distributed_load_n_m.toFixed(1)} N/m</p>
          </div>

          {result.warnings.length > 0 && (
            <ul className="warnings">
              {result.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
            </ul>
          )}

          <h3>Spanwise deflection</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={deflectionData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" label={{ value: "Span position (m)", position: "insideBottom", offset: -5 }} />
              <YAxis label={{ value: "Deflection (mm)", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="flapwise_mm" name="Flapwise" stroke="#f472b6" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="edgewise_mm" name="Edgewise" stroke="#a78bfa" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>

          <h3>Bending moment distribution</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={momentData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" label={{ value: "Span position (m)", position: "insideBottom", offset: -5 }} />
              <YAxis label={{ value: "Moment (N·m)", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="flapwise_nm" name="Flapwise" stroke="#fb923c" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="edgewise_nm" name="Edgewise" stroke="#22d3ee" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
