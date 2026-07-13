import { useState } from "react";
import type { HybridRotorIn, ValidationReportOut } from "./types";
import {
  downloadDocxReport, downloadXlsxReport, downloadPdfReport, downloadCsvReport, runSystemValidation,
} from "./api";

interface Props {
  geometry: HybridRotorIn;
}

export default function ReportingValidationPanel({ geometry }: Props) {
  const [material, setMaterial] = useState("CFRP_UD");
  const [downloading, setDownloading] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationReportOut | null>(null);
  const [validating, setValidating] = useState(false);

  const plyKeyFor = (mat: string) => (mat === "GFRP_UD" ? "GFRP_UD_PLY" : "CFRP_UD_PLY");

  const download = async (fmt: string, fn: (g: HybridRotorIn, m: string, p: string) => Promise<void>) => {
    setDownloading(fmt);
    try {
      await fn(geometry, material, plyKeyFor(material));
    } finally {
      setDownloading(null);
    }
  };

  const runValidation = async () => {
    setValidating(true);
    try {
      const res = await runSystemValidation(geometry, material, plyKeyFor(material));
      setValidation(res);
    } finally {
      setValidating(false);
    }
  };

  return (
    <div className="panel cfd-panel">
      <h2>Stage 12 - Reporting &amp; Validation</h2>
      <p className="hint">
        Generate a full design report (DOCX/PDF/XLSX/CSV) assembled from a single live analysis
        run across Stages 1-7, plus a system validation checklist that re-derives key physical
        and financial invariants for this specific design.
      </p>

      <div className="row">
        <label className="field inline">
          <span>Material</span>
          <select value={material} onChange={(e) => setMaterial(e.target.value)}>
            <option value="CFRP_UD">Carbon Fibre (CFRP)</option>
            <option value="GFRP_UD">Glass Fibre (GFRP)</option>
          </select>
        </label>
      </div>

      <h3>Download report</h3>
      <div className="row">
        <button onClick={() => download("docx", downloadDocxReport)} disabled={downloading !== null}>
          {downloading === "docx" ? "Generating..." : "Word (.docx)"}
        </button>
        <button onClick={() => download("pdf", downloadPdfReport)} disabled={downloading !== null}>
          {downloading === "pdf" ? "Generating..." : "PDF"}
        </button>
        <button onClick={() => download("xlsx", downloadXlsxReport)} disabled={downloading !== null}>
          {downloading === "xlsx" ? "Generating..." : "Excel (.xlsx)"}
        </button>
        <button onClick={() => download("csv", downloadCsvReport)} disabled={downloading !== null}>
          {downloading === "csv" ? "Generating..." : "CSV"}
        </button>
      </div>

      <h3>System validation</h3>
      <div className="row">
        <button onClick={runValidation} disabled={validating}>
          {validating ? "Running checks..." : "Run Validation Checks"}
        </button>
      </div>

      {validation && (
        <>
          <div className={`validation-result ${validation.all_passed ? "ok" : "warn"}`}>
            <p><strong>{validation.n_passed} / {validation.n_total}</strong> checks passed
              {validation.all_passed ? " — all systems consistent for this design." : " — see details below."}</p>
          </div>
          <ul className="check-list">
            {validation.checks.map((c, i) => (
              <li key={i} className={c.passed ? "check-pass" : "check-fail"}>
                <span className="check-icon">{c.passed ? "✓" : "✗"}</span>
                <div>
                  <strong>{c.name}</strong>
                  <p className="hint" style={{ margin: "2px 0 0" }}>{c.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
