import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { HybridRotorIn, FatigueAnalysisResponse, MaterialOut } from "./types";
import { analyzeFatigue, listMaterials } from "./api";

interface Props {
  geometry: HybridRotorIn;
  tipSpeedRatio: number;
}

export default function FatiguePanel({ geometry, tipSpeedRatio }: Props) {
  const [materials, setMaterials] = useState<MaterialOut[]>([]);
  const [material, setMaterial] = useState("CFRP_UD");
  const [weibullK, setWeibullK] = useState(2.0);
  const [weibullC, setWeibullC] = useState(7.0);
  const [result, setResult] = useState<FatigueAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listMaterials().then(setMaterials).catch(() => {});
  }, []);

  const plyKeyFor = (mat: string) => (mat === "GFRP_UD" ? "GFRP_UD_PLY" : "CFRP_UD_PLY");

  const run = async () => {
    setLoading(true);
    try {
      const res = await analyzeFatigue(geometry, material, plyKeyFor(material), tipSpeedRatio, weibullK, weibullC);
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  const chartData = result
    ? result.wind_bins_ms.map((v, i) => ({ v, damage: result.damage_by_bin[i] }))
    : [];

  const lifeDisplay = result
    ? result.estimated_life_years >= 1000
      ? "1000+ years (effectively unlimited)"
      : `${result.estimated_life_years.toFixed(1)} years`
    : null;

  return (
    <div className="panel cfd-panel">
      <h2>Stage 5 - Fatigue Analysis</h2>
      <p className="hint">
        Rainflow counting of the per-revolution azimuthal stress cycle (the dominant VAWT fatigue
        driver), weighted across a Weibull wind distribution, accumulated via Miner's rule.
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
          <span>Weibull shape (k)</span>
          <input type="number" step={0.1} min={1} max={3.5} value={weibullK}
            onChange={(e) => setWeibullK(parseFloat(e.target.value))} />
        </label>
        <label className="field inline">
          <span>Weibull scale (c, m/s)</span>
          <input type="number" step={0.5} min={2} max={15} value={weibullC}
            onChange={(e) => setWeibullC(parseFloat(e.target.value))} />
        </label>
        <button onClick={run} disabled={loading}>{loading ? "Analyzing..." : "Run Fatigue Analysis"}</button>
      </div>

      {result && (
        <>
          <div className={`validation-result ${result.estimated_life_years >= 20 ? "ok" : "warn"}`}>
            <p>Estimated fatigue life: <strong>{lifeDisplay}</strong>{" "}
              ({result.estimated_life_years >= 20 ? "meets" : "below"} the common 20-year design target)</p>
            <p>Total cycles/year: {(result.total_cycles_per_year / 1e6).toFixed(1)} million ·
              {" "}Dominant stress range: {(result.dominant_stress_range_pa / 1e6).toFixed(1)} MPa</p>
          </div>

          {result.warnings.length > 0 && (
            <ul className="warnings">
              {result.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
            </ul>
          )}

          <h3>Annual damage contribution by wind speed bin</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="v" label={{ value: "Wind speed (m/s)", position: "insideBottom", offset: -5 }} />
              <YAxis label={{ value: "Annual damage", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Bar dataKey="damage" fill="#fb7185" />
            </BarChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
