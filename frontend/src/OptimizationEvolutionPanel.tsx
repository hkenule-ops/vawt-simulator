import { useState, useRef, useEffect } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { HybridRotorIn, GenerationSnapshotOut } from "./types";
import { optimizeParetoFront } from "./api";

interface Props {
  geometry: HybridRotorIn;
}

export default function OptimizationEvolutionPanel({ geometry }: Props) {
  const [history, setHistory] = useState<GenerationSnapshotOut[]>([]);
  const [genIndex, setGenIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [loading, setLoading] = useState(false);
  const rafRef = useRef<number | null>(null);
  const lastTickRef = useRef<number>(0);

  const run = async () => {
    setLoading(true);
    setPlaying(false);
    try {
      const res = await optimizeParetoFront(
        geometry, "CFRP_UD", "CFRP_UD_PLY", 16, 12, 1.5, 2.25, 1, true
      );
      setHistory(res.generation_history);
      setGenIndex(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!playing || history.length === 0) return;
    const tick = (t: number) => {
      if (t - lastTickRef.current > 600 / speed) {
        lastTickRef.current = t;
        setGenIndex((i) => {
          if (i >= history.length - 1) {
            setPlaying(false);
            return i;
          }
          return i + 1;
        });
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [playing, speed, history.length]);

  const currentGen = history[genIndex];
  const chartData = currentGen
    ? currentGen.pareto_front.map((d) => ({ aep: d.aep_kwh, lcoe: d.lcoe_usd_per_kwh, mass: d.blade_mass_kg }))
    : [];

  return (
    <div className="panel cfd-panel">
      <h2>Stage 10 - Pareto Front Evolution</h2>
      <p className="hint">
        Watch NSGA-II actually converge, generation by generation — real per-generation snapshots
        from the Stage-8 optimizer, not an interpolated fake.
      </p>

      <div className="row">
        <button onClick={run} disabled={loading}>{loading ? "Running search..." : "Run & Capture Evolution"}</button>
        {history.length > 0 && (
          <>
            <button onClick={() => setPlaying((p) => !p)}>{playing ? "Pause" : "Play"}</button>
            <button onClick={() => { setGenIndex(0); setPlaying(false); }}>Restart</button>
            <label className="field inline">
              <span>Speed</span>
              <select value={speed} onChange={(e) => setSpeed(parseFloat(e.target.value))}>
                <option value={0.5}>0.5x</option>
                <option value={1}>1x</option>
                <option value={2}>2x</option>
                <option value={4}>4x</option>
              </select>
            </label>
          </>
        )}
      </div>

      {history.length > 0 && currentGen && (
        <>
          <div className="row" style={{ alignItems: "center" }}>
            <input
              type="range" min={0} max={history.length - 1} value={genIndex}
              onChange={(e) => { setGenIndex(parseInt(e.target.value)); setPlaying(false); }}
              style={{ flex: 1 }}
            />
            <span className="stat" style={{ margin: 0, minWidth: 140 }}>
              Generation {currentGen.generation} / {history.length} ({currentGen.n_eval} evals)
            </span>
          </div>

          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" dataKey="aep" name="AEP" unit=" kWh" domain={["dataMin - 100", "dataMax + 100"]}
                label={{ value: "AEP (kWh/yr)", position: "insideBottom", offset: -10 }} />
              <YAxis type="number" dataKey="lcoe" name="LCOE" unit=" $/kWh"
                label={{ value: "LCOE ($/kWh)", angle: -90, position: "insideLeft" }} />
              <ZAxis type="number" dataKey="mass" range={[50, 280]} name="Blade mass" unit=" kg" />
              <Tooltip formatter={(v) => Number(v).toFixed(3)} />
              <Scatter data={chartData} fill="#a78bfa" isAnimationActive={false} />
            </ScatterChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
