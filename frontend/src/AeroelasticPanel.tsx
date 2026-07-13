import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar,
} from "recharts";
import type { HybridRotorIn, AeroelasticAnalysisResponse, MaterialOut } from "./types";
import { analyzeAeroelastics, listMaterials } from "./api";

interface Props {
  geometry: HybridRotorIn;
  tipSpeedRatio: number;
}

export default function AeroelasticPanel({ geometry, tipSpeedRatio }: Props) {
  const [materials, setMaterials] = useState<MaterialOut[]>([]);
  const [material, setMaterial] = useState("CFRP_UD");
  const [result, setResult] = useState<AeroelasticAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listMaterials().then(setMaterials).catch(() => {});
  }, []);

  const run = async () => {
    setLoading(true);
    try {
      const res = await analyzeAeroelastics(geometry, material, tipSpeedRatio);
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  const campbellData = result
    ? result.campbell.rpm_range.map((rpm, i) => {
        const point: any = { rpm };
        Object.entries(result.campbell.excitation_lines_hz).forEach(([h, freqs]) => {
          point[`${h}P`] = freqs[i];
        });
        return point;
      })
    : [];

  const harmonicData = result
    ? result.harmonics.harmonic_number.map((n, i) => ({
        harmonic: `${n}P`,
        amplitude: result.harmonics.amplitude_n_m[i],
      }))
    : [];

  const exactResonances = result?.campbell.resonance_risks.filter((r) => r.margin_percent === 0) ?? [];

  return (
    <div className="panel cfd-panel">
      <h2>Stage 6 - Aeroelasticity</h2>
      <p className="hint">
        Modal analysis (natural frequencies, validated against closed-form beam vibration theory)
        overlaid with real NP excitation lines and the actual harmonic content of the Stage-1 aero load.
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
        <button onClick={run} disabled={loading}>{loading ? "Solving..." : "Run Modal Analysis"}</button>
      </div>

      {result && (
        <>
          <div className={`validation-result ${exactResonances.length === 0 ? "ok" : "warn"}`}>
            <p>Natural frequencies: <strong>{result.modal.natural_frequencies_hz.map((f) => f.toFixed(1)).join(", ")} Hz</strong></p>
            <p>Operating RPM range: {result.operating_rpm_min.toFixed(0)} - {result.operating_rpm_max.toFixed(0)} ·
              {" "}Dominant load harmonic(s): {result.harmonics.dominant_harmonics.join(", ")}P</p>
            {exactResonances.length > 0 ? (
              <p>⚠ {exactResonances.length} resonance crossing(s) within operating range</p>
            ) : (
              <p>No exact resonance crossings within the operating RPM range</p>
            )}
          </div>

          {result.warnings.length > 0 && (
            <ul className="warnings">
              {result.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
            </ul>
          )}

          <h3>Campbell diagram</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={campbellData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="rpm" label={{ value: "RPM", position: "insideBottom", offset: -5 }} />
              <YAxis label={{ value: "Frequency (Hz)", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              {Object.keys(result.campbell.excitation_lines_hz).map((h, i) => (
                <Line key={h} type="monotone" dataKey={`${h}P`} stroke={`hsl(${i * 50}, 70%, 60%)`}
                  dot={false} strokeWidth={1.5} strokeDasharray={h === "1" ? undefined : "4 3"} />
              ))}
              {result.modal.natural_frequencies_hz.map((f, i) => (
                <Line key={`mode${i}`} type="monotone"
                  data={result.campbell.rpm_range.map((rpm) => ({ rpm, [`mode${i + 1}`]: f }))}
                  dataKey={`mode${i + 1}`} name={`Mode ${i + 1} (${f.toFixed(1)} Hz)`}
                  stroke="#e5e9f0" strokeWidth={2} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>

          <h3>Aerodynamic load harmonic content (at rated wind speed)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={harmonicData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="harmonic" />
              <YAxis label={{ value: "Amplitude (N/m)", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Bar dataKey="amplitude" fill="#38bdf8" />
            </BarChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
