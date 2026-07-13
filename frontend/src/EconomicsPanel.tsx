import { useState, useEffect } from "react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { HybridRotorIn, EconomicAnalysisResponse, MaterialOut } from "./types";
import { analyzeEconomics, listMaterials } from "./api";

interface Props {
  geometry: HybridRotorIn;
}

const COLORS = ["#f472b6", "#a78bfa", "#38bdf8", "#fb923c", "#22d3ee"];

export default function EconomicsPanel({ geometry }: Props) {
  const [materials, setMaterials] = useState<MaterialOut[]>([]);
  const [material, setMaterial] = useState("CFRP_UD");
  const [price, setPrice] = useState(0.15);
  const [discountRate, setDiscountRate] = useState(0.06);
  const [lifetime, setLifetime] = useState(20);
  const [result, setResult] = useState<EconomicAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listMaterials().then(setMaterials).catch(() => {});
  }, []);

  const plyKeyFor = (mat: string) => (mat === "GFRP_UD" ? "GFRP_UD_PLY" : "CFRP_UD_PLY");

  const run = async () => {
    setLoading(true);
    try {
      const res = await analyzeEconomics(geometry, material, plyKeyFor(material), price, discountRate, lifetime);
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  const capexData = result
    ? [
        { name: "Blade material", value: result.capex.blade_material_cost_usd },
        { name: "Blade fabrication", value: result.capex.blade_fabrication_cost_usd },
        { name: "Generator/electronics", value: result.capex.generator_electronics_cost_usd },
        { name: "Tower/foundation", value: result.capex.tower_foundation_cost_usd },
        { name: "Installation", value: result.capex.installation_cost_usd },
      ]
    : [];

  return (
    <div className="panel cfd-panel">
      <h2>Stage 7 - Economics</h2>
      <p className="hint">
        AEP from the Stage-1 power curve (rated-power-limited, with system losses) integrated
        against a Weibull wind distribution; CAPEX grounded in the real Stage-4 spar mass.
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
          <span>Electricity price ($/kWh)</span>
          <input type="number" step={0.01} min={0.01} value={price}
            onChange={(e) => setPrice(parseFloat(e.target.value))} />
        </label>
        <label className="field inline">
          <span>Discount rate</span>
          <input type="number" step={0.01} min={0} max={0.5} value={discountRate}
            onChange={(e) => setDiscountRate(parseFloat(e.target.value))} />
        </label>
        <label className="field inline">
          <span>Project lifetime (yrs)</span>
          <input type="number" step={1} min={1} value={lifetime}
            onChange={(e) => setLifetime(parseInt(e.target.value))} />
        </label>
        <button onClick={run} disabled={loading}>{loading ? "Analyzing..." : "Run Economic Analysis"}</button>
      </div>

      {result && (
        <>
          <div className={`validation-result ${result.npv_usd >= 0 ? "ok" : "warn"}`}>
            <p>AEP: <strong>{result.aep.aep_kwh.toFixed(0)} kWh/yr</strong> ·
              {" "}Capacity factor: {(result.aep.capacity_factor * 100).toFixed(1)}% ·
              {" "}Total CAPEX: <strong>${result.capex.total_capex_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong></p>
            <p>LCOE: <strong>${result.lcoe_usd_per_kwh.toFixed(3)}/kWh</strong> ·
              {" "}NPV: <strong>${result.npv_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong> ·
              {" "}IRR: {result.irr !== null ? `${(result.irr * 100).toFixed(1)}%` : "N/A"} ·
              {" "}Payback: {result.simple_payback_years === Infinity ? "never" : `${result.simple_payback_years.toFixed(1)} yrs`}</p>
          </div>

          {result.warnings.length > 0 && (
            <ul className="warnings">
              {result.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
            </ul>
          )}

          <h3>CAPEX breakdown</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={capexData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90}
                label={(entry) => `$${entry.value.toFixed(0)}`}>
                {capexData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Legend />
              <Tooltip formatter={(v) => `$${Number(v).toFixed(2)}`} />
            </PieChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
