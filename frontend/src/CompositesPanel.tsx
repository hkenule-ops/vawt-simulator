import { useState } from "react";
import type { HybridRotorIn, CompositeCompareResponse } from "./types";
import { compareCompositeMaterials } from "./api";

interface Props {
  geometry: HybridRotorIn;
  windSpeed: number;
  tipSpeedRatio: number;
}

export default function CompositesPanel({ geometry, windSpeed, tipSpeedRatio }: Props) {
  const [targetSF, setTargetSF] = useState(1.5);
  const [result, setResult] = useState<CompositeCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const res = await compareCompositeMaterials(geometry, windSpeed, tipSpeedRatio, targetSF);
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  const rows = result
    ? [
        { label: "Carbon Fibre (CFRP)", d: result.cfrp },
        { label: "Glass Fibre (GFRP)", d: result.gfrp },
      ]
    : [];

  return (
    <div className="panel cfd-panel">
      <h2>Stage 4 - Composite Spar Optimization</h2>
      <p className="hint">
        Classical Laminate Theory spar cap ([0]<sub>n</sub>) and shear web ([±45]<sub>ns</sub>) layup
        search, minimizing mass subject to a target safety factor, at V={windSpeed} m/s, TSR={tipSpeedRatio}.
      </p>

      <div className="row">
        <label className="field inline">
          <span>Target safety factor</span>
          <input type="number" step={0.1} min={1.0} value={targetSF}
            onChange={(e) => setTargetSF(parseFloat(e.target.value))} />
        </label>
        <button onClick={run} disabled={loading}>{loading ? "Optimizing..." : "Compare Carbon vs Glass"}</button>
      </div>

      {result && (
        <>
          <table className="compare-table">
            <thead>
              <tr>
                <th>Material</th>
                <th>Cap plies</th>
                <th>Web pairs</th>
                <th>Spar mass</th>
                <th>Cap thickness</th>
                <th>Safety factor</th>
                <th>Feasible</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label} className={row.d.feasible ? "" : "infeasible-row"}>
                  <td>{row.label}</td>
                  <td>{row.d.n_cap_plies}</td>
                  <td>{row.d.n_web_pairs}</td>
                  <td>{(row.d.spar_mass_kg * 1000).toFixed(0)} g</td>
                  <td>{(row.d.cap_thickness_m * 1000).toFixed(2)} mm</td>
                  <td>{row.d.safety_factor.toFixed(2)}</td>
                  <td>{row.d.feasible ? "✓" : "✗"}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {result.cfrp.feasible && result.gfrp.feasible && (
            <p className="stat">
              {result.cfrp.spar_mass_kg < result.gfrp.spar_mass_kg ? (
                <>Carbon fibre wins on mass: <strong>{((1 - result.cfrp.spar_mass_kg / result.gfrp.spar_mass_kg) * 100).toFixed(0)}% lighter</strong> than glass fibre for this load case.</>
              ) : (
                <>Glass fibre matches or beats carbon fibre on mass for this load case — carbon's strength advantage isn't needed here.</>
              )}
            </p>
          )}
          {!result.gfrp.feasible && result.cfrp.feasible && (
            <p className="stat">Glass fibre could not meet the target safety factor within the search range at this load — carbon fibre is required (or a larger/wider spar).</p>
          )}

          {rows.map((row) =>
            row.d.warnings.length > 0 ? (
              <ul className="warnings" key={row.label + "-warn"}>
                {row.d.warnings.map((w, i) => <li key={i}>{row.label}: ⚠ {w}</li>)}
              </ul>
            ) : null
          )}
        </>
      )}
    </div>
  );
}
