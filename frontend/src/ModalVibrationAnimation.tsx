import { useState, useEffect, useRef } from "react";
import type { HybridRotorIn, ModalResultOut } from "./types";
import { analyzeAeroelastics } from "./api";

interface Props {
  geometry: HybridRotorIn;
  tipSpeedRatio: number;
}

const W = 560;
const H = 220;
const AMPLITUDE_PX = 70;

export default function ModalVibrationAnimation({ geometry, tipSpeedRatio }: Props) {
  const [modal, setModal] = useState<ModalResultOut | null>(null);
  const [modeIndex, setModeIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState(0);
  const rafRef = useRef<number | null>(null);
  const lastRef = useRef<number>(0);

  const run = async () => {
    setLoading(true);
    try {
      const res = await analyzeAeroelastics(geometry, "CFRP_UD", tipSpeedRatio);
      setModal(res.modal);
      setModeIndex(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!playing || !modal) return;
    const freq = modal.natural_frequencies_hz[modeIndex] ?? 1;
    // Visual angular rate deliberately decoupled from the true (often very high) natural
    // frequency -- shown numerically instead -- so the shape is actually watchable.
    const visualRate = Math.min(freq, 2.0) * 2 * Math.PI;
    const tick = (t: number) => {
      const dt = lastRef.current ? (t - lastRef.current) / 1000 : 0;
      lastRef.current = t;
      setPhase((p) => p + visualRate * dt);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      lastRef.current = 0;
    };
  }, [playing, modal, modeIndex]);

  const shape = modal?.mode_shapes[modeIndex];
  const xVals = modal?.x_m ?? [];
  const maxX = xVals.length ? xVals[xVals.length - 1] : 1;

  const points = shape
    ? shape.map((v, i) => {
        const x = (xVals[i] / maxX) * (W - 40) + 20;
        const y = H / 2 - v * Math.sin(phase) * AMPLITUDE_PX;
        return `${x},${y}`;
      }).join(" ")
    : "";

  return (
    <div className="panel cfd-panel">
      <h2>Stage 11 - Modal Vibration Animation</h2>
      <p className="hint">
        Real mode shapes from Stage 6, animated at a watchable visual rate (the true natural
        frequency is shown numerically, not literally rendered — modes here run into the hundreds
        of Hz, far faster than a screen refresh can usefully show).
      </p>

      <div className="row">
        <button onClick={run} disabled={loading}>{loading ? "Solving..." : "Load Mode Shapes"}</button>
        {modal && (
          <>
            <label className="field inline">
              <span>Mode</span>
              <select value={modeIndex} onChange={(e) => setModeIndex(parseInt(e.target.value))}>
                {modal.natural_frequencies_hz.map((f, i) => (
                  <option key={i} value={i}>Mode {i + 1} ({f.toFixed(1)} Hz)</option>
                ))}
              </select>
            </label>
            <button onClick={() => setPlaying((p) => !p)}>{playing ? "Pause" : "Play"}</button>
            <button onClick={() => setPhase(0)}>Restart</button>
          </>
        )}
      </div>

      {shape && (
        <svg width={W} height={H} className="mode-shape-svg">
          <line x1={20} y1={H / 2} x2={W - 20} y2={H / 2} stroke="#2c3550" strokeDasharray="4 4" />
          <polyline points={points} fill="none" stroke="#a78bfa" strokeWidth={3} />
          <circle cx={20} cy={H / 2} r={5} fill="#7c88a8" />
          <circle cx={W - 20} cy={H / 2} r={5} fill="#7c88a8" />
        </svg>
      )}
    </div>
  );
}
