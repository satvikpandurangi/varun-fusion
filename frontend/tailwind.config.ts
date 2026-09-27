import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0B1020",
        panel: "#121A2B",
        panelHover: "#18233A",
        panelBorder: "rgba(255, 255, 255, 0.08)",
        accentOrange: "#F28C28",
        navyDark: "#1F3864",
        brandBlue: "#0070C0",
        // Fixed model colors
        modelIfs: "#3B82F6",
        modelGfs: "#06B6D4",
        modelNcmrwf: "#38BDF8",
        modelAifs: "#A855F7",
        // Operational alert colors
        alertGreen: "#10B981",
        alertYellow: "#F59E0B",
        alertOrange: "#F97316",
        alertRed: "#EF4444",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "Courier New", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
