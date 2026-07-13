import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { HybridRotorIn } from "./types";
import { getCpLambdaCurve } from "./api";

interface Props {
  geometry: HybridRotorIn;
}

/** One straight Darrieus blade: a thin extruded box standing in for the airfoil cross-section. */
function DarrieusBlade({
  radius, height, chord, angleOffset,
}: { radius: number; height: number; chord: number; angleOffset: number }) {
  const x = radius * Math.cos(angleOffset);
  const z = radius * Math.sin(angleOffset);
  return (
    <mesh position={[x, 0, z]} rotation={[0, -angleOffset, 0]}>
      <boxGeometry args={[chord, height, chord * 0.18]} />
      <meshStandardMaterial color="#38bdf8" metalness={0.3} roughness={0.4} />
    </mesh>
  );
}

function SavoniusBucket({ diameter, height, angleOffset }: { diameter: number; height: number; angleOffset: number }) {
  const r = diameter / 4;
  const x = r * Math.cos(angleOffset);
  const z = r * Math.sin(angleOffset);
  return (
    <mesh position={[x, 0, z]} rotation={[0, -angleOffset, 0]}>
      <cylinderGeometry args={[diameter / 2.2, diameter / 2.2, height, 16, 1, true, 0, Math.PI]} />
      <meshStandardMaterial color="#f472b6" metalness={0.2} roughness={0.6} side={THREE.DoubleSide} />
    </mesh>
  );
}

function Shaft({ height }: { height: number }) {
  return (
    <mesh>
      <cylinderGeometry args={[0.025, 0.025, height * 1.15, 12]} />
      <meshStandardMaterial color="#9aa4bf" metalness={0.6} roughness={0.3} />
    </mesh>
  );
}

function WindParticles({ count = 60, speed = 1 }: { count?: number; speed?: number }) {
  const points = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = -4 - Math.random() * 2;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 3;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 3;
    }
    return arr;
  }, [count]);

  useFrame((_, delta) => {
    if (!points.current) return;
    const pos = points.current.geometry.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < count; i++) {
      let x = pos.getX(i) + delta * speed * 1.5;
      if (x > 4) x = -6;
      pos.setX(i, x);
    }
    pos.needsUpdate = true;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial color="#7dd3fc" size={0.04} transparent opacity={0.7} />
    </points>
  );
}

function RotatingRotor({
  geometry, rpm, playing, speedMultiplier,
}: { geometry: HybridRotorIn; rpm: number; playing: boolean; speedMultiplier: number }) {
  const group = useRef<THREE.Group>(null);
  const angleRef = useRef(0);

  useFrame((_, delta) => {
    if (!playing || !group.current) return;
    const radPerSec = (rpm / 60) * 2 * Math.PI * speedMultiplier;
    angleRef.current += radPerSec * delta;
    group.current.rotation.y = angleRef.current;
  });

  const d = geometry.darrieus;
  const s = geometry.savonius;
  const blades = Array.from({ length: d.num_blades }, (_, i) => (2 * Math.PI * i) / d.num_blades);
  const buckets = Array.from({ length: s.num_buckets }, (_, i) => (2 * Math.PI * i) / s.num_buckets);

  return (
    <group ref={group}>
      <Shaft height={d.blade_height_m} />
      {blades.map((a, i) => (
        <DarrieusBlade key={i} radius={d.rotor_radius_m} height={d.blade_height_m} chord={d.chord_m} angleOffset={a} />
      ))}
      {buckets.map((a, i) => (
        <SavoniusBucket key={i} diameter={s.bucket_diameter_m} height={s.bucket_height_m} angleOffset={a} />
      ))}
    </group>
  );
}

interface Gauges {
  rpm: number;
  torque_nm: number;
  power_w: number;
  cp: number;
}

export default function TurbineViewer3D({ geometry }: Props) {
  const [windSpeed, setWindSpeed] = useState(8);
  const [tsr, setTsr] = useState(2.25);
  const [playing, setPlaying] = useState(true);
  const [speedMultiplier, setSpeedMultiplier] = useState(1);
  const [gauges, setGauges] = useState<Gauges | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchGauges = async () => {
    setLoading(true);
    try {
      const res = await getCpLambdaCurve(geometry, windSpeed, tsr - 0.05, tsr + 0.05, 3);
      const point = res.points[Math.floor(res.points.length / 2)] ?? res.points[0];
      const omega = (tsr * windSpeed) / geometry.darrieus.rotor_radius_m;
      const rpm = (omega * 60) / (2 * Math.PI);
      setGauges({
        rpm, torque_nm: point.total_torque_nm, power_w: point.total_power_w, cp: point.system_cp,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGauges();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [windSpeed, tsr]);

  return (
    <div className="panel cfd-panel">
      <h2>Stage 9 - 3D Turbine Visualization</h2>
      <p className="hint">
        Real-time rotating turbine driven by the Stage-1 BEM solver — RPM, torque, power, and Cp
        are computed, not decorative.
      </p>

      <div className="row">
        <label className="field inline">
          <span>Wind speed (m/s)</span>
          <input type="number" step={0.5} min={geometry.cut_in_wind_speed_ms} max={geometry.cut_out_wind_speed_ms}
            value={windSpeed} onChange={(e) => setWindSpeed(parseFloat(e.target.value))} />
        </label>
        <label className="field inline">
          <span>Tip-speed ratio</span>
          <input type="number" step={0.1} min={0.5} max={5} value={tsr}
            onChange={(e) => setTsr(parseFloat(e.target.value))} />
        </label>
        <button onClick={() => setPlaying((p) => !p)}>{playing ? "Pause" : "Play"}</button>
        <button onClick={() => setPlaying(true)}>Restart</button>
        <label className="field inline">
          <span>Speed</span>
          <select value={speedMultiplier} onChange={(e) => setSpeedMultiplier(parseFloat(e.target.value))}>
            <option value={0.25}>0.25x</option>
            <option value={0.5}>0.5x</option>
            <option value={1}>1x</option>
            <option value={2}>2x</option>
            <option value={4}>4x (visual only — real RPM may be much higher)</option>
          </select>
        </label>
      </div>

      {gauges && (
        <div className="gauge-row">
          <div className="gauge"><span className="gauge-label">RPM</span><span className="gauge-value">{gauges.rpm.toFixed(0)}</span></div>
          <div className="gauge"><span className="gauge-label">Torque</span><span className="gauge-value">{gauges.torque_nm.toFixed(2)} N·m</span></div>
          <div className="gauge"><span className="gauge-label">Power</span><span className="gauge-value">{gauges.power_w.toFixed(0)} W</span></div>
          <div className="gauge"><span className="gauge-label">Cp</span><span className="gauge-value">{gauges.cp.toFixed(3)}</span></div>
        </div>
      )}
      {loading && <p className="hint">Computing operating point...</p>}

      <div className="canvas3d-wrap">
        <Canvas camera={{ position: [3, 1.5, 3], fov: 45 }}>
          <ambientLight intensity={0.6} />
          <directionalLight position={[4, 5, 2]} intensity={1.0} />
          <RotatingRotor
            geometry={geometry}
            rpm={gauges?.rpm ?? 0}
            playing={playing}
            speedMultiplier={speedMultiplier}
          />
          <WindParticles speed={playing ? Math.max(windSpeed / 8, 0.3) : 0} />
          <gridHelper args={[6, 12, "#2c3550", "#1a2033"]} />
          <OrbitControls enablePan={false} />
        </Canvas>
      </div>
      <p className="hint">
        Note: the blade rotation speed is scaled for visual clarity (real RPM at these design points
        is often several hundred RPM — the "Speed" control scales the visual, it doesn't fake the
        physics being displayed in the gauges above).
      </p>
    </div>
  );
}
