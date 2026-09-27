"use client";

import React, { useState } from "react";
import {
  FileText,
  Download,
  Printer,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sparkles,
  Calendar,
  Layers,
} from "lucide-react";
import { generateReport } from "@/lib/api";
import { useAppStore, VariableType, MethodType } from "@/lib/store";

export default function ReportPage() {
  const { cycle, setCycle, variable, setVariable, lead, setLead, method, setMethod } = useAppStore();
  const [region, setRegion] = useState<string>("all");
  const [generating, setGenerating] = useState<boolean>(false);
  const [reportResult, setReportResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await generateReport(cycle, region, variable, lead, method);
      setReportResult(res);
    } catch (err: any) {
      console.error("Failed to generate report:", err);
      setError(err?.message || "Failed to generate PDF bulletin");
    } finally {
      setGenerating(false);
    }
  };

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return (
    <div className="flex-1 bg-[#0a0f18] p-6 overflow-y-auto space-y-6">
      {/* Top Banner */}
      <div className="bg-panel border border-panelBorder rounded-xl p-5 shadow-lg flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-accentOrange" />
            <h1 className="text-lg font-bold text-white tracking-wide">
              OPERATIONAL SHIFT BULLETIN GENERATOR
            </h1>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Automated publication-grade PDF bulletins for IMD shift handovers, emergency operations centers, and state disaster authorities.
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-alertRed/20 border border-alertRed/40 text-xs text-rose-300 font-mono">
          <ShieldCheck className="w-4 h-4 text-alertRed" />
          <span>Forecaster guidance — not a public warning</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Configuration Form */}
        <div className="bg-panel border border-panelBorder rounded-xl p-5 shadow-lg space-y-5">
          <h2 className="text-sm font-bold text-white border-b border-panelBorder pb-2 flex items-center gap-2">
            <Layers className="w-4 h-4 text-brandBlue" />
            Bulletin Parameters
          </h2>

          <div className="space-y-4 text-xs font-mono">
            {/* Cycle Date */}
            <div>
              <label className="text-gray-400 block mb-1">FORECAST CYCLE</label>
              <select
                value={cycle}
                onChange={(e) => setCycle(e.target.value)}
                className="w-full bg-background border border-panelBorder rounded p-2 text-white focus:outline-none focus:border-brandBlue cursor-pointer"
              >
                {[15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1].map((d) => {
                  const dateStr = `2025-08-${d < 10 ? "0" + d : d}`;
                  return (
                    <option key={dateStr} value={dateStr} className="bg-panel text-white">
                      {dateStr} 03:00 UTC (IMD Window)
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Sub-region */}
            <div>
              <label className="text-gray-400 block mb-1">TARGET SUB-REGION</label>
              <select
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="w-full bg-background border border-panelBorder rounded p-2 text-white focus:outline-none focus:border-brandBlue cursor-pointer"
              >
                <option value="all" className="bg-panel text-white">Entire Pilot Domain (Odisha & East India)</option>
                <option value="coastal" className="bg-panel text-white">Coastal Belt (Ports, Cyclones, Paradip)</option>
                <option value="inland" className="bg-panel text-white">Inland Plains (Mahanadi River Basin)</option>
                <option value="hills" className="bg-panel text-white">Eastern Ghats Hills (Orographic Rain)</option>
              </select>
            </div>

            {/* Variable */}
            <div>
              <label className="text-gray-400 block mb-1">PREDICTAND VARIABLE</label>
              <select
                value={variable}
                onChange={(e) => setVariable(e.target.value as VariableType)}
                className="w-full bg-background border border-panelBorder rounded p-2 text-white focus:outline-none focus:border-brandBlue cursor-pointer"
              >
                <option value="rain24_mm" className="bg-panel text-white">24h Accumulated Rainfall (rain24_mm)</option>
                <option value="t2m_max_c" className="bg-panel text-white">Max Daily Temperature (t2m_max_c)</option>
                <option value="ws10_ms" className="bg-panel text-white">10m Wind Speed (ws10_ms)</option>
              </select>
            </div>

            {/* Lead Time */}
            <div>
              <label className="text-gray-400 block mb-1">LEAD TIME HORIZON</label>
              <select
                value={lead}
                onChange={(e) => setLead(Number(e.target.value))}
                className="w-full bg-background border border-panelBorder rounded p-2 text-white focus:outline-none focus:border-brandBlue cursor-pointer"
              >
                <option value="24" className="bg-panel text-white">+24h (Next Day Outlook)</option>
                <option value="48" className="bg-panel text-white">+48h (Day 2 Outlook)</option>
                <option value="72" className="bg-panel text-white">+72h (Day 3 Outlook)</option>
                <option value="96" className="bg-panel text-white">+96h (Day 4 Outlook)</option>
                <option value="120" className="bg-panel text-white">+120h (Day 5 Outlook)</option>
              </select>
            </div>

            {/* Blending Method */}
            <div>
              <label className="text-gray-400 block mb-1">BLENDING ALGORITHM</label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value as MethodType)}
                className="w-full bg-background border border-panelBorder rounded p-2 text-white focus:outline-none focus:border-brandBlue cursor-pointer"
              >
                <option value="adaptive" className="bg-panel text-white">B3: Adaptive ML Gate (Recommended)</option>
                <option value="inverse_error" className="bg-panel text-white">B2: Inverse-Error Weighted</option>
                <option value="equal" className="bg-panel text-white">B1: Equal Mean Ensemble</option>
                <option value="best_single" className="bg-panel text-white">B0: Best Single Model</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-brandBlue to-navyDark hover:from-blue-600 hover:to-brandBlue text-white font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 cursor-pointer"
          >
            {generating ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Generating Shift Bulletin...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-accentOrange" />
                <span>Generate Official PDF Bulletin</span>
              </>
            )}
          </button>

          {error && (
            <div className="p-3 rounded bg-rose-950/80 border border-rose-600/50 text-xs text-rose-300">
              {error}
            </div>
          )}
        </div>

        {/* Right Column: Bulletin Preview & Download Card */}
        <div className="lg:col-span-2 space-y-6">
          {reportResult ? (
            <div className="bg-panel border border-panelBorder rounded-xl p-6 shadow-xl space-y-6 animate-in fade-in duration-300">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-panelBorder pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <h3 className="text-base font-bold text-white font-mono">
                      {reportResult.filename}
                    </h3>
                  </div>
                  <p className="text-xs text-gray-400 mt-1 font-mono">
                    Generated at {new Date(reportResult.generated_at).toLocaleString()} UTC
                  </p>
                </div>

                <a
                  href={`${API_BASE}${reportResult.download_url}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 rounded-lg bg-accentOrange hover:bg-orange-600 text-white font-bold text-xs flex items-center gap-2 shadow-lg transition-colors cursor-pointer"
                >
                  <Download className="w-4 h-4" />
                  <span>Download ReportLab PDF</span>
                </a>
              </div>

              {/* Mock Bulletin Render Preview */}
              <div className="bg-background rounded-lg p-5 border border-panelBorder font-mono text-xs space-y-4 text-gray-300">
                <div className="border-b border-panelBorder/60 pb-3 flex justify-between items-center text-[11px] text-gray-400">
                  <span>MINISTRY OF EARTH SCIENCES | SIH 2026 PS 26081</span>
                  <span>TEAM CODEX_2026 (159951)</span>
                </div>

                <div className="text-center py-2">
                  <div className="text-sm font-bold text-white tracking-wider">
                    OPERATIONAL WEATHER FORECAST SHIFT BULLETIN
                  </div>
                  <div className="text-[11px] text-accentOrange mt-1">
                    CYCLE: {reportResult.cycle} 03:00 UTC | LEAD: +{reportResult.lead}h | REGION: {reportResult.region.toUpperCase()}
                  </div>
                </div>

                <div className="bg-alertRed/10 border border-alertRed/30 rounded p-2.5 text-center text-rose-300 text-[11px]">
                  ⚠️ FORECASTER GUIDANCE — NOT A PUBLIC WARNING
                </div>

                <div className="space-y-2 pt-2">
                  <div className="font-bold text-white text-[11px]">EXECUTIVE METEOROLOGICAL SUMMARY:</div>
                  <p className="text-gray-300 leading-relaxed text-[11px]">
                    Synoptic monsoon depression active over Northwest Bay of Bengal and adjacent coastal Odisha.
                    VARUN-FUSION adaptive ML gate executed with temperature-scaled softmax weighting.
                    All primary NWP and AI model data sources verified with zero degradation.
                  </p>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                  <div className="bg-panel p-2.5 rounded border border-panelBorder">
                    <div className="text-[10px] text-gray-400">ECMWF IFS</div>
                    <div className="text-sm font-bold text-blue-400">34.2% wt</div>
                  </div>
                  <div className="bg-panel p-2.5 rounded border border-panelBorder">
                    <div className="text-[10px] text-gray-400">ECMWF AIFS</div>
                    <div className="text-sm font-bold text-purple-400">38.5% wt</div>
                  </div>
                  <div className="bg-panel p-2.5 rounded border border-panelBorder">
                    <div className="text-[10px] text-gray-400">NOAA GFS</div>
                    <div className="text-sm font-bold text-cyan-400">18.1% wt</div>
                  </div>
                  <div className="bg-panel p-2.5 rounded border border-panelBorder">
                    <div className="text-[10px] text-gray-400">NCMRWF</div>
                    <div className="text-sm font-bold text-sky-400">9.2% wt</div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-panel border border-panelBorder rounded-xl p-12 text-center text-gray-400 font-mono flex flex-col items-center justify-center space-y-4">
              <FileText className="w-12 h-12 text-gray-600 stroke-1" />
              <div>
                <div className="font-bold text-white text-sm">No Shift Bulletin Selected</div>
                <p className="text-xs text-gray-400 max-w-md mt-1">
                  Select cycle date, target region, and lead time on the left panel, then click &ldquo;Generate Official PDF Bulletin&rdquo; to produce a ReportLab vector shift document.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
