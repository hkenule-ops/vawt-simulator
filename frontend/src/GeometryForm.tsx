import type { HybridRotorIn } from "./types";

interface Props {
  geometry: HybridRotorIn;
  onChange: (g: HybridRotorIn) => void;
}

function NumField({
  label,
  value,
  onChange,
  step = 0.01,
  min,
  max,
  impact,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
  impact?: string;
}) {
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
      {impact && <span className="field-impact">{impact}</span>}
    </label>
  );
}

export default function GeometryForm({ geometry, onChange }: Props) {
  const set = (patch: Partial<HybridRotorIn>) => onChange({ ...geometry, ...patch });
  const setDarrieus = (patch: Partial<HybridRotorIn["darrieus"]>) =>
    onChange({ ...geometry, darrieus: { ...geometry.darrieus, ...patch } });
  const setSavonius = (patch: Partial<HybridRotorIn["savonius"]>) =>
    onChange({ ...geometry, savonius: { ...geometry.savonius, ...patch } });
  const setGenerator = (patch: Partial<HybridRotorIn["generator"]>) =>
    onChange({ ...geometry, generator: { ...geometry.generator, ...patch } });
  const setTower = (patch: Partial<HybridRotorIn["tower"]>) =>
    onChange({ ...geometry, tower: { ...geometry.tower, ...patch } });

  const solidity =
    (geometry.darrieus.num_blades * geometry.darrieus.chord_m) /
    geometry.darrieus.rotor_radius_m;

  return (
    <div className="panel">
      <h2>
        Rotor Geometry
        <span className="stage-badge">Design inputs</span>
      </h2>
      <p className="panel-desc">
        These parameters set swept area, solidity, and the operating envelope — the main drivers of
        annual energy production (AEP) and peak power.
      </p>

      <div className="impact-callout">
        <strong>Production levers:</strong> larger radius and height raise power roughly with area;
        chord and blade count set solidity (Cp peak and torque); cut-in / rated / cut-out define how
        much of the wind resource the turbine can use.
      </div>

      <div className="form-section">
        <label className="field">
          <span>Design name</span>
          <input
            type="text"
            value={geometry.name}
            onChange={(e) => set({ name: e.target.value })}
          />
        </label>
        <NumField
          label="Target power (W)"
          value={geometry.target_power_w}
          step={10}
          onChange={(v) => set({ target_power_w: v })}
          impact="Reference goal for sizing; compared against the predicted power curve."
        />
      </div>

      <div className="form-section">
        <h3>Darrieus (lift-type) stage</h3>
        <p className="hint">
          Primary power producer at higher tip-speed ratios. Radius and height set the swept area;
          chord and blade count set solidity σ = Nc/R.
        </p>
        <div className="grid">
          <NumField
            label="Number of blades"
            value={geometry.darrieus.num_blades}
            step={1}
            min={2}
            max={6}
            onChange={(v) => setDarrieus({ num_blades: Math.round(v) })}
            impact="More blades → higher torque, lower peak Cp; typical 2–4."
          />
          <NumField
            label="Blade height (m)"
            value={geometry.darrieus.blade_height_m}
            onChange={(v) => setDarrieus({ blade_height_m: v })}
            impact="Increases swept area and power nearly linearly with height."
          />
          <NumField
            label="Rotor radius (m)"
            value={geometry.darrieus.rotor_radius_m}
            onChange={(v) => setDarrieus({ rotor_radius_m: v })}
            impact="Strongest geometric lever: power scales with radius² (area)."
          />
          <NumField
            label="Chord (m)"
            value={geometry.darrieus.chord_m}
            onChange={(v) => setDarrieus({ chord_m: v })}
            impact="Larger chord raises solidity and starting torque; may lower peak Cp."
          />
        </div>
        <label className="field">
          <span>Airfoil</span>
          <select
            value={geometry.darrieus.airfoil}
            onChange={(e) => setDarrieus({ airfoil: e.target.value })}
          >
            <option value="NACA0012">NACA 0012 (thinner — lower drag, less structural depth)</option>
            <option value="NACA0015">NACA 0015</option>
            <option value="NACA0018">NACA 0018 (thicker — better stall, more structure)</option>
          </select>
          <span className="field-impact">
            Section shape affects Cl/Cd and stall; thickness also influences spar depth.
          </span>
        </label>
        <div className="grid">
          <NumField
            label="Twist, root→tip (deg)"
            value={geometry.darrieus.twist_angle_deg}
            step={0.5}
            min={0}
            max={30}
            onChange={(v) => setDarrieus({ twist_angle_deg: v })}
            impact="Linear geometric twist from root (0°) to tip; changes local angle of attack and revolution-averaged Cp."
          />
          <NumField
            label="Helical sweep, root→tip (deg)"
            value={geometry.darrieus.helical_twist_deg}
            step={5}
            min={0}
            max={360}
            onChange={(v) => setDarrieus({ helical_twist_deg: v })}
            impact="Azimuthal sweep of the blade shape from bottom to top (0° = straight/H-type). Smooths torque ripple; mean power stays about the same."
          />
        </div>
        {(geometry.darrieus.twist_angle_deg !== 0 || geometry.darrieus.helical_twist_deg !== 0) && (
          <p className="hint">
            Spanwise-varying blade — aero, CFD case export, and structural loads now discretise the
            blade along its span instead of treating it as one uniform straight section.
          </p>
        )}
        <div className="solidity-chip">
          Solidity σ = Nc/R =
          <span className="val">{solidity.toFixed(3)}</span>
          <span>(practical range ~0.1–1.0)</span>
        </div>
      </div>

      <div className="form-section">
        <h3>Savonius (drag-type) stage</h3>
        <p className="hint">
          Improves self-starting and low-wind torque. Adds some power at low TSR; less efficient at
          high speed than the Darrieus stage.
        </p>
        <div className="grid">
          <NumField
            label="Number of buckets"
            value={geometry.savonius.num_buckets}
            step={1}
            min={2}
            max={3}
            onChange={(v) => setSavonius({ num_buckets: Math.round(v) })}
            impact="2 buckets common; 3 can smooth torque ripple."
          />
          <NumField
            label="Bucket height (m)"
            value={geometry.savonius.bucket_height_m}
            onChange={(v) => setSavonius({ bucket_height_m: v })}
            impact="Larger frontal area → more drag torque at low wind."
          />
          <NumField
            label="Bucket diameter (m)"
            value={geometry.savonius.bucket_diameter_m}
            onChange={(v) => setSavonius({ bucket_diameter_m: v })}
            impact="Sets Savonius rotor size relative to the Darrieus radius."
          />
          <NumField
            label="Overlap ratio"
            value={geometry.savonius.overlap_ratio}
            step={0.01}
            min={0}
            max={0.5}
            onChange={(v) => setSavonius({ overlap_ratio: v })}
            impact="Typical 0.1–0.2; affects gap flow and starting behaviour."
          />
        </div>
      </div>

      <div className="form-section">
        <h3>Operating envelope</h3>
        <p className="hint">
          Defines which wind speeds contribute to AEP. Wider envelope captures more resource; rated
          wind sets the design point for structural and power electronics sizing.
        </p>
        <div className="grid">
          <NumField
            label="Cut-in (m/s)"
            value={geometry.cut_in_wind_speed_ms}
            onChange={(v) => set({ cut_in_wind_speed_ms: v })}
            impact="Below this, no generation. Lower cut-in improves low-wind AEP."
          />
          <NumField
            label="Rated (m/s)"
            value={geometry.rated_wind_speed_ms}
            onChange={(v) => set({ rated_wind_speed_ms: v })}
            impact="Design wind for peak continuous power and load cases."
          />
          <NumField
            label="Cut-out (m/s)"
            value={geometry.cut_out_wind_speed_ms}
            onChange={(v) => set({ cut_out_wind_speed_ms: v })}
            impact="Shutdown above this for safety; limits storm contribution to AEP."
          />
        </div>
      </div>

      <div className="form-section">
        <h3>Generator / alternator</h3>
        <p className="hint">
          Direct-drive PM synchronous generator (no gearbox — shaft speed = generator speed).
          See the Generator/Tower panel below for the resulting torque-speed curve and operating point.
        </p>
        <div className="grid">
          <NumField
            label="Pole pairs"
            value={geometry.generator.pole_pairs}
            step={1}
            min={1}
            max={60}
            onChange={(v) => setGenerator({ pole_pairs: Math.round(v) })}
            impact="Sets electrical frequency and cogging ripple count; more poles → lower rpm for a given electrical frequency."
          />
          <NumField
            label="Slot count"
            value={geometry.generator.slot_count}
            step={1}
            min={3}
            max={180}
            onChange={(v) => setGenerator({ slot_count: Math.round(v) })}
            impact="With pole pairs, sets cogging torque ripple frequency (LCM of slots and 2×poles)."
          />
          <NumField
            label="Torque constant Kt (Nm/A)"
            value={geometry.generator.torque_constant_nm_per_a}
            step={0.01}
            onChange={(v) => setGenerator({ torque_constant_nm_per_a: v })}
            impact="Higher Kt → less current (and less copper loss) for the same torque, but lower back-EMF headroom."
          />
          <NumField
            label="Phase resistance (Ω)"
            value={geometry.generator.phase_resistance_ohm}
            step={0.01}
            min={0.001}
            onChange={(v) => setGenerator({ phase_resistance_ohm: v })}
            impact="Dominant loss term — copper loss scales with I²R; keep this small relative to load resistance."
          />
          <NumField
            label="Synchronous reactance (Ω)"
            value={geometry.generator.synchronous_reactance_ohm}
            step={0.01}
            min={0}
            onChange={(v) => setGenerator({ synchronous_reactance_ohm: v })}
            impact="Winding inductance's AC impedance; reduces terminal voltage under load but doesn't dissipate power."
          />
          <NumField
            label="Load resistance (Ω)"
            value={geometry.generator.load_resistance_ohm}
            step={0.1}
            min={0.01}
            onChange={(v) => setGenerator({ load_resistance_ohm: v })}
            impact="Effective resistive load reflected through the rectifier — used for the torque-speed curve."
          />
          <NumField
            label="Core loss coefficient"
            value={geometry.generator.core_loss_coefficient}
            step={0.001}
            min={0}
            onChange={(v) => setGenerator({ core_loss_coefficient: v })}
            impact="Hysteresis + eddy-current loss, W per (rad/s)^1.5 — grows with shaft speed."
          />
          <NumField
            label="Peak cogging torque (Nm)"
            value={geometry.generator.cogging_torque_peak_nm}
            step={0.01}
            min={0}
            onChange={(v) => setGenerator({ cogging_torque_peak_nm: v })}
            impact="If this exceeds the rotor's starting torque, the rotor can't self-start from rest."
          />
        </div>
      </div>

      <div className="form-section">
        <h3>Tower</h3>
        <p className="hint">
          Sets rotor hub height and, optionally, corrects wind speeds for shear between the
          reference measurement height and the rotor.
        </p>
        <div className="grid">
          <NumField
            label="Tower height (m)"
            value={geometry.tower.height_m}
            step={0.1}
            min={0.1}
            onChange={(v) => setTower({ height_m: v })}
            impact="Raises hub height = tower height + half blade height; affects wind-shear-corrected inflow if enabled below."
          />
          <NumField
            label="Reference height (m)"
            value={geometry.tower.reference_height_m}
            step={0.5}
            min={0.5}
            onChange={(v) => setTower({ reference_height_m: v })}
            impact="Height at which the wind speeds you enter elsewhere are assumed to be measured (typically 10 m)."
          />
          <NumField
            label="Wind shear exponent α"
            value={geometry.tower.wind_shear_exponent}
            step={0.01}
            min={0}
            max={0.6}
            onChange={(v) => setTower({ wind_shear_exponent: v })}
            impact="Power-law exponent V(h)=V_ref·(h/h_ref)^α; IEC 61400-2 default 0.20 for small wind turbines."
          />
        </div>
        <label className="field">
          <span>
            <input
              type="checkbox"
              checked={geometry.tower.apply_wind_shear}
              onChange={(e) => setTower({ apply_wind_shear: e.target.checked })}
              style={{ width: "auto", marginRight: 6 }}
            />
            Apply wind shear correction to hub height
          </span>
          <span className="field-impact">
            Off by default (matches previous behaviour exactly). When on, wind speeds fed into
            the BEM solver are corrected from the reference height above to the rotor's hub height.
          </span>
        </label>
      </div>
    </div>
  );
}