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
import ErrorBoundary from "./ErrorBoundary";
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

  const statusClass =
    backendUp === null ? "checking" : backendUp ? "ok" : "down";
  const statusLabel =
    backendUp === null
      ? "Checking backend…"
      : backendUp
        ? "Backend connected"
        : "Backend offline";

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-brand">
          <div className="logo-mark" aria-hidden>
            V
          </div>
          <div>
            <h1>Hybrid VAWT CAE Platform</h1>
            <span className="topbar-subtitle">
              Design · aero · structure · economics · optimisation
            </span>
          </div>
        </div>
        <span className={`status ${statusClass}`}>{statusLabel}</span>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <GeometryForm geometry={geometry} onChange={setGeometry} />
        </aside>

        <div className="main-stack">
          <div className="panel results">
            <div className="results-header">
              <div>
                <h2>
                  BEM Results
                  <span className="stage-badge">Stage 1</span>
                </h2>
                <p className="panel-desc" style={{ marginBottom: 0 }}>
                  Blade-element momentum performance at the current geometry. Power and Cp respond
                  strongly to radius, height, solidity, and the wind envelope set on the left.
                </p>
              </div>
              <button onClick={runAnalysis} disabled={loading || !backendUp}>
                {loading ? "Solving…" : "Run Analysis"}
              </button>
            </div>

            {error && <p className="error">{error}</p>}
            {warnings.length > 0 && (
              <ul className="warnings">
                {warnings.map((w, i) => (
                  <li key={i}>⚠ {w}</li>
                ))}
              </ul>
            )}

            {ratedPower !== null && (
              <p className="stat">
                Peak predicted power across sweep:{" "}
                <strong>{ratedPower.toFixed(1)} W</strong>
                {" · "}
                target: {geometry.target_power_w} W
              </p>
            )}

            <h3>Cp vs tip-speed ratio (at 8 m/s)</h3>
            <p className="hint">
              Peak Cp and the TSR at which it occurs shift with solidity and airfoil choice.
            </p>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={cpLambda}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="tsr"
                  label={{ value: "TSR (λ)", position: "insideBottom", offset: -5 }}
                />
                <YAxis
                  label={{ value: "Cp", angle: -90, position: "insideLeft" }}
                  domain={[0, 0.6]}
                />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="cp"
                  name="System Cp"
                  stroke="#38bdf8"
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>

            <h3>Power curve (MPPT, cut-in to cut-out)</h3>
            <p className="hint">
              How much power the hybrid rotor delivers versus wind speed — the basis for AEP.
            </p>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={powerCurve}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="wind_speed"
                  label={{ value: "Wind speed (m/s)", position: "insideBottom", offset: -5 }}
                />
                <YAxis
                  label={{ value: "Power (W)", angle: -90, position: "insideLeft" }}
                />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="power_w"
                  name="Total power"
                  stroke="#4ade80"
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <CFDPanel
            geometry={geometry}
            windSpeed={geometry.rated_wind_speed_ms}
            tipSpeedRatio={2.25}
          />
          <StructuralPanel
            geometry={geometry}
            windSpeed={geometry.rated_wind_speed_ms}
            tipSpeedRatio={2.25}
          />
          <CompositesPanel
            geometry={geometry}
            windSpeed={geometry.rated_wind_speed_ms}
            tipSpeedRatio={2.25}
          />
          <FatiguePanel geometry={geometry} tipSpeedRatio={2.25} />
          <AeroelasticPanel geometry={geometry} tipSpeedRatio={2.25} />
          <EconomicsPanel geometry={geometry} />
          <OptimizationPanel geometry={geometry} />
          <ErrorBoundary label="3D viewer">
            <TurbineViewer3D geometry={geometry} />
          </ErrorBoundary>
          <OptimizationEvolutionPanel geometry={geometry} />
          <ModalVibrationAnimation geometry={geometry} tipSpeedRatio={2.25} />
          <BladeDeformationAnimation
            geometry={geometry}
            windSpeed={geometry.rated_wind_speed_ms}
            tipSpeedRatio={2.25}
          />
          <ReportingValidationPanel geometry={geometry} />
        </div>
      </div>
    </div>
  );
}
