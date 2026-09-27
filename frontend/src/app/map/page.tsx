"use client";

import React, { useState } from "react";
import { MapViewer } from "@/components/MapViewer";
import { PointInspector } from "@/components/PointInspector";
import { BottomStatusBar } from "@/components/BottomStatusBar";
import { useAppStore } from "@/lib/store";

export default function MapPage() {
  const { selectedPoint, setSelectedPoint } = useAppStore();

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-80px)] overflow-hidden relative">
      {/* Central Interactive Viewport with Map and Optional Inspector Sidebar */}
      <div className="flex-1 flex min-h-0 relative">
        {/* Full-width Map Canvas */}
        <div className="flex-1 relative h-full">
          <MapViewer />
        </div>

        {/* Slide-over / Docked Point Inspector */}
        {selectedPoint && (
          <div className="relative z-30 h-full shrink-0 border-l border-panelBorder animate-in slide-in-from-right duration-200">
            <PointInspector onClose={() => setSelectedPoint(null)} />
          </div>
        )}
      </div>

      {/* Operational Resilient Status Bar */}
      <BottomStatusBar />
    </div>
  );
}
