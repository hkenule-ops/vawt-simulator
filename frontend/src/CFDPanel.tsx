import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import type { HybridRotorIn, ValidationResponse } from "./types";
import { getPanelMethodDistribution, downloadOpenFOAMCase, validateAgainstBem } from "./api";

interface Props {
  geometry: HybridRotorIn;
  windSpeed: number;
  tipSpeedRatio: number;
}

export default function CFDPanel({ geometry, windSpeed, tipSpeedRatio }: Props) {
  const [alpha, setAlpha] = useState(5);
  const [cpData, setCpData] = useState<any[]>([]);
  const [cl, setCl] = useState<number | null>(null);
  const [clThin, setClThin] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const [cfdCd, setCfdCd] = useState(0.5);
  const [cfdCl, setCfdCl] = useState(0.1);
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [validating, setValidating] = useState(false);

  const runPanelMethod = async () => {
    setLoading(true);
    try {
      const res = await getPanelMethodDistribution(geometry.darrieus.blade_thickness_ratio, alpha, 80);
      const upper = res.x_over_c
        .map((x, i) => ({ x, cp: res.cp[i], isUpper: res.is_upper[i] }))
        .filter((p) => p.isUpper)
        .sort((a, b) => a.x - b.x);
      const lower = res.x_over_c
        .map((x, i) => ({ x, cp: res.cp[i], isUpper: res.is_upper[i] }))
        .filter((p) => !p.isUpper)
        .sort((a, b) => a.x - b.x);
      const merged: any[] = [];
      const n = Math.max(upper.length, lower.length);
      for (let i = 0; i < n; i++) {
        merged.push({
          x: upper[i]?.x ?? lower[i]?.x,
          cp_upper: upper[i]?.cp,
          cp_lower: lower[i]?.cp,
        });
      }
      setCpData(merged);
      setCl(res.cl);
      setClThin(res.cl_thin_airfoil_theory);
    } finally {
      setLoading(false);
    }
  };

  const runDownload = async () => {
    setDownloading(true);
    try {
      await downloadOpenFOAMCase(geometry, windSpeed, tipSpeedRatio);
    } finally {
      setDownloading(false);
    }
  };

  const runValidation = async () => {
    setValidating(true);
    try {
      const res = await validateAgainstBem(geometry, windSpeed, tipSpeedRatio, cfdCd, cfdCl);
      setValidation(res);
    } finally {
      setValidating(false);
    }
  };

  return (
    <div className="panel cfd-panel">
      <h2>Stage 2 - CFD Validation</h2>

      <h3>2a. Surface pressure distribution (panel method)</h3>
      <p className="hint">
        Fast in-process potential-flow check on the blade section before committing to a full OpenFOAM run.
      </p>
      <div className="row">
        <label className="field inline">
          <span>Angle of attack (deg)</span>
          <input type="number" value={alpha} step={0.5} onChange={(e) => setAlpha(parseFloat(e.target.value))} />
        </label>
        <button onClick={runPanelMethod} disabled={loading}>{loading ? "Solving..." : "Run Panel Method"}</button>
      </div>
      {cl !== null && (
        <p className="stat">
          Cl = <strong>{cl.toFixed(3)}</strong> (thin-airfoil theory: {clThin?.toFixed(3)},
          thickness correction ratio: {clThin ? (cl / clThin).toFixed(3) : "-"})
        </p>
      )}
      {cpData.length > 0 && (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={cpData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" label={{ value: "x/c", position: "insideBottom", offset: -5 }} />
            <YAxis reversed label={{ value: "Cp", angle: -90, position: "insideLeft" }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="cp_upper" name="Upper surface" stroke="#f59e0b" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="cp_lower" name="Lower surface" stroke="#38bdf8" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      )}

      <h3>2b. OpenFOAM case (full CFD, runs on your machine)</h3>
      <p className="hint">
        Generates a ready-to-run OpenFOAM case at the current design point
        (V={windSpeed} m/s, TSR={tipSpeedRatio}). Requires OpenFOAM installed
        locally or on a cluster — see the README inside the download.
      </p>
      <button onClick={runDownload} disabled={downloading}>
        {downloading ? "Building case..." : "Download OpenFOAM Case (.zip)"}
      </button>

      <h3>2c. Validate CFD results against BEM</h3>
      <p className="hint">
        Paste your revolution-averaged Cd/Cl from OpenFOAM's forceCoeffs output
        (or from the postProcessing file) to compare against the Stage-1 BEM prediction.
      </p>
      <div className="row">
        <label className="field inline">
          <span>CFD mean Cd</span>
          <input type="number" step={0.01} value={cfdCd} onChange={(e) => setCfdCd(parseFloat(e.target.value))} />
        </label>
        <label className="field inline">
          <span>CFD mean Cl</span>
          <input type="number" step={0.01} value={cfdCl} onChange={(e) => setCfdCl(parseFloat(e.target.value))} />
        </label>
        <button onClick={runValidation} disabled={validating}>
          {validating ? "Comparing..." : "Compare to BEM"}
        </button>
      </div>
      {validation && (
        <div className={`validation-result ${validation.within_engineering_tolerance ? "ok" : "warn"}`}>
          <p>BEM Ct: {validation.bem_ct.toFixed(3)} · CFD-equivalent Ct: {validation.cfd_ct_equivalent.toFixed(3)}</p>
          <p>Error: <strong>{validation.percent_error.toFixed(1)}%</strong>{" "}
            ({validation.within_engineering_tolerance ? "within" : "outside"} the 15% engineering tolerance)</p>
          <p className="hint">{validation.notes}</p>
        </div>
      )}
    </div>
  );
}
