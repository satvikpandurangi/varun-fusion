"use client";

import React, { useEffect, useState } from "react";
import { X, Activity, ShieldAlert, Cpu, BarChart2, TrendingUp } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { fetchExplain, fetchPointInspection } from "@/lib/api";
import { MODEL_COLORS } from "@/lib/constants";
import { useAppStore } from "@/lib/store";

interface PointInspectorProps {
  onClose: () => void;
}

export function PointInspector({ onClose }: PointInspectorProps) {
  const { selectedPoint, cycle, variable, lead, method } = useAppStore();
  const [data, setData] = useState<any>(null);
  const [explainData, setExplainData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!selectedPoint) return;
    let isMounted = true;
    setLoading(true);

    Promise.all([
      fetchPointInspection(selectedPoint.lat, selectedPoint.lon, cycle, variable, method),
      fetchExplain(selectedPoint.lat, selectedPoint.lon, "ecmwf_ifs", variable, lead, cycle).catch(() => null),
    ])
      .then(([ptRes, expRes]) => {
        if (isMounted) {
          setData(ptRes);
          setExplainData(expRes);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Point inspection error:", err);
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedPoint, cycle, variable, lead, method]);

  if (!selectedPoint) return null;

  const currentStep = data?.time_series?.find((s: any) => s.lead === lead) || data?.time_series?.[0];

  return (
    <div className="w-96 bg-panel border-l border-panelBorder flex flex-col h-full overflow-y-auto text-xs font-sans text-gray-200 shadow-2xl">
      {/* Header */}
      <div className="p-3.5 border-b border-panelBorder bg-background/50 flex items-center justify-between sticky top-0 z-10 backdrop-blur">
        <div>
          <div className="flex items-center gap-1.5 text-xs font-bold text-white uppercase tracking-wider">
            <Activity className="w-4 h-4 text-accentOrange" />
            <span>CELL INSPECTOR</span>
          </div>
          <div className="font-mono text-[11px] text-gray-400 mt-0.5">
            {selectedPoint.lat.toFixed(2)}°N, {selectedPoint.lon.toFixed(2)}°E
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded text-gray-400 hover:text-white hover:bg-panelBorder/50 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div className="p-6 text-center text-gray-400 font-mono animate-pulse">
          Fetching multi-model ensemble telemetry...
        </div>
      ) : (
        <div className="p-4 space-y-5">
          {/* Current Lead Snapshot */}
          <div className="bg-background/80 rounded-lg p-3.5 border border-panelBorder">
            <div className="flex items-center justify-between text-gray-400 font-mono text-[10px] mb-1">
              <span>LEAD +{lead}h BLENDED FORECAST</span>
              <span
                className={`px-1.5 py-0.5 rounded font-bold ${
                  currentStep?.confidence_label === "HIGH"
                    ? "bg-emerald-950 text-emerald-400"
                    : currentStep?.confidence_label === "MEDIUM"
                    ? "bg-amber-950 text-amber-400"
                    : "bg-rose-950 text-rose-400"
                }`}
              >
                {currentStep?.confidence_label || "HIGH"} CONFIDENCE
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold font-mono text-white">
                {currentStep?.blend_value ?? "--"}
              </span>
              <span className="text-xs text-accentOrange font-mono">{data?.unit}</span>
            </div>
            <div className="mt-2 pt-2 border-t border-panelBorder/50 flex items-center justify-between text-[11px]">
              <span className="text-gray-400">Dominant Model:</span>
              <span className="font-bold text-white">
                {MODEL_COLORS[currentStep?.dominant_source]?.name || currentStep?.dominant_source} (
                {((currentStep?.dominant_weight || 0) * 100).toFixed(0)}%)
              </span>
            </div>
          </div>

          {/* Model Weights Breakdown Bar */}
          <div>
            <div className="text-[11px] font-bold text-gray-300 uppercase tracking-wider mb-2 flex items-center justify-between">
              <span>Model Weight Allocation</span>
              <span className="text-[10px] text-gray-500 font-mono">Σ w_m = 1.0</span>
            </div>
            {/* Stacked Bar */}
            <div className="w-full h-3 rounded overflow-hidden flex bg-background border border-panelBorder">
              {currentStep &&
                Object.entries(currentStep.weights || {}).map(([mid, w]: [string, any]) => {
                  const meta = MODEL_COLORS[mid] || { name: mid, color: "#3B82F6", kind: "NWP" };
                  const pct = Math.max(0, Number(w) * 100);
                  if (pct < 1) return null;
                  return (
                    <div
                      key={mid}
                      style={{ width: `${pct}%`, backgroundColor: meta.color }}
                      title={`${meta.name}: ${pct.toFixed(1)}%`}
                    />
                  );
                })}
            </div>

            {/* Models Value Cards */}
            <div className="grid grid-cols-2 gap-2 mt-3">
              {currentStep &&
                Object.entries(currentStep.models || {}).map(([mid, val]: [string, any]) => {
                  const meta = MODEL_COLORS[mid] || { name: mid, color: "#3B82F6", kind: "NWP" };
                  const w = currentStep.weights?.[mid] ?? 0;
                  return (
                    <div key={mid} className="bg-background/60 p-2 rounded border border-panelBorder">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-bold text-white flex items-center gap-1">
                          <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: meta.color }} />
                          {meta.name}
                        </span>
                        <span className="text-[9px] px-1 rounded bg-panelBorder font-mono text-gray-300">
                          {meta.kind}
                        </span>
                      </div>
                      <div className="flex items-baseline justify-between font-mono">
                        <span className="text-sm font-bold text-white">{val}</span>
                        <span className="text-[10px] text-accentOrange">w: {(w * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Time Series 5-Lead Chart */}
          <div>
            <div className="text-[11px] font-bold text-gray-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-brandBlue" />
              <span>Lead Evolution (24h to 120h)</span>
            </div>
            <div className="h-44 w-full bg-background/50 rounded-lg p-2 border border-panelBorder">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data?.time_series || []} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                  <XAxis dataKey="lead" tick={{ fill: "#94a3b8", fontSize: 10 }} tickFormatter={(l) => `+${l}h`} />
                  <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#121A2B", borderColor: "rgba(255,255,255,0.1)", fontSize: "11px" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="blend_value"
                    name="Blend"
                    stroke="#F28C28"
                    strokeWidth={2.5}
                    dot={{ fill: "#F28C28", r: 3 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="models.ecmwf_ifs"
                    name="IFS"
                    stroke="#3B82F6"
                    strokeWidth={1.5}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="models.ecmwf_aifs"
                    name="AIFS"
                    stroke="#A855F7"
                    strokeWidth={1.5}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="models.noaa_gfs"
                    name="GFS"
                    stroke="#06B6D4"
                    strokeWidth={1.5}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Explainability Tree-SHAP Feature Contribution */}
          {explainData && (
            <div className="bg-background/60 p-3 rounded-lg border border-panelBorder">
              <div className="text-[11px] font-bold text-gray-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-purple-400" />
                <span>Explainability (Tree-SHAP)</span>
              </div>
              <p className="text-[10px] text-gray-400 mb-2">
                Local feature impact on predicted error for ECMWF IFS at this cell:
              </p>
              <div className="space-y-1.5">
                {Object.entries(explainData.shap_contributions || {})
                  .filter(([k]) => k !== "base_value" && k !== "source_idx")
                  .slice(0, 4)
                  .map(([feat, val]: [string, any]) => {
                    const isPositive = Number(val) >= 0;
                    return (
                      <div key={feat} className="flex items-center justify-between text-[10px] font-mono">
                        <span className="text-gray-300">{feat}</span>
                        <span className={isPositive ? "text-rose-400 font-bold" : "text-emerald-400 font-bold"}>
                          {isPositive ? `+${val}` : val}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
