export interface DarrieusBladeIn {
  num_blades: number;
  blade_height_m: number;
  rotor_radius_m: number;
  chord_m: number;
  airfoil: string;
  twist_angle_deg: number;
  helical_twist_deg: number;
  blade_thickness_ratio: number;
}

export interface SavoniusBucketIn {
  num_buckets: number;
  bucket_height_m: number;
  bucket_diameter_m: number;
  overlap_ratio: number;
  end_plate_diameter_m: number;
}

export interface ShaftIn {
  length_m: number;
  outer_diameter_mm: number;
  wall_thickness_mm: number;
  material: string;
}

export interface HybridRotorIn {
  name: string;
  target_power_w: number;
  darrieus: DarrieusBladeIn;
  savonius: SavoniusBucketIn;
  shaft: ShaftIn;
  rated_wind_speed_ms: number;
  cut_in_wind_speed_ms: number;
  cut_out_wind_speed_ms: number;
}

export interface HybridOperatingPointOut {
  wind_speed_ms: number;
  tip_speed_ratio: number;
  darrieus_power_w: number;
  savonius_power_w: number;
  total_power_w: number;
  total_torque_nm: number;
  system_cp: number;
  darrieus_cp: number;
  savonius_cp: number;
  darrieus_max_aoa_deg: number;
  induction_factor: number;
  converged: boolean;
}

export interface CpLambdaResponse {
  points: HybridOperatingPointOut[];
  warnings: string[];
}

export interface PowerCurvePoint {
  wind_speed_ms: number;
  operating_point: HybridOperatingPointOut | null;
}

export interface PowerCurveResponse {
  curve: PowerCurvePoint[];
  warnings: string[];
  rated_power_w: number | null;
  rated_wind_speed_ms: number | null;
}

export interface PanelMethodResponse {
  x_over_c: number[];
  cp: number[];
  is_upper: boolean[];
  cl: number;
  cl_thin_airfoil_theory: number;
  alpha_deg: number;
  converged: boolean;
}

export interface ValidationResponse {
  bem_ct: number;
  cfd_ct_equivalent: number;
  percent_error: number;
  bem_power_w: number;
  within_engineering_tolerance: boolean;
  notes: string;
}

export interface BeamResultOut {
  x_m: number[];
  deflection_m: number[];
  bending_moment_nm: number[];
  max_deflection_m: number;
  max_deflection_location_m: number;
  max_bending_moment_nm: number;
  max_bending_stress_pa: number;
  max_stress_location_m: number;
}

export interface StructuralAnalysisResponse {
  material: string;
  spar_area_m2: number;
  spar_mass_kg: number;
  flapwise_distributed_load_n_m: number;
  edgewise_distributed_load_n_m: number;
  centrifugal_distributed_load_n_m: number;
  flapwise: BeamResultOut;
  edgewise: BeamResultOut;
  max_flapwise_stress_pa: number;
  max_edgewise_stress_pa: number;
  combined_max_stress_pa: number;
  yield_strength_pa: number;
  safety_factor: number;
  euler_buckling_load_n: number;
  nominal_axial_load_n: number;
  buckling_safety_factor: number;
  warnings: string[];
}

export interface MaterialOut {
  key: string;
  name: string;
  density_kg_m3: number;
  youngs_modulus_pa: number;
  shear_modulus_pa: number;
  yield_strength_pa: number;
  ultimate_strength_pa: number;
}

export interface OptimizedSparOut {
  material_key: string;
  n_cap_plies: number;
  n_web_pairs: number;
  spar_width_fraction: number;
  feasible: boolean;
  spar_mass_kg: number;
  cap_thickness_m: number;
  web_thickness_m: number;
  combined_max_stress_pa: number;
  safety_factor: number;
  buckling_safety_factor: number;
  warnings: string[];
}

export interface CompositeCompareResponse {
  cfrp: OptimizedSparOut;
  gfrp: OptimizedSparOut;
}

export interface FatigueAnalysisResponse {
  annual_damage: number;
  estimated_life_years: number;
  dominant_stress_range_pa: number;
  total_cycles_per_year: number;
  wind_bins_ms: number[];
  damage_by_bin: number[];
  warnings: string[];
}

export interface ModalResultOut {
  natural_frequencies_hz: number[];
  mode_shapes: number[][];
  x_m: number[];
}

export interface ResonanceRiskOut {
  mode_number: number;
  natural_frequency_hz: number;
  harmonic_number: number;
  excitation_rpm: number;
  margin_percent: number;
}

export interface CampbellResultOut {
  rpm_range: number[];
  natural_frequencies_hz: number[];
  excitation_lines_hz: Record<string, number[]>;
  resonance_risks: ResonanceRiskOut[];
}

export interface HarmonicContentOut {
  harmonic_number: number[];
  amplitude_n_m: number[];
  dominant_harmonics: number[];
}

export interface AeroelasticAnalysisResponse {
  modal: ModalResultOut;
  campbell: CampbellResultOut;
  harmonics: HarmonicContentOut;
  operating_rpm_min: number;
  operating_rpm_max: number;
  warnings: string[];
}

export interface AEPResultOut {
  aep_kwh: number;
  capacity_factor: number;
  wind_bins_ms: number[];
  energy_by_bin_kwh: number[];
  rated_power_w: number;
}

export interface CapexBreakdownOut {
  blade_material_cost_usd: number;
  blade_fabrication_cost_usd: number;
  generator_electronics_cost_usd: number;
  tower_foundation_cost_usd: number;
  installation_cost_usd: number;
  total_capex_usd: number;
}

export interface EconomicAnalysisResponse {
  aep: AEPResultOut;
  capex: CapexBreakdownOut;
  annual_opex_usd: number;
  lcoe_usd_per_kwh: number;
  npv_usd: number;
  irr: number | null;
  simple_payback_years: number;
  annual_revenue_usd: number;
  warnings: string[];
}

export interface ParetoDesignOut {
  rotor_radius_m: number;
  blade_height_m: number;
  chord_m: number;
  spar_width_fraction: number;
  spar_wall_thickness_m: number;
  aep_kwh: number;
  lcoe_usd_per_kwh: number;
  blade_mass_kg: number;
}

export interface GenerationSnapshotOut {
  generation: number;
  n_eval: number;
  pareto_front: ParetoDesignOut[];
}

export interface OptimizationResponse {
  pareto_front: ParetoDesignOut[];
  n_generations: number;
  population_size: number;
  n_evaluated: number;
  generation_history: GenerationSnapshotOut[];
}

export interface CheckResultOut {
  name: string;
  passed: boolean;
  detail: string;
}

export interface ValidationReportOut {
  checks: CheckResultOut[];
  all_passed: boolean;
  n_passed: number;
  n_total: number;
}

export const DEFAULT_GEOMETRY: HybridRotorIn = {
  name: "300W Hybrid VAWT",
  target_power_w: 300,
  darrieus: {
    num_blades: 3,
    blade_height_m: 1.2,
    rotor_radius_m: 0.6,
    chord_m: 0.09,
    airfoil: "NACA0018",
    twist_angle_deg: 0,
    helical_twist_deg: 0,
    blade_thickness_ratio: 0.18,
  },
  savonius: {
    num_buckets: 2,
    bucket_height_m: 0.9,
    bucket_diameter_m: 0.5,
    overlap_ratio: 0.15,
    end_plate_diameter_m: 0.55,
  },
  shaft: {
    length_m: 1.6,
    outer_diameter_mm: 40,
    wall_thickness_mm: 4,
    material: "AISI_304_Stainless",
  },
  rated_wind_speed_ms: 10,
  cut_in_wind_speed_ms: 3,
  cut_out_wind_speed_ms: 20,
};
