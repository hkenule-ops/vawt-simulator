import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import type { HybridRotorIn, TorqueSpeedCurveResponse, GeneratorAnalysisResponse } from "./types";
import { getTorqueSpeedCurve, analyzeGenerator } from "./api";

interface Props {
  geometry: HybridRotorIn;
  tipSpeedRatio: number;
}

export default function GeneratorTowerPanel({ geometry, tipSpeedRatio }: Props) {
  const [curve, setCurve] = useState<TorqueSpeedCurveResponse | null>(null);
  const [operating, setOperating] = useState<GeneratorAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const [curveRes, opRes] = await Promise.all([
        getTorqueSpeedCurve(geometry, 600, 30),
        analyzeGenerator(geometry, geometry.rated_wind_speed_ms, tipSpeedRatio),
      ]);
      setCurve(curveRes);
      setOperating(opRes);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? "Generator analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  const torqueSpeedData = curve
    ? curve.points.map((p) => ({
        rpm: Number(p.rpm.toFixed(0)),
        torque_nm: Number(p.mechanical_torque_nm.toFixed(3)),
        power_w: Number(p.electrical_power_w.toFixed(1)),
        efficiency_pct: Number((p.efficiency * 100).toFixed(1)),
      }))
    : [];

  return (
    <div className="panel cfd-panel">
      <h2>
        Generator / Alternator &amp; Tower
        <span className="stage-badge">Stage 13</span>
      </h2>
      <p className="panel-desc">
        Couples the rotor's aerodynamic output to a permanent-magnet synchronous
        generator/alternator (torque-speed characteristic, cogging torque, copper + core
        losses) and accounts for the support tower's effect on hub height and — optionally —
        wind shear correction to the wind speeds fed into the aero solver.
      </p>

      <div className="impact-callout">
        <strong>Generator levers:</strong> torque constant and phase resistance set how much of
        the rotor's mechanical power survives to electrical output; cogging torque can prevent
        low-wind self-starting even when the BEM power curve looks fine once spinning.
        <strong> Tower:</strong> a taller tower moves the rotor away from ground-level wind shear
        — usually a stronger, steadier resource higher up.
      </div>

      <div className="form-section">
        <button onClick={run} disabled={loading}>
          {loading ? "Analyzing…" : "Run Generator + Tower Analysis"}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {operating && (
        <>
          <h3>
            Operating point at rated wind ({geometry.rated_wind_speed_ms} m/s, TSR{" "}
            {tipSpeedRatio.toFixed(2)})
          </h3>
          {operating.warnings.length > 0 && (
            <ul className="warnings">
              {operating.warnings.map((w, i) => (
                <li key={i}>⚠ {w}</li>
              ))}
            </ul>
          )}
          <div className="grid">
            <p className="stat">
              Hub height: <strong>{operating.hub_height_m.toFixed(2)} m</strong>
              {" "}(tower {geometry.tower.height_m.toFixed(2)} m + half blade height)
            </p>
            <p className="stat">
              Wind at hub: <strong>{operating.wind_speed_at_hub_ms.toFixed(2)} m/s</strong>
              {geometry.tower.apply_wind_shear ? "" : " (shear correction off — same as reference)"}
            </p>
            <p className="stat">
              Mechanical power (rotor): <strong>{operating.aero_operating_point.total_power_w.toFixed(0)} W</strong>
            </p>
            <p className="stat">
              Electrical power (generator output):{" "}
              <strong>{operating.generator_operating_point.electrical_power_w.toFixed(0)} W</strong>
            </p>
            <p className="stat">
              Generator efficiency:{" "}
              <strong>{(operating.generator_operating_point.efficiency * 100).toFixed(1)}%</strong>
            </p>
            <p className="stat">
              Shaft speed: <strong>{operating.generator_operating_point.rpm.toFixed(0)} rpm</strong>
              {" "}({operating.generator_operating_point.electrical_freq_hz.toFixed(1)} Hz electrical)
            </p>
            <p className="stat">
              Terminal voltage (est.): <strong>{operating.generator_operating_point.terminal_voltage_v.toFixed(1)} V</strong>
            </p>
            <p className="stat">
              Copper / core loss:{" "}
              <strong>
                {operating.generator_operating_point.copper_loss_w.toFixed(1)} W /{" "}
                {operating.generator_operating_point.core_loss_w.toFixed(1)} W
              </strong>
            </p>
          </div>

          <h3>Self-starting (breakaway) check</h3>
          <p className={`stat ${operating.breakaway_check.can_break_away ? "" : "error"}`}>
            {operating.breakaway_check.can_break_away
              ? `✓ Rotor starting torque (${operating.breakaway_check.rotor_starting_torque_nm.toFixed(3)} Nm) exceeds cogging torque (${operating.breakaway_check.cogging_torque_peak_nm.toFixed(3)} Nm) — margin ${operating.breakaway_check.margin_nm.toFixed(3)} Nm.`
              : `✗ Cogging torque (${operating.breakaway_check.cogging_torque_peak_nm.toFixed(3)} Nm) exceeds rotor starting torque (${operating.breakaway_check.rotor_starting_torque_nm.toFixed(3)} Nm) — rotor may not self-start at rated wind speed.`}
          </p>
        </>
      )}

      {curve && (
        <>
          <h3>Generator torque-speed characteristic</h3>
          <p className="hint">
            Intrinsic curve for the fixed reflected load resistance in the generator
            parameters — independent of the rotor, this is what you'd match against a
            datasheet when picking a generator.
          </p>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={torqueSpeedData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="rpm" label={{ value: "Shaft speed (rpm)", position: "insideBottom", offset: -5 }} />
              <YAxis yAxisId="left" label={{ value: "Torque (Nm)", angle: -90, position: "insideLeft" }} />
              <YAxis yAxisId="right" orientation="right" label={{ value: "Power (W)", angle: 90, position: "insideRight" }} />
              <Tooltip />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="torque_nm" name="Torque (Nm)" stroke="#f59e0b" dot={false} strokeWidth={2} />
              <Line yAxisId="right" type="monotone" dataKey="power_w" name="Electrical power (W)" stroke="#4ade80" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>

          <h3>Efficiency vs shaft speed</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={torqueSpeedData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="rpm" label={{ value: "Shaft speed (rpm)", position: "insideBottom", offset: -5 }} />
              <YAxis domain={[0, 100]} label={{ value: "Efficiency (%)", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Line type="monotone" dataKey="efficiency_pct" name="Efficiency (%)" stroke="#38bdf8" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
          <p className="hint">
            Cogging ripple frequency at max rpm swept: {curve.cogging_ripple_frequency_hz_at_max_rpm.toFixed(1)} Hz
            — check against the Stage 6 Campbell diagram if this coincides with a structural natural frequency.
          </p>
        </>
      )}
    </div>
  );
}