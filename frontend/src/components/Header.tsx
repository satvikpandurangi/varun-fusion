"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CloudRain, Thermometer, Wind, AlertTriangle, Play, Pause, ShieldCheck, Database, Layers } from "lucide-react";
import { MethodType, useAppStore, VariableType } from "@/lib/store";

const VARIABLES: { id: VariableType; label: string; icon: any }[] = [
  { id: "rain24_mm", label: "24h Rain", icon: CloudRain },
  { id: "t2m_max_c", label: "Max Temp", icon: Thermometer },
  { id: "ws10_ms", label: "Wind Speed", icon: Wind },
];

const METHODS: { id: MethodType; label: string }[] = [
  { id: "adaptive", label: "B3: Adaptive ML Gate" },
  { id: "inverse_error", label: "B2: Inverse-Error" },
  { id: "equal", label: "B1: Equal Mean" },
  { id: "best_single", label: "B0: Best Single" },
];

const NAV_LINKS = [
  { href: "/map", label: "Operational Map" },
  { href: "/skill", label: "Skill Engine" },
  { href: "/evaluation", label: "Baseline Scorecard" },
  { href: "/report", label: "Shift Bulletins" },
  { href: "/about", label: "Methodology" },
];

export function Header() {
  const pathname = usePathname();
  const {
    cycle,
    variable,
    lead,
    method,
    isPlaying,
    provenance,
    setCycle,
    setVariable,
    setLead,
    setMethod,
    setIsPlaying,
  } = useAppStore();

  // Auto-play lead times
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        setLead(lead >= 120 ? 24 : lead + 24);
      }, 1800);
    }
    return () => clearInterval(interval);
  }, [isPlaying, lead, setLead]);

  return (
    <header className="bg-panel border-b border-panelBorder sticky top-0 z-50">
      {/* Top Warning Disclaimer Banner */}
      <div className="bg-alertRed/90 text-white text-xs font-semibold py-1 px-4 flex items-center justify-between tracking-wide">
        <div className="flex items-center gap-2 mx-auto">
          <ShieldCheck className="w-3.5 h-3.5 text-white" />
          <span>OPERATIONAL NOTICE: FORECASTER GUIDANCE — NOT A PUBLIC WARNING</span>
          <span className="opacity-75">| MoES SIH 2026 PS 26081 | Team CodeX_2026 (159951)</span>
        </div>
      </div>

      <div className="max-w-[1720px] mx-auto px-4 py-2 flex flex-wrap items-center justify-between gap-4">
        {/* Logo and Nav links */}
        <div className="flex items-center gap-6">
          <Link href="/map" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-md bg-gradient-to-br from-brandBlue via-navyDark to-accentOrange flex items-center justify-center font-bold text-white shadow-md">
              V
            </div>
            <div>
              <div className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
                VARUN-FUSION
                <span className="text-[10px] font-normal px-1.5 py-0.5 rounded bg-navyDark text-blue-200 border border-blue-400/20">
                  v1.0
                </span>
              </div>
              <div className="text-[10px] text-gray-400 font-mono">East India & Odisha Pilot</div>
            </div>
          </Link>

          <nav className="flex items-center gap-1 bg-background/50 p-1 rounded-md border border-panelBorder">
            {NAV_LINKS.map((link) => {
              const active = pathname === link.href || (pathname === "/" && link.href === "/map");
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`text-xs px-2.5 py-1 rounded transition-colors font-medium ${
                    active
                      ? "bg-brandBlue text-white shadow-sm"
                      : "text-gray-300 hover:text-white hover:bg-panelHover"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Operational Controls Bar */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Cycle Picker */}
          <div className="flex items-center gap-1.5 bg-background border border-panelBorder rounded px-2.5 py-1">
            <span className="text-[11px] text-gray-400 font-mono">CYCLE:</span>
            <select
              value={cycle}
              onChange={(e) => setCycle(e.target.value)}
              className="bg-transparent text-xs text-white font-mono focus:outline-none cursor-pointer"
            >
              {[15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1].map((d) => {
                const dateStr = `2025-08-${d < 10 ? "0" + d : d}`;
                return (
                  <option key={dateStr} value={dateStr} className="bg-panel text-white">
                    {dateStr} 00 UTC
                  </option>
                );
              })}
            </select>
          </div>

          {/* Variable Pills */}
          <div className="flex items-center gap-1 bg-background border border-panelBorder rounded p-0.5">
            {VARIABLES.map((v) => {
              const Icon = v.icon;
              const isSelected = variable === v.id;
              return (
                <button
                  key={v.id}
                  onClick={() => setVariable(v.id)}
                  className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded transition-all ${
                    isSelected
                      ? "bg-accentOrange text-white font-semibold shadow"
                      : "text-gray-400 hover:text-gray-200 hover:bg-panelHover"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{v.label}</span>
                </button>
              );
            })}
          </div>

          {/* Lead Slider with Play/Pause */}
          <div className="flex items-center gap-2 bg-background border border-panelBorder rounded px-3 py-1">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className="text-accentOrange hover:text-white transition-colors"
              title={isPlaying ? "Pause Lead Loop" : "Play Lead Animation"}
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <span className="text-[11px] text-gray-400 font-mono">LEAD:</span>
            <span className="text-xs font-mono font-bold text-accentOrange w-10 text-right">+{lead}h</span>
            <input
              type="range"
              min="24"
              max="120"
              step="24"
              value={lead}
              onChange={(e) => setLead(Number(e.target.value))}
              className="w-20 accent-[#F28C28] cursor-pointer"
            />
          </div>

          {/* Method Selector */}
          <div className="flex items-center gap-1.5 bg-background border border-panelBorder rounded px-2.5 py-1">
            <span className="text-[11px] text-gray-400 font-mono">METHOD:</span>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as MethodType)}
              className="bg-transparent text-xs text-white focus:outline-none cursor-pointer font-medium"
            >
              {METHODS.map((m) => (
                <option key={m.id} value={m.id} className="bg-panel text-white">
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          {/* Provenance Pill */}
          <div
            className={`flex items-center gap-1 text-[10px] font-mono font-semibold px-2 py-1 rounded border ${
              provenance === "LIVE"
                ? "bg-emerald-950/80 text-emerald-400 border-emerald-700/50"
                : "bg-blue-950/80 text-blue-300 border-blue-700/50"
            }`}
          >
            <Database className="w-3 h-3" />
            <span>{provenance}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
