import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/Header";

export const metadata: Metadata = {
  title: "VARUN-FUSION | Adaptive AI–NWP Multi-Model Forecast Blending System",
  description:
    "Production prototype for Smart India Hackathon 2026, Problem Statement 26081 (Ministry of Earth Sciences, Team CodeX_2026, ID 159951). Real-time forecast harmonization, rolling skill evaluation, and adaptive ML blending for India.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0a0f18] text-gray-100 min-h-screen flex flex-col font-sans antialiased overflow-x-hidden">
        <Header />
        <main className="flex-1 flex flex-col min-h-0 relative">
          {children}
        </main>
      </body>
    </html>
  );
}
