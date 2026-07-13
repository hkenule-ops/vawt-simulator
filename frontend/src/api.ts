import axios from "axios";
import type {
  HybridRotorIn, CpLambdaResponse, PowerCurveResponse, PanelMethodResponse, ValidationResponse,
  StructuralAnalysisResponse, MaterialOut, CompositeCompareResponse, FatigueAnalysisResponse,
  AeroelasticAnalysisResponse, EconomicAnalysisResponse, OptimizationResponse, ValidationReportOut,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

const client = axios.create({ baseURL: API_BASE, timeout: 30000 });

export async function checkHealth(): Promise<boolean> {
  try {
    const r = await client.get("/health");
    return r.data?.status === "ok";
  } catch {
    return false;
  }
}

export async function validateGeometry(geometry: HybridRotorIn): Promise<string[]> {
  const r = await client.post<string[]>("/geometry/validate", geometry);
  return r.data;
}

export async function getCpLambdaCurve(
  geometry: HybridRotorIn,
  wind_speed_ms: number,
  tsr_min: number,
  tsr_max: number,
  n_points: number
): Promise<CpLambdaResponse> {
  const r = await client.post<CpLambdaResponse>("/bem/cp-lambda", {
    geometry,
    wind_speed_ms,
    tsr_min,
    tsr_max,
    n_points,
  });
  return r.data;
}

export async function getPowerCurve(
  geometry: HybridRotorIn,
  wind_speeds_ms: number[]
): Promise<PowerCurveResponse> {
  const r = await client.post<PowerCurveResponse>("/bem/power-curve", {
    geometry,
    wind_speeds_ms,
  });
  return r.data;
}

export async function getPanelMethodDistribution(
  airfoil_thickness_ratio: number,
  alpha_deg: number,
  n_panels = 80
): Promise<PanelMethodResponse> {
  const r = await client.post<PanelMethodResponse>("/cfd/panel-method", {
    airfoil_thickness_ratio,
    alpha_deg,
    n_panels,
  });
  return r.data;
}

export async function downloadOpenFOAMCase(
  geometry: HybridRotorIn,
  wind_speed_ms: number,
  tip_speed_ratio: number
): Promise<void> {
  const r = await client.post(
    "/cfd/openfoam-case",
    { geometry, wind_speed_ms, tip_speed_ratio },
    { responseType: "blob" }
  );
  const url = window.URL.createObjectURL(new Blob([r.data]));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${geometry.name.replace(/\s+/g, "_")}_cfd_case.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function listMaterials(): Promise<MaterialOut[]> {
  const r = await client.get<MaterialOut[]>("/structural/materials");
  return r.data;
}

export async function analyzeBladeStructure(
  geometry: HybridRotorIn,
  material: string,
  wind_speed_ms: number,
  tip_speed_ratio: number,
  spar_width_fraction = 0.5,
  spar_wall_thickness_m = 0.003,
  boundary: "pinned-pinned" | "cantilever" = "pinned-pinned"
): Promise<StructuralAnalysisResponse> {
  const r = await client.post<StructuralAnalysisResponse>("/structural/analyze-blade", {
    geometry, material, wind_speed_ms, tip_speed_ratio,
    spar_width_fraction, spar_wall_thickness_m, boundary,
  });
  return r.data;
}

export async function compareCompositeMaterials(
  geometry: HybridRotorIn,
  wind_speed_ms: number,
  tip_speed_ratio: number,
  target_safety_factor = 1.5,
  boundary: "pinned-pinned" | "cantilever" = "pinned-pinned"
): Promise<CompositeCompareResponse> {
  const r = await client.post<CompositeCompareResponse>("/composites/compare-materials", {
    geometry, wind_speed_ms, tip_speed_ratio, target_safety_factor, boundary,
  });
  return r.data;
}

export async function analyzeFatigue(
  geometry: HybridRotorIn,
  material: string,
  plyMaterial: string,
  operatingTsr: number,
  weibullK = 2.0,
  weibullC = 7.0,
  boundary: "pinned-pinned" | "cantilever" = "pinned-pinned"
): Promise<FatigueAnalysisResponse> {
  const r = await client.post<FatigueAnalysisResponse>("/fatigue/analyze-blade", {
    geometry, material, ply_material: plyMaterial, operating_tsr: operatingTsr,
    weibull_k: weibullK, weibull_c: weibullC, boundary,
  });
  return r.data;
}

export async function analyzeAeroelastics(
  geometry: HybridRotorIn,
  material: string,
  operatingTsr: number,
  sparWidthFraction = 0.5,
  sparWallThicknessM = 0.003,
  boundary: "pinned-pinned" | "cantilever" = "pinned-pinned",
  nModes = 4
): Promise<AeroelasticAnalysisResponse> {
  const r = await client.post<AeroelasticAnalysisResponse>("/aeroelastic/analyze-blade", {
    geometry, material, operating_tsr: operatingTsr,
    spar_width_fraction: sparWidthFraction, spar_wall_thickness_m: sparWallThicknessM,
    boundary, n_modes: nModes,
  });
  return r.data;
}

export async function analyzeEconomics(
  geometry: HybridRotorIn,
  material: string,
  plyMaterial: string,
  electricityPrice = 0.15,
  discountRate = 0.06,
  lifetimeYears = 20,
  weibullK = 2.0,
  weibullC = 7.0
): Promise<EconomicAnalysisResponse> {
  const r = await client.post<EconomicAnalysisResponse>("/economics/analyze", {
    geometry, material, ply_material: plyMaterial,
    electricity_price_usd_per_kwh: electricityPrice, discount_rate: discountRate,
    project_lifetime_years: lifetimeYears, weibull_k: weibullK, weibull_c: weibullC,
  });
  return r.data;
}

export async function optimizeParetoFront(
  geometry: HybridRotorIn,
  material: string,
  plyMaterial: string,
  populationSize = 24,
  nGenerations = 10,
  targetSafetyFactor = 1.5,
  operatingTsr = 2.25,
  seed = 1,
  captureHistory = false
): Promise<OptimizationResponse> {
  const r = await client.post<OptimizationResponse>("/optimization/pareto-front", {
    geometry, material, ply_material: plyMaterial,
    population_size: populationSize, n_generations: nGenerations,
    target_safety_factor: targetSafetyFactor, operating_tsr: operatingTsr, seed,
    capture_history: captureHistory,
  });
  return r.data;
}

async function downloadReport(
  endpoint: string, geometry: HybridRotorIn, material: string, plyMaterial: string, filenameSuffix: string
): Promise<void> {
  const r = await client.post(
    `/reporting/${endpoint}`,
    { geometry, material, ply_material: plyMaterial },
    { responseType: "blob" }
  );
  const url = window.URL.createObjectURL(new Blob([r.data]));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${geometry.name.replace(/\s+/g, "_")}_report.${filenameSuffix}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export const downloadDocxReport = (g: HybridRotorIn, m: string, p: string) => downloadReport("docx", g, m, p, "docx");
export const downloadXlsxReport = (g: HybridRotorIn, m: string, p: string) => downloadReport("xlsx", g, m, p, "xlsx");
export const downloadPdfReport = (g: HybridRotorIn, m: string, p: string) => downloadReport("pdf", g, m, p, "pdf");
export const downloadCsvReport = (g: HybridRotorIn, m: string, p: string) => downloadReport("csv", g, m, p, "csv");

export async function runSystemValidation(
  geometry: HybridRotorIn, material: string, plyMaterial: string, operatingTsr = 2.25
): Promise<ValidationReportOut> {
  const r = await client.post<ValidationReportOut>("/validation/run-checks", {
    geometry, material, ply_material: plyMaterial, operating_tsr: operatingTsr,
  });
  return r.data;
}

export async function validateAgainstBem(
  geometry: HybridRotorIn,
  wind_speed_ms: number,
  tip_speed_ratio: number,
  cfd_cd_mean: number,
  cfd_cl_mean: number
): Promise<ValidationResponse> {
  const r = await client.post<ValidationResponse>("/cfd/validate-against-bem", {
    geometry, wind_speed_ms, tip_speed_ratio, cfd_cd_mean, cfd_cl_mean,
  });
  return r.data;
}
