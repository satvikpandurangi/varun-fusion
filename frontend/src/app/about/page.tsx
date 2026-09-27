"use client";

import React from "react";
import {
  ShieldCheck,
  Award,
  Layers,
  Cpu,
  Database,
  Compass,
  FileCode,
  BookOpen,
  GitBranch,
} from "lucide-react";

export default function AboutPage() {
  return (
    <div className="flex-1 bg-[#0a0f18] p-6 lg:p-10 overflow-y-auto space-y-8 max-w-5xl mx-auto">
      {/* Top Banner */}
      <div className="bg-panel border border-panelBorder rounded-xl p-6 shadow-xl space-y-3">
        <div className="flex items-center gap-2 text-accentOrange text-xs font-mono font-bold uppercase tracking-wider">
          <Award className="w-4 h-4" />
          <span>Smart India Hackathon 2026 | Problem Statement 26081</span>
        </div>
        <h1 className="text-2xl font-bold text-white tracking-tight">
          VARUN-FUSION: Adaptive AI–NWP Multi-Model Forecast Blending System
        </h1>
        <p className="text-xs text-gray-300 leading-relaxed font-mono">
          Ministry of Earth Sciences (MoES), Government of India | Theme: Disaster Management | Team CodeX_2026 (Team ID 159951)
        </p>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-alertRed/20 border border-alertRed/40 text-xs text-rose-300 font-mono font-semibold">
          <ShieldCheck className="w-4 h-4 text-alertRed" />
          <span>OPERATIONAL NOTICE: Forecaster guidance — not a public warning</span>
        </div>
      </div>

      {/* System Architecture Section */}
      <div className="bg-panel border border-panelBorder rounded-xl p-6 shadow-xl space-y-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2 border-b border-panelBorder pb-3">
          <Layers className="w-5 h-5 text-brandBlue" />
          1. System Philosophy & Workflow
        </h2>
        <p className="text-xs text-gray-300 leading-relaxed font-mono">
          VARUN-FUSION is an operational post-processing layer designed to ingest heterogeneous gridded forecasts from global and national NWP centres (ECMWF IFS, NOAA GFS, NCMRWF) and cutting-edge data-driven weather AI models (ECMWF AIFS). Operating on an aligned 0.25° grid over India (pilot: East India &amp; Odisha coast), it dynamically blends predictions using rolling empirical verification skill and contextual features.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-2 text-xs font-mono">
          <div className="bg-background/80 p-3.5 rounded-lg border border-panelBorder">
            <div className="text-accentOrange font-bold mb-1">01. INGESTION</div>
            <div className="text-[11px] text-gray-400">ECMWF IFS &amp; AIFS, NOAA GFS, NCMRWF via unified adapters.</div>
          </div>
          <div className="bg-background/80 p-3.5 rounded-lg border border-panelBorder">
            <div className="text-brandBlue font-bold mb-1">02. HARMONIZATION</div>
            <div className="text-[11px] text-gray-400">Flux-conserving regridding, unit conversion, IMD 03 UTC sync.</div>
          </div>
          <div className="bg-background/80 p-3.5 rounded-lg border border-panelBorder">
            <div className="text-emerald-400 font-bold mb-1">03. SKILL EVALUATION</div>
            <div className="text-[11px] text-gray-400">Rolling 7–30d RMSE, MAE, BIAS, FSS (1/3/5/9 scales), CRPS.</div>
          </div>
          <div className="bg-background/80 p-3.5 rounded-lg border border-panelBorder">
            <div className="text-purple-400 font-bold mb-1">04. ADAPTIVE GATE</div>
            <div className="text-[11px] text-gray-400">LightGBM contextual weighting + water-filling simplex bounds.</div>
          </div>
        </div>
      </div>

      {/* Mathematical Formulations Section */}
      <div className="bg-panel border border-panelBorder rounded-xl p-6 shadow-xl space-y-5">
        <h2 className="text-base font-bold text-white flex items-center gap-2 border-b border-panelBorder pb-3">
          <Cpu className="w-5 h-5 text-purple-400" />
          2. Mathematical &amp; Algorithmic Foundations
        </h2>

        <div className="space-y-4 text-xs font-mono text-gray-300">
          {/* Baseline B2 Inverse Error */}
          <div className="bg-background/80 p-4 rounded-lg border border-panelBorder space-y-2">
            <div className="font-bold text-emerald-400">B2: Inverse-Error Variance Weighting</div>
            <p className="text-[11px] text-gray-400">
              Raw weights are inversely proportional to rolling continuous error:
            </p>
            <div className="bg-panel p-2 rounded text-center text-accentOrange text-sm">
              w_m &prop; 1 / (RMSE_m + &epsilon;)^p &nbsp;&nbsp;(where p = 1.0, &epsilon; = 1e-4)
            </div>
            <p className="text-[11px] text-gray-400">
              Subject to the strict simplex constraint: &sum; w_m = 1.0 and bounds w_min = 0.05, w_max = 0.80 via water-filling projection.
            </p>
          </div>

          {/* Adaptive ML Gate B3 */}
          <div className="bg-background/80 p-4 rounded-lg border border-panelBorder space-y-2">
            <div className="font-bold text-purple-400">B3: Contextual Adaptive ML Gate</div>
            <p className="text-[11px] text-gray-400">
              A gradient-boosted LightGBM regressor predicts expected MAE for each model based on synoptic weather regime, terrain elevation, sub-region ID, ensemble spread, and cyclical DOY. Weights are formed via temperature-scaled softmax:
            </p>
            <div className="bg-panel p-2 rounded text-center text-accentOrange text-sm">
              w_m = exp(-e&#770;_m / &tau;) / &sum;_k exp(-e&#770;_k / &tau;) &nbsp;&nbsp;(with &tau; = 1.5)
            </div>
            <p className="text-[11px] text-gray-400">
              Explained in real-time to the duty meteorologist using Tree-SHAP additive feature attributions.
            </p>
          </div>

          {/* Minority Signal Retention */}
          <div className="bg-background/80 p-4 rounded-lg border border-panelBorder space-y-2">
            <div className="font-bold text-rose-400">Extreme Event &amp; Minority Signal Preservation</div>
            <p className="text-[11px] text-gray-400">
              Traditional multi-model means dilute isolated heavy rainfall peaks (&gt;64.5 mm/day). When a high-historical-skill model triggers an extreme threshold but the ensemble blend does not, a minority alarm is triggered and event weights are applied via Critical Success Index (CSI) and Fractions Skill Score (FSS):
            </p>
            <div className="bg-panel p-2 rounded text-center text-accentOrange text-sm">
              FSS(n) = 1 - [ MSE(P_fcst(n), P_obs(n)) / (MSE_ref) ]
            </div>
          </div>
        </div>
      </div>

      {/* Degradation Cascade */}
      <div className="bg-panel border border-panelBorder rounded-xl p-6 shadow-xl space-y-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2 border-b border-panelBorder pb-3">
          <GitBranch className="w-5 h-5 text-accentOrange" />
          3. Automated Fail-Safe Degradation Hierarchy
        </h2>
        <p className="text-xs text-gray-300 leading-relaxed font-mono">
          Under operational data latency or network outages, the system never halts. An automated fallback cascade ensures continuous forecast delivery:
        </p>
        <div className="bg-background/80 p-4 rounded-lg border border-panelBorder font-mono text-xs text-gray-300 space-y-2">
          <div className="flex items-center gap-2 text-purple-400 font-bold">
            <span>Primary [Level 0]:</span>
            <span className="text-white">B3 Adaptive ML Gate (Contextual Softmax)</span>
          </div>
          <div className="flex items-center gap-2 text-emerald-400 font-bold pl-4">
            <span>&darr; Fallback [Level 1]:</span>
            <span className="text-white">B2 Inverse-Error Weighted (Rolling Verification Skill)</span>
          </div>
          <div className="flex items-center gap-2 text-blue-400 font-bold pl-8">
            <span>&darr; Fallback [Level 2]:</span>
            <span className="text-white">B0 Best Single Model (Highest historical CSI/RMSE)</span>
          </div>
          <div className="flex items-center gap-2 text-gray-400 font-bold pl-12">
            <span>&darr; Fallback [Level 3]:</span>
            <span className="text-white">B1 Equal Mean Ensemble (Simple arithmetic average)</span>
          </div>
        </div>
      </div>

      {/* Data Provenance & Open Licences */}
      <div className="bg-panel border border-panelBorder rounded-xl p-6 shadow-xl space-y-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2 border-b border-panelBorder pb-3">
          <Database className="w-5 h-5 text-cyan-400" />
          4. Data Provenance &amp; Attribution
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          <div className="bg-background/80 p-3.5 rounded-lg border border-panelBorder space-y-1">
            <div className="font-bold text-blue-400">ECMWF IFS &amp; AIFS</div>
            <div className="text-[11px] text-gray-400">
              European Centre for Medium-Range Weather Forecasts Open Data. Licensed under Creative Commons CC-BY 4.0.
            </div>
          </div>
          <div className="bg-background/80 p-3.5 rounded-lg border border-panelBorder space-y-1">
            <div className="font-bold text-cyan-400">NOAA GFS (Global Forecast System)</div>
            <div className="text-[11px] text-gray-400">
              National Oceanic and Atmospheric Administration. Public Domain / CC0 Open Government Data.
            </div>
          </div>
          <div className="bg-background/80 p-3.5 rounded-lg border border-panelBorder space-y-1">
            <div className="font-bold text-purple-400">NCMRWF Unified Model</div>
            <div className="text-[11px] text-gray-400">
              National Centre for Medium Range Weather Forecasting, Ministry of Earth Sciences, New Delhi.
            </div>
          </div>
          <div className="bg-background/80 p-3.5 rounded-lg border border-panelBorder space-y-1">
            <div className="font-bold text-emerald-400">IMD Gridded Observations</div>
            <div className="text-[11px] text-gray-400">
              India Meteorological Department 0.25° gridded rainfall and temperature analysis.
            </div>
          </div>
        </div>
      </div>

      {/* Team & SIH Footer */}
      <div className="text-center font-mono text-xs text-gray-500 py-4 border-t border-panelBorder">
        VARUN-FUSION &bull; Smart India Hackathon 2026 &bull; Team CodeX_2026 (Team ID 159951) &bull; Problem Statement 26081
      </div>
    </div>
  );
}
