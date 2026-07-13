import { useEffect, useState, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import GeometryForm from "./GeometryForm";
import CFDPanel from "./CFDPanel";
import StructuralPanel from "./StructuralPanel";
import CompositesPanel from "./CompositesPanel";
import FatiguePanel from "./FatiguePanel";
import AeroelasticPanel from "./AeroelasticPanel";
import EconomicsPanel from "./EconomicsPanel";
import OptimizationPanel from "./OptimizationPanel";
import TurbineViewer3D from "./TurbineViewer3D";
import OptimizationEvolutionPanel from "./OptimizationEvolutionPanel";
import ModalVibrationAnimation from "./ModalVibrationAnimation";
import BladeDeformationAnimation from "./BladeDeformationAnimation";
import ReportingValidationPanel from "./ReportingValidationPanel";
import { DEFAULT_GEOMETRY } from "./types";
import type { HybridRotorIn } from "./types";
import { checkHealth, getCpLambdaCurve, getPowerCurve, validateGeometry } from "./api";
import "./app.css";

const DEFAULT_WIND_SPEEDS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];

export default function App() {
  const [geometry, setGeometry] = useState<HybridRotorIn>(DEFAULT_GEOMETRY);
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [cpLambda, setCpLambda] = useState<any[]>([]);
  const [powerCurve, setPowerCurve] = useState<any[]>([]);
  const [ratedPower, setRatedPower] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkHealth().then(setBackendUp);
  }, []);

  const runAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [validation, cpRes, pcRes] = await Promise.all([
        validateGeometry(geometry),
        getCpLambdaCurve(geometry, 8.0, 0.5, 5.0, 30),
        getPowerCurve(geometry, DEFAULT_WIND_SPEEDS),
      ]);
      setWarnings([...validation, ...cpRes.warnings, ...pcRes.warnings]);
      setCpLambda(cpRes.points.map((p) => ({ tsr: Number(p.tip_speed_ratio.toFixed(2)), cp: p.system_cp })));
      setPowerCurve(
        pcRes.curve.map((c) => ({
          wind_speed: c.wind_speed_ms,
          power_w: c.operating_point?.total_power_w ?? 0,
        }))
      );
      setRatedPower(pcRes.rated_power_w);
    } catch (e: any) {
      setError(e?.message ?? "Analysis failed");
    } finally {
      setLoading(false);
    }
  }, [geometry]);

  useEffect(() => {
    if (backendUp) runAnalysis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendUp]);

  return (
    <div className="app">
      <header className="topbar">
        <h1>Hybrid VAWT CAE Platform</h1>
        <span className={`status ${backendUp ? "ok" : "down"}`}>
          {backendUp === null ? "checking backend..." : backendUp ? "backend connected" : "backend offline"}
        </span>
      </header>

      <div className="layout">
        <GeometryForm geometry={geometry} onChange={setGeometry} />

        <div className="panel results">
          <div className="results-header">
            <h2>Stage 1 - BEM Results</h2>
            <button onClick={runAnalysis} disabled={loading || !backendUp}>
              {loading ? "Solving..." : "Run Analysis"}
            </button>
          </div>

          {error && <p className="error">{error}</p>}
          {warnings.length > 0 && (
            <ul className="warnings">
              {warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
            </ul>
          )}

          {ratedPower !== null && (
            <p className="stat">
              Peak predicted power across sweep: <strong>{ratedPower.toFixed(1)} W</strong>
              {" "}(target: {geometry.target_power_w} W)
            </p>
          )}

          <h3>Cp vs Tip-Speed Ratio (at 8 m/s)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={cpLambda}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="tsr" label={{ value: "TSR (λ)", position: "insideBottom", offset: -5 }} />
              <YAxis label={{ value: "Cp", angle: -90, position: "insideLeft" }} domain={[0, 0.6]} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="cp" name="System Cp" stroke="#2563eb" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>

          <h3>Power Curve (MPPT, cut-in to cut-out)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={powerCurve}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="wind_speed" label={{ value: "Wind speed (m/s)", position: "insideBottom", offset: -5 }} />
              <YAxis label={{ value: "Power (W)", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="power_w" name="Total power" stroke="#16a34a" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <CFDPanel geometry={geometry} windSpeed={geometry.rated_wind_speed_ms} tipSpeedRatio={2.25} />
        <StructuralPanel geometry={geometry} windSpeed={geometry.rated_wind_speed_ms} tipSpeedRatio={2.25} />
        <CompositesPanel geometry={geometry} windSpeed={geometry.rated_wind_speed_ms} tipSpeedRatio={2.25} />
        <FatiguePanel geometry={geometry} tipSpeedRatio={2.25} />
        <AeroelasticPanel geometry={geometry} tipSpeedRatio={2.25} />
        <EconomicsPanel geometry={geometry} />
        <OptimizationPanel geometry={geometry} />
        <TurbineViewer3D geometry={geometry} />
        <OptimizationEvolutionPanel geometry={geometry} />
        <ModalVibrationAnimation geometry={geometry} tipSpeedRatio={2.25} />
        <BladeDeformationAnimation geometry={geometry} windSpeed={geometry.rated_wind_speed_ms} tipSpeedRatio={2.25} />
        <ReportingValidationPanel geometry={geometry} />
      </div>
    </div>
  );
}
