import type { HybridRotorIn } from "./types";

interface Props {
  geometry: HybridRotorIn;
  onChange: (g: HybridRotorIn) => void;
}

function NumField({
  label, value, onChange, step = 0.01, min, max,
}: { label: string; value: number; onChange: (v: number) => void; step?: number; min?: number; max?: number }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        value={value}
        step={step}
        min={min}
        max={max}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </label>
  );
}

export default function GeometryForm({ geometry, onChange }: Props) {
  const set = (patch: Partial<HybridRotorIn>) => onChange({ ...geometry, ...patch });
  const setDarrieus = (patch: Partial<HybridRotorIn["darrieus"]>) =>
    onChange({ ...geometry, darrieus: { ...geometry.darrieus, ...patch } });
  const setSavonius = (patch: Partial<HybridRotorIn["savonius"]>) =>
    onChange({ ...geometry, savonius: { ...geometry.savonius, ...patch } });

  return (
    <div className="panel">
      <h2>Rotor Geometry</h2>

      <label className="field">
        <span>Design name</span>
        <input type="text" value={geometry.name} onChange={(e) => set({ name: e.target.value })} />
      </label>
      <NumField label="Target power (W)" value={geometry.target_power_w} step={10}
        onChange={(v) => set({ target_power_w: v })} />

      <h3>Darrieus (lift-type) stage</h3>
      <div className="grid">
        <NumField label="Number of blades" value={geometry.darrieus.num_blades} step={1} min={2} max={6}
          onChange={(v) => setDarrieus({ num_blades: Math.round(v) })} />
        <NumField label="Blade height (m)" value={geometry.darrieus.blade_height_m}
          onChange={(v) => setDarrieus({ blade_height_m: v })} />
        <NumField label="Rotor radius (m)" value={geometry.darrieus.rotor_radius_m}
          onChange={(v) => setDarrieus({ rotor_radius_m: v })} />
        <NumField label="Chord (m)" value={geometry.darrieus.chord_m}
          onChange={(v) => setDarrieus({ chord_m: v })} />
      </div>
      <label className="field">
        <span>Airfoil</span>
        <select value={geometry.darrieus.airfoil} onChange={(e) => setDarrieus({ airfoil: e.target.value })}>
          <option value="NACA0012">NACA 0012</option>
          <option value="NACA0015">NACA 0015</option>
          <option value="NACA0018">NACA 0018</option>
        </select>
      </label>
      <p className="hint">
        Solidity σ = Nc/R = {((geometry.darrieus.num_blades * geometry.darrieus.chord_m) / geometry.darrieus.rotor_radius_m).toFixed(3)}
        {" "}(practical range ~0.1-1.0)
      </p>

      <h3>Savonius (drag-type) stage</h3>
      <div className="grid">
        <NumField label="Number of buckets" value={geometry.savonius.num_buckets} step={1} min={2} max={3}
          onChange={(v) => setSavonius({ num_buckets: Math.round(v) })} />
        <NumField label="Bucket height (m)" value={geometry.savonius.bucket_height_m}
          onChange={(v) => setSavonius({ bucket_height_m: v })} />
        <NumField label="Bucket diameter (m)" value={geometry.savonius.bucket_diameter_m}
          onChange={(v) => setSavonius({ bucket_diameter_m: v })} />
        <NumField label="Overlap ratio" value={geometry.savonius.overlap_ratio} step={0.01} min={0} max={0.5}
          onChange={(v) => setSavonius({ overlap_ratio: v })} />
      </div>

      <h3>Operating envelope</h3>
      <div className="grid">
        <NumField label="Cut-in (m/s)" value={geometry.cut_in_wind_speed_ms}
          onChange={(v) => set({ cut_in_wind_speed_ms: v })} />
        <NumField label="Rated (m/s)" value={geometry.rated_wind_speed_ms}
          onChange={(v) => set({ rated_wind_speed_ms: v })} />
        <NumField label="Cut-out (m/s)" value={geometry.cut_out_wind_speed_ms}
          onChange={(v) => set({ cut_out_wind_speed_ms: v })} />
      </div>
    </div>
  );
}
