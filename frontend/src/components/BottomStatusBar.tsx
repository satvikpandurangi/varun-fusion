"use client";

import React from "react";
import { CheckCircle2, AlertTriangle, Radio } from "lucide-react";
import { MODEL_COLORS } from "@/lib/constants";

interface BottomStatusBarProps {
  fallbackActive?: boolean;
  fallbackReason?: string | null;
  dominantSource?: string;
  confidenceMean?: number;
}

export function BottomStatusBar({
  fallbackActive = false,
  fallbackReason = null,
  dominantSource,
  confidenceMean = 0.82,
}: BottomStatusBarProps) {
  const sources = [
    { id: "ecmwf_ifs", label: "IFS 0.25°", status: "ON-TIME" },
    { id: "ecmwf_aifs", label: "AIFS 0.25°", status: "ON-TIME" },
    { id: "noaa_gfs", label: "GFS 0.25°", status: "ON-TIME" },
    { id: "ncmrwf", label: "NCMRWF", status: "SAMPLE" },
  ];

  return (
    <div className="bg-panel/95 backdrop-blur border-t border-panelBorder px-4 py-1.5 flex flex-wrap items-center justify-between gap-4 text-xs font-mono text-gray-300">
      {/* Sources Feed Status */}
      <div className="flex items-center gap-3">
        <span className="text-[10px] text-gray-400 font-bold uppercase tracking-wider flex items-center gap-1">
          <Radio className="w-3 h-3 text-emerald-400 animate-pulse" />
          FEEDS:
        </span>
        <div className="flex items-center gap-2">
          {sources.map((s) => {
            const meta = MODEL_COLORS[s.id] || { color: "#3B82F6" };
            return (
              <div
                key={s.id}
                className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-background/60 border border-panelBorder"
              >
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: meta.color }} />
                <span className="font-semibold text-white">{s.label}</span>
                <span className="text-[10px] text-emerald-400 font-normal">[{s.status}]</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Fallback Resilience Pill */}
      <div className="flex items-center gap-3">
        <div
          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded border text-[11px] font-semibold ${
            fallbackActive
              ? "bg-amber-950/80 text-amber-300 border-amber-600/50"
              : "bg-emerald-950/80 text-emerald-300 border-emerald-600/40"
          }`}
        >
          {fallbackActive ? (
            <>
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              <span>FALLBACK ACTIVE: {fallbackReason || "Degraded mode"}</span>
            </>
          ) : (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>FALLBACK NOMINAL: Zero Degradation (All Sources Verified)</span>
            </>
          )}
        </div>

        {/* Confidence metric indicator */}
        <div className="flex items-center gap-1 text-[11px] text-gray-400 bg-background/50 px-2 py-0.5 rounded border border-panelBorder">
          <span>DOMAIN CONFIDENCE:</span>
          <span className="font-bold text-white">{(confidenceMean * 100).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
}
