"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  Layers,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  AlertTriangle,
  Shield,
  Scale,
  CloudRain,
  MapPin,
  Eye,
  Sliders,
  Play,
  Pause,
  ChevronRight,
  ChevronLeft,
} from "lucide-react";
import { fetchBlend } from "@/lib/api";
import { COLOR_SCALES, DEFAULT_DOMAIN, MODEL_COLORS } from "@/lib/constants";
import { LayerType, useAppStore } from "@/lib/store";

// Landmarks in the East India / Odisha pilot domain
const CITIES = [
  { name: "Bhubaneswar", lat: 20.30, lon: 85.82, capital: true },
  { name: "Cuttack", lat: 20.46, lon: 85.88 },
  { name: "Puri", lat: 19.81, lon: 85.83 },
  { name: "Paradip Port", lat: 20.32, lon: 86.61, port: true },
  { name: "Balasore", lat: 21.49, lon: 86.93 },
  { name: "Gopalpur", lat: 19.26, lon: 84.91 },
  { name: "Sambalpur", lat: 21.47, lon: 83.97 },
  { name: "Koraput", lat: 18.81, lon: 82.71 },
  { name: "Kolkata", lat: 22.57, lon: 88.36 },
  { name: "Visakhapatnam", lat: 17.68, lon: 83.22, port: true },
];

// Simplified coastline polyline for Bay of Bengal (lon, lat)
const COASTLINE_POINTS = [
  [83.0, 17.0],
  [83.3, 17.7],
  [84.0, 18.3],
  [84.9, 19.3],
  [85.8, 19.8],
  [86.6, 20.3],
  [86.9, 21.0],
  [87.1, 21.5],
  [87.5, 21.7],
  [88.0, 21.6],
  [88.8, 21.8],
  [89.5, 22.0],
  [90.0, 22.2],
];

interface MapViewerProps {
  onSelectPoint?: (lat: number, lon: number) => void;
}

export function MapViewer({ onSelectPoint }: MapViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const {
    cycle,
    variable,
    lead,
    method,
    activeLayer,
    selectedPoint,
    isPlaying,
    setActiveLayer,
    setSelectedPoint,
    setLead,
    setIsPlaying,
    setProvenance,
  } = useAppStore();

  const [gridData, setGridData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Zoom and pan state
  const [scale, setScale] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Hover state
  const [hoverInfo, setHoverInfo] = useState<{
    x: number;
    y: number;
    lat: number;
    lon: number;
    val: number | null;
    domSource?: string;
    domWeight?: number;
    confLabel?: string;
    confScore?: number;
    isMinority?: boolean;
    minorityDetail?: any;
  } | null>(null);

  // Layer opacity
  const [layerOpacity, setLayerOpacity] = useState<number>(0.85);

  // Fetch forecast blend payload
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    fetchBlend(cycle, variable, lead, method)
      .then((data) => {
        if (!active) return;
        setGridData(data);
        if (data.provenance) setProvenance(data.provenance);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        console.error("MapViewer fetch error:", err);
        setError("Failed to load forecast grid");
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [cycle, variable, lead, method, setProvenance]);

  // Coordinate projections: Lon/Lat to Canvas X/Y
  const project = useCallback(
    (lon: number, lat: number, width: number, height: number) => {
      const margin = 40;
      const drawWidth = width - margin * 2;
      const drawHeight = height - margin * 2;

      const normX = (lon - DEFAULT_DOMAIN.lon_min) / (DEFAULT_DOMAIN.lon_max - DEFAULT_DOMAIN.lon_min);
      // Invert Y because lat increases northward while canvas Y increases downward
      const normY = (DEFAULT_DOMAIN.lat_max - lat) / (DEFAULT_DOMAIN.lat_max - DEFAULT_DOMAIN.lat_min);

      const baseCenterX = margin + drawWidth / 2;
      const baseCenterY = margin + drawHeight / 2;

      const px = margin + normX * drawWidth;
      const py = margin + normY * drawHeight;

      // Apply zoom and pan around center
      const finalX = baseCenterX + (px - baseCenterX) * scale + pan.x;
      const finalY = baseCenterY + (py - baseCenterY) * scale + pan.y;

      return { x: finalX, y: finalY };
    },
    [scale, pan]
  );

  // Inverse projection: Canvas X/Y to Lon/Lat
  const unproject = useCallback(
    (x: number, y: number, width: number, height: number) => {
      const margin = 40;
      const drawWidth = width - margin * 2;
      const drawHeight = height - margin * 2;

      const baseCenterX = margin + drawWidth / 2;
      const baseCenterY = margin + drawHeight / 2;

      const px = (x - pan.x - baseCenterX) / scale + baseCenterX;
      const py = (y - pan.y - baseCenterY) / scale + baseCenterY;

      const normX = (px - margin) / drawWidth;
      const normY = (py - margin) / drawHeight;

      const lon = DEFAULT_DOMAIN.lon_min + normX * (DEFAULT_DOMAIN.lon_max - DEFAULT_DOMAIN.lon_min);
      const lat = DEFAULT_DOMAIN.lat_max - normY * (DEFAULT_DOMAIN.lat_max - DEFAULT_DOMAIN.lat_min);

      return { lat, lon };
    },
    [scale, pan]
  );

  // Color lookup helper
  const getColor = useCallback(
    (val: number, varName: string) => {
      const scaleDef = (COLOR_SCALES as any)[varName] || COLOR_SCALES.rain24_mm;
      let matched = scaleDef[0].color;
      for (let i = 0; i < scaleDef.length; i++) {
        if (val >= scaleDef[i].threshold) {
          matched = scaleDef[i].color;
        } else {
          break;
        }
      }
      return matched;
    },
    []
  );

  // Render canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // 1. Clear background - dark radar slate
    ctx.fillStyle = "#0c131f";
    ctx.fillRect(0, 0, width, height);

    // 2. Draw Ocean vs Land Demarcation (Bay of Bengal is south-east of the coastline)
    ctx.save();
    ctx.beginPath();
    const seaTopRight = project(DEFAULT_DOMAIN.lon_max, DEFAULT_DOMAIN.lat_max, width, height);
    const seaBottomRight = project(DEFAULT_DOMAIN.lon_max, DEFAULT_DOMAIN.lat_min, width, height);
    const seaBottomLeft = project(DEFAULT_DOMAIN.lon_min, DEFAULT_DOMAIN.lat_min, width, height);

    ctx.moveTo(seaBottomLeft.x, seaBottomLeft.y);
    for (const pt of COASTLINE_POINTS) {
      const p = project(pt[0], pt[1], width, height);
      ctx.lineTo(p.x, p.y);
    }
    ctx.lineTo(seaTopRight.x, seaTopRight.y);
    ctx.lineTo(seaBottomRight.x, seaBottomRight.y);
    ctx.closePath();

    ctx.fillStyle = "#09101d"; // Deep ocean blue-black
    ctx.fill();

    // Subtle ocean water pattern label
    const pOcean = project(87.5, 18.5, width, height);
    ctx.fillStyle = "rgba(56, 189, 248, 0.12)";
    ctx.font = "italic bold 16px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("BAY OF BENGAL", pOcean.x, pOcean.y);
    ctx.restore();

    // 3. Draw Graticule Lines (Lat/Lon grid)
    ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    ctx.lineWidth = 1;
    ctx.font = "10px monospace";
    ctx.fillStyle = "rgba(148, 163, 184, 0.6)";

    for (let lat = 17; lat <= 24; lat += 1) {
      const p1 = project(DEFAULT_DOMAIN.lon_min, lat, width, height);
      const p2 = project(DEFAULT_DOMAIN.lon_max, lat, width, height);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
      ctx.textAlign = "left";
      ctx.fillText(`${lat}°N`, p1.x + 4, p1.y - 4);
    }

    for (let lon = 81; lon <= 90; lon += 1) {
      const p1 = project(lon, DEFAULT_DOMAIN.lat_min, width, height);
      const p2 = project(lon, DEFAULT_DOMAIN.lat_max, width, height);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
      ctx.textAlign = "center";
      ctx.fillText(`${lon}°E`, p1.x, p1.y - 6);
    }

    // 4. Render Raster Heatmap / Weights / Confidence Layer
    if (gridData && gridData.coordinates && gridData.grid) {
      const lats: number[] = gridData.coordinates.lats;
      const lons: number[] = gridData.coordinates.lons;
      const nLats = lats.length;
      const nLons = lons.length;

      ctx.save();
      ctx.globalAlpha = layerOpacity;

      for (let i = 0; i < nLats; i++) {
        const lat = lats[i];
        for (let j = 0; j < nLons; j++) {
          const lon = lons[j];
          const val = gridData.grid[i]?.[j] ?? 0;
          const domSource = gridData.dominant_source?.[i]?.[j] || "ecmwf_ifs";
          const domWeight = gridData.dominant_weight?.[i]?.[j] || 0.25;
          const confScore = gridData.confidence_score?.[i]?.[j] || 0.8;
          const extremeVal = gridData.extreme_risk?.[i]?.[j] || 0.0;

          // Compute cell bounding box (0.25 deg)
          const pNW = project(lon - 0.125, lat + 0.125, width, height);
          const pSE = project(lon + 0.125, lat - 0.125, width, height);
          const cellW = Math.max(1, pSE.x - pNW.x);
          const cellH = Math.max(1, pSE.y - pNW.y);

          // Select color according to activeLayer
          if (activeLayer === "blend") {
            ctx.fillStyle = getColor(val, variable);
          } else if (activeLayer === "weights") {
            const mMeta = MODEL_COLORS[domSource] || { color: "#3B82F6" };
            // Modulate alpha by weight strength
            const alpha = Math.min(0.95, Math.max(0.2, domWeight * 1.5));
            ctx.fillStyle = mMeta.color;
            ctx.globalAlpha = alpha * layerOpacity;
          } else if (activeLayer === "confidence") {
            if (confScore >= 0.75) {
              ctx.fillStyle = "rgba(16, 185, 129, 0.75)"; // Green HIGH
            } else if (confScore >= 0.5) {
              ctx.fillStyle = "rgba(245, 158, 11, 0.80)"; // Amber MEDIUM
            } else {
              ctx.fillStyle = "rgba(239, 68, 68, 0.85)"; // Red LOW
            }
          } else if (activeLayer === "extremes") {
            if (extremeVal > 0.6) {
              ctx.fillStyle = "rgba(220, 38, 38, 0.9)";
            } else if (extremeVal > 0.3) {
              ctx.fillStyle = "rgba(249, 115, 22, 0.75)";
            } else {
              ctx.fillStyle = "rgba(234, 179, 8, 0.4)";
            }
          }

          ctx.fillRect(pNW.x, pNW.y, cellW + 0.5, cellH + 0.5);

          // Reset alpha if altered
          if (activeLayer === "weights") {
            ctx.globalAlpha = layerOpacity;
          }
        }
      }
      ctx.restore();
    }

    // 5. Draw Coastline stroke (high contrast glowing teal)
    ctx.save();
    ctx.strokeStyle = "rgba(45, 212, 191, 0.8)";
    ctx.lineWidth = 2 * Math.min(2, Math.max(1, scale));
    ctx.beginPath();
    COASTLINE_POINTS.forEach((pt, idx) => {
      const p = project(pt[0], pt[1], width, height);
      if (idx === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    });
    ctx.stroke();
    ctx.restore();

    // 6. Draw Minority Alert Signal Markers (Pulsing radar targets)
    if (gridData?.minority_alerts && gridData.minority_alerts.length > 0) {
      ctx.save();
      const timeSec = Date.now() / 1000;
      const pulseRadius = 8 + (Math.sin(timeSec * 4) + 1) * 4;

      gridData.minority_alerts.forEach((alert: any) => {
        const p = project(alert.lon, alert.lat, width, height);

        // Outer pulsing ring
        ctx.strokeStyle = "rgba(239, 68, 68, 0.8)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(p.x, p.y, pulseRadius, 0, Math.PI * 2);
        ctx.stroke();

        // Inner solid badge
        ctx.fillStyle = "#ef4444";
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx.fill();

        // Icon text tag
        ctx.font = "bold 9px sans-serif";
        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "center";
        ctx.fillText("MINORITY ALERT", p.x, p.y - 12);
      });
      ctx.restore();
    }

    // 7. Draw Landmark Cities
    ctx.save();
    CITIES.forEach((city) => {
      const p = project(city.lon, city.lat, width, height);

      // Marker dot
      ctx.fillStyle = city.capital ? "#fbbf24" : city.port ? "#38bdf8" : "#e2e8f0";
      ctx.beginPath();
      ctx.arc(p.x, p.y, city.capital ? 4.5 : 3, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = "#000000";
      ctx.lineWidth = 1;
      ctx.stroke();

      // City label
      ctx.font = city.capital ? "bold 11px sans-serif" : "10px sans-serif";
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "left";
      ctx.shadowColor = "rgba(0,0,0,0.8)";
      ctx.shadowBlur = 3;
      ctx.fillText(city.name, p.x + 6, p.y + 3);
    });
    ctx.restore();

    // 8. Draw Selected Point Reticle / Crosshairs
    if (selectedPoint) {
      const p = project(selectedPoint.lon, selectedPoint.lat, width, height);
      ctx.save();
      ctx.strokeStyle = "#f97316"; // Brand orange
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 3]);

      // Reticle Box
      const boxSize = 14;
      ctx.strokeRect(p.x - boxSize / 2, p.y - boxSize / 2, boxSize, boxSize);

      // Crosshairs
      ctx.beginPath();
      ctx.moveTo(p.x - boxSize, p.y);
      ctx.lineTo(p.x + boxSize, p.y);
      ctx.moveTo(p.x, p.y - boxSize);
      ctx.lineTo(p.x, p.y + boxSize);
      ctx.stroke();

      ctx.restore();
    }

    // 9. Domain Boundary Frame
    ctx.strokeStyle = "rgba(148, 163, 184, 0.4)";
    ctx.lineWidth = 1;
    const pMin = project(DEFAULT_DOMAIN.lon_min, DEFAULT_DOMAIN.lat_max, width, height);
    const pMax = project(DEFAULT_DOMAIN.lon_max, DEFAULT_DOMAIN.lat_min, width, height);
    ctx.strokeRect(pMin.x, pMin.y, pMax.x - pMin.x, pMax.y - pMin.y);

  }, [
    gridData,
    variable,
    activeLayer,
    layerOpacity,
    scale,
    pan,
    selectedPoint,
    project,
    getColor,
  ]);

  // Handle Resize
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current && canvasRef.current) {
        const { clientWidth, clientHeight } = containerRef.current;
        canvasRef.current.width = clientWidth;
        canvasRef.current.height = clientHeight;
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Mouse Interactions (Pan & Click)
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
      return;
    }

    // Hover detection: snap to nearest 0.25° grid
    const { lat, lon } = unproject(clientX, clientY, canvas.width, canvas.height);
    const snappedLat = Math.round(lat * 4) / 4;
    const snappedLon = Math.round(lon * 4) / 4;

    if (
      snappedLat >= DEFAULT_DOMAIN.lat_min &&
      snappedLat <= DEFAULT_DOMAIN.lat_max &&
      snappedLon >= DEFAULT_DOMAIN.lon_min &&
      snappedLon <= DEFAULT_DOMAIN.lon_max
    ) {
      let val = null;
      let domSource = undefined;
      let domWeight = undefined;
      let confLabel = undefined;
      let confScore = undefined;
      let isMinority = false;
      let minorityDetail = null;

      if (gridData?.coordinates?.lats && gridData?.coordinates?.lons) {
        const latIdx = gridData.coordinates.lats.indexOf(snappedLat);
        const lonIdx = gridData.coordinates.lons.indexOf(snappedLon);
        if (latIdx !== -1 && lonIdx !== -1) {
          val = gridData.grid?.[latIdx]?.[lonIdx];
          domSource = gridData.dominant_source?.[latIdx]?.[lonIdx];
          domWeight = gridData.dominant_weight?.[latIdx]?.[lonIdx];
          confLabel = gridData.confidence_label?.[latIdx]?.[lonIdx];
          confScore = gridData.confidence_score?.[latIdx]?.[lonIdx];
        }
      }

      if (gridData?.minority_alerts) {
        const alert = gridData.minority_alerts.find(
          (a: any) => Math.abs(a.lat - snappedLat) < 0.1 && Math.abs(a.lon - snappedLon) < 0.1
        );
        if (alert) {
          isMinority = true;
          minorityDetail = alert;
        }
      }

      setHoverInfo({
        x: clientX,
        y: clientY,
        lat: snappedLat,
        lon: snappedLon,
        val,
        domSource,
        domWeight,
        confLabel,
        confScore,
        isMinority,
        minorityDetail,
      });
    } else {
      setHoverInfo(null);
    }
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDragging) {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;
      const { lat, lon } = unproject(clientX, clientY, canvas.width, canvas.height);
      const snappedLat = Math.round(lat * 4) / 4;
      const snappedLon = Math.round(lon * 4) / 4;

      if (
        snappedLat >= DEFAULT_DOMAIN.lat_min &&
        snappedLat <= DEFAULT_DOMAIN.lat_max &&
        snappedLon >= DEFAULT_DOMAIN.lon_min &&
        snappedLon <= DEFAULT_DOMAIN.lon_max
      ) {
        setSelectedPoint({ lat: snappedLat, lon: snappedLon });
        if (onSelectPoint) onSelectPoint(snappedLat, snappedLon);
      }
    }
    setIsDragging(false);
  };

  const resetView = () => {
    setScale(1);
    setPan({ x: 0, y: 0 });
  };

  const zoomIn = () => setScale((prev) => Math.min(prev * 1.3, 4));
  const zoomOut = () => setScale((prev) => Math.max(prev / 1.3, 0.7));

  const leadSteps = [24, 48, 72, 96, 120];

  return (
    <div ref={containerRef} className="relative w-full h-full bg-[#0a0f18] overflow-hidden select-none">
      {/* Main Canvas */}
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          setIsDragging(false);
          setHoverInfo(null);
        }}
        className="cursor-crosshair w-full h-full block"
      />

      {/* Layer Switcher Glassmorphic Bar (Top Left) */}
      <div className="absolute top-4 left-4 z-20 flex flex-col gap-2">
        <div className="bg-panel/90 backdrop-blur border border-panelBorder rounded-lg p-1.5 shadow-xl flex items-center gap-1">
          <button
            onClick={() => setActiveLayer("blend")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeLayer === "blend"
                ? "bg-brandBlue text-white shadow-md font-semibold"
                : "text-gray-300 hover:text-white hover:bg-panelHover"
            }`}
          >
            <CloudRain className="w-3.5 h-3.5" />
            <span>Blended Field</span>
          </button>

          <button
            onClick={() => setActiveLayer("weights")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeLayer === "weights"
                ? "bg-brandBlue text-white shadow-md font-semibold"
                : "text-gray-300 hover:text-white hover:bg-panelHover"
            }`}
          >
            <Scale className="w-3.5 h-3.5" />
            <span>Dominant Weight</span>
          </button>

          <button
            onClick={() => setActiveLayer("confidence")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeLayer === "confidence"
                ? "bg-brandBlue text-white shadow-md font-semibold"
                : "text-gray-300 hover:text-white hover:bg-panelHover"
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            <span>Confidence Index</span>
          </button>

          <button
            onClick={() => setActiveLayer("extremes")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeLayer === "extremes"
                ? "bg-alertRed text-white shadow-md font-semibold"
                : "text-gray-300 hover:text-white hover:bg-panelHover"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Extreme Signals</span>
            {gridData?.n_minority_alerts > 0 && (
              <span className="bg-white text-alertRed font-bold text-[10px] px-1.5 py-0.2 rounded-full">
                {gridData.n_minority_alerts}
              </span>
            )}
          </button>
        </div>

        {/* Minority Alert Notification Pill */}
        {gridData?.n_minority_alerts > 0 && (
          <div className="bg-rose-950/90 border border-rose-600/80 rounded-lg px-3 py-2 text-xs text-rose-200 shadow-xl backdrop-blur flex items-center justify-between gap-3 animate-pulse">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <div>
                <span className="font-bold">{gridData.n_minority_alerts} Minority Extreme Signals Active!</span>
                <p className="text-[10px] text-rose-300">
                  Individual high-skill models forecast heavy threshold triggers suppressed by ensemble mean.
                </p>
              </div>
            </div>
            <button
              onClick={() => setActiveLayer("extremes")}
              className="px-2 py-1 rounded bg-rose-800 hover:bg-rose-700 text-white text-[10px] font-bold uppercase shrink-0"
            >
              Inspect
            </button>
          </div>
        )}
      </div>

      {/* Map Zoom / Navigation Controls (Top Right) */}
      <div className="absolute top-4 right-4 z-20 flex flex-col gap-1.5 bg-panel/90 backdrop-blur border border-panelBorder rounded-lg p-1 shadow-lg">
        <button
          onClick={zoomIn}
          title="Zoom In"
          className="p-2 rounded hover:bg-panelHover text-gray-300 hover:text-white transition-colors"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={zoomOut}
          title="Zoom Out"
          className="p-2 rounded hover:bg-panelHover text-gray-300 hover:text-white transition-colors"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={resetView}
          title="Reset Frame"
          className="p-2 rounded hover:bg-panelHover text-gray-300 hover:text-white transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Floating Dynamic Color Legend (Bottom Left) */}
      <div className="absolute bottom-16 left-4 z-20 bg-panel/90 backdrop-blur border border-panelBorder rounded-lg p-2.5 shadow-xl max-w-xs text-xs font-mono">
        <div className="flex items-center justify-between text-[11px] text-gray-300 mb-1.5 font-bold">
          <span>
            {activeLayer === "blend" && (variable === "rain24_mm" ? "24h Rainfall (mm)" : variable === "t2m_max_c" ? "Max Temp (°C)" : "Wind Speed (m/s)")}
            {activeLayer === "weights" && "Dominant Ensemble Model"}
            {activeLayer === "confidence" && "Domain Confidence Index"}
            {activeLayer === "extremes" && "Extreme Risk Level (0-1)"}
          </span>
          <span className="text-[10px] text-accentOrange">{gridData?.provenance || "CACHED"}</span>
        </div>

        {activeLayer === "blend" && (
          <div className="flex items-center gap-1">
            {((COLOR_SCALES as any)[variable] || COLOR_SCALES.rain24_mm).map((step: any, i: number) => (
              <div key={i} className="flex-1 flex flex-col items-center">
                <div className="w-full h-3 rounded-sm border border-black/40" style={{ backgroundColor: step.color }} />
                <span className="text-[9px] text-gray-400 mt-1">{step.label}</span>
              </div>
            ))}
          </div>
        )}

        {activeLayer === "weights" && (
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            {Object.entries(MODEL_COLORS).map(([id, meta]) => (
              <div key={id} className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: meta.color }} />
                <span className="text-gray-200">{meta.name}</span>
              </div>
            ))}
          </div>
        )}

        {activeLayer === "confidence" && (
          <div className="flex items-center gap-2 text-[10px]">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-emerald-500" />
              <span>HIGH (≥0.75)</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-amber-500" />
              <span>MED (0.5-0.75)</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-rose-500" />
              <span>LOW (&lt;0.5)</span>
            </div>
          </div>
        )}

        {activeLayer === "extremes" && (
          <div className="flex items-center gap-2 text-[10px]">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-rose-600" />
              <span>High Risk (&gt;0.6)</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-amber-500" />
              <span>Moderate Risk</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full border-2 border-rose-500" />
              <span>Minority Alert</span>
            </div>
          </div>
        )}
      </div>

      {/* Floating Timeline Control Bar (Bottom Center) */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 bg-panel/90 backdrop-blur border border-panelBorder rounded-xl px-4 py-2 shadow-2xl flex items-center gap-4 text-xs font-mono">
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="p-1.5 rounded-lg bg-brandBlue hover:bg-blue-600 text-white transition-colors"
          title={isPlaying ? "Pause Timeline" : "Play Timeline"}
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </button>

        <div className="flex items-center gap-1.5">
          {leadSteps.map((step) => (
            <button
              key={step}
              onClick={() => setLead(step)}
              className={`px-2.5 py-1 rounded-md text-xs font-bold transition-all ${
                lead === step
                  ? "bg-accentOrange text-white shadow-md scale-105"
                  : "bg-background/80 text-gray-300 hover:text-white hover:bg-panelBorder"
              }`}
            >
              +{step}h
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-panelBorder mx-1" />

        <div className="text-[11px] text-gray-400 flex items-center gap-1.5">
          <span>CYCLE:</span>
          <span className="font-bold text-white">{cycle} 03:00 UTC</span>
        </div>
      </div>

      {/* Interactive Hover HUD Tooltip */}
      {hoverInfo && (
        <div
          className="absolute z-30 pointer-events-none bg-panel/95 border border-panelBorder rounded-lg p-2.5 shadow-2xl text-xs font-mono text-gray-200 transform -translate-x-1/2 -translate-y-full mb-3"
          style={{ left: hoverInfo.x, top: hoverInfo.y }}
        >
          <div className="flex items-center justify-between gap-4 font-bold border-b border-panelBorder/60 pb-1 mb-1.5 text-[11px]">
            <span className="text-white">
              {hoverInfo.lat.toFixed(2)}°N, {hoverInfo.lon.toFixed(2)}°E
            </span>
            <span className="text-accentOrange">
              {hoverInfo.val !== null ? `${hoverInfo.val.toFixed(1)} ${variable === "rain24_mm" ? "mm" : "units"}` : "--"}
            </span>
          </div>

          <div className="space-y-1 text-[10px]">
            {hoverInfo.domSource && (
              <div className="flex items-center justify-between gap-3">
                <span className="text-gray-400">Dominant:</span>
                <span className="font-semibold text-white">
                  {MODEL_COLORS[hoverInfo.domSource]?.name || hoverInfo.domSource} (
                  {hoverInfo.domWeight ? (hoverInfo.domWeight * 100).toFixed(0) : "--"}%)
                </span>
              </div>
            )}

            {hoverInfo.confLabel && (
              <div className="flex items-center justify-between gap-3">
                <span className="text-gray-400">Confidence:</span>
                <span
                  className={`font-semibold ${
                    hoverInfo.confLabel === "HIGH"
                      ? "text-emerald-400"
                      : hoverInfo.confLabel === "MEDIUM"
                      ? "text-amber-400"
                      : "text-rose-400"
                  }`}
                >
                  {hoverInfo.confLabel} ({hoverInfo.confScore ? (hoverInfo.confScore * 100).toFixed(0) : "--"}%)
                </span>
              </div>
            )}

            {hoverInfo.isMinority && (
              <div className="bg-rose-950 text-rose-300 px-1.5 py-0.5 rounded text-[9px] font-bold mt-1">
                MINORITY ALARM: {hoverInfo.minorityDetail?.source_id} predicts {hoverInfo.minorityDetail?.model_value?.toFixed(1)}mm
              </div>
            )}
          </div>
        </div>
      )}

      {/* Loading & Error Overlays */}
      {loading && (
        <div className="absolute inset-0 bg-background/50 backdrop-blur-xs flex items-center justify-center z-40">
          <div className="bg-panel border border-panelBorder rounded-xl p-4 shadow-2xl flex items-center gap-3 text-xs font-mono text-gray-200">
            <div className="w-4 h-4 border-2 border-brandBlue border-t-transparent rounded-full animate-spin" />
            <span>Computing Adaptive Multi-Model Blend ({method})...</span>
          </div>
        </div>
      )}

      {error && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-40 bg-alertRed/90 text-white text-xs font-mono px-4 py-2 rounded-lg shadow-xl flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
