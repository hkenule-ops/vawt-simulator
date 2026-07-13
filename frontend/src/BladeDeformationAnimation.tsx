import { useState, useEffect, useRef } from "react";
import type { HybridRotorIn, BeamResultOut } from "./types";
import { analyzeBladeStructure } from "./api";

interface Props {
  geometry: HybridRotorIn;
  windSpeed: number;
  tipSpeedRatio: number;
}

const W = 560;
const H = 220;
const SCALE = 8; // visual exaggeration factor so mm-scale real deflections are visible

export default function BladeDeformationAnimation({ geometry, windSpeed, tipSpeedRatio }: Props) {
  const [flapwise, setFlapwise] = useState<BeamResultOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(true);
  const [t, setT] = useState(0); // 0 = undeformed, 1 = fully loaded
  const rafRef = useRef<number | null>(null);
  const lastRef = useRef<number>(0);
  const directionRef = useRef(1);

  const run = async () => {
    setLoading(true);
    try {
      const res = await analyzeBladeStructure(geometry, "CFRP_UD", windSpeed, tipSpeedRatio);
      setFlapwise(res.flapwise);
      setT(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!playing || !flapwise) return;
    const tick = (now: number) => {
      const dt = lastRef.current ? (now - lastRef.current) / 1000 : 0;
      lastRef.current = now;
      setT((prev) => {
        let next = prev + directionRef.current * dt * 0.6;
        if (next >= 1) { next = 1; directionRef.current = -1; }
        if (next <= 0) { next = 0; directionRef.current = 1; }
        return next;
      });
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      lastRef.current = 0;
    };
  }, [playing, flapwise]);

  const maxX = flapwise ? flapwise.x_m[flapwise.x_m.length - 1] : 1;
  const maxDefl = flapwise ? Math.max(...flapwise.deflection_m.map(Math.abs), 1e-9) : 1;

  function amplitudeScale(maxD: number) {
    // Normalize so the max deflection always renders at a fixed, visible pixel amplitude,
    // regardless of the actual (often sub-cm) real deflection magnitude.
    const targetPx = 60;
    return maxD > 0 ? targetPx / (maxD * SCALE) : 1;
  }

  const undeformedPoints = flapwise
    ? flapwise.x_m.map((x) => `${(x / maxX) * (W - 40) + 20},${H / 2}`).join(" ")
    : "";
  const deformedPoints = flapwise
    ? flapwise.x_m.map((x, i) => {
        const px = (x / maxX) * (W - 40) + 20;
        const py = H / 2 + flapwise.deflection_m[i] * t * SCALE * amplitudeScale(maxDefl);
        return `${px},${py}`;
      }).join(" ")
    : "";

  return (
    <div className="panel cfd-panel">
      <h2>Stage 11 - Blade Deformation Under Load</h2>
      <p className="hint">
        Real Stage-3 beam FEM deflection shape, animated as a loading/unloading cycle
        (visually exaggerated — max deflection is normalized to a visible pixel amplitude
        and shown numerically alongside).
      </p>

      <div className="row">
        <button onClick={run} disabled={loading}>{loading ? "Solving..." : "Load Deflection Shape"}</button>
        {flapwise && (
          <>
            <button onClick={() => setPlaying((p) => !p)}>{playing ? "Pause" : "Play"}</button>
            <button onClick={() => { setT(0); directionRef.current = 1; }}>Restart</button>
          </>
        )}
      </div>

      {flapwise && (
        <>
          <p className="stat">Max flapwise deflection: <strong>{(maxDefl * 1000).toFixed(2)} mm</strong></p>
          <svg width={W} height={H} className="mode-shape-svg">
            <polyline points={undeformedPoints} fill="none" stroke="#2c3550" strokeDasharray="4 4" strokeWidth={2} />
            <polyline points={deformedPoints} fill="none" stroke="#fb923c" strokeWidth={3} />
          </svg>
        </>
      )}
    </div>
  );
}
