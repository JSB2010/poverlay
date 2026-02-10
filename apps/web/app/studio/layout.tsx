import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Studio",
  description: "Professional GoPro telemetry overlay studio. Upload your GPX track and GoPro clips, customize themes and layouts, and render stunning overlays with real-time telemetry data.",
  openGraph: {
    title: "POVerlay Studio — GoPro Telemetry Overlay Studio",
    description: "Upload your GPX track and GoPro clips, customize themes and layouts, and render stunning overlays with real-time telemetry data.",
  },
};

export default function StudioLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}

