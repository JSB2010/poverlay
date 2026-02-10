import Link from "next/link";
import {
  ArrowRight,
  Upload,
  Palette,
  LayoutGrid,
  Film,
  Gauge,
  Map,
  Zap,
} from "lucide-react";
import { FAQSchema } from "./faq-schema";

const FEATURES = [
  { icon: Upload, title: "Drag & Drop Upload", description: "Upload your GPX track and GoPro clips with a simple drag-and-drop interface. Supports multiple clips for batch rendering." },
  { icon: Palette, title: "Professional Themes", description: "Choose from six handcrafted color themes designed for maximum readability and visual impact on action footage." },
  { icon: LayoutGrid, title: "Layout Styles", description: "Seven unique overlay layouts — from cinematic lower-thirds to full race dashboards — each optimized for different content." },
  { icon: Film, title: "Batch Rendering", description: "Render multiple clips in a single job. Each video gets its own overlay with synchronized GPX telemetry data." },
  { icon: Gauge, title: "Live Telemetry", description: "Display speed, altitude, grade, distance, GPS coordinates, and route maps — all synced to your ride data." },
  { icon: Map, title: "Interactive Maps", description: "Embed moving maps and journey overview maps directly into your overlay with multiple cartographic styles." },
];

export default function LandingPage() {
  return (
    <>
      <FAQSchema />
      <main className="min-h-[calc(100dvh-3.5rem)]">
        {/* Hero */}
        <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10">
          <div className="absolute left-1/4 top-0 h-[500px] w-[500px] rounded-full bg-[var(--color-primary)]/10 blur-[120px]" />
          <div className="absolute bottom-0 right-1/4 h-[400px] w-[400px] rounded-full bg-[var(--color-ring)]/8 blur-[100px]" />
        </div>

        <div className="mx-auto max-w-5xl px-4 pb-20 pt-24 text-center sm:px-6 sm:pt-32 md:pt-40">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-card)]/60 px-4 py-1.5 text-sm font-medium text-[var(--color-muted-foreground)] backdrop-blur-sm">
            <Zap className="h-3.5 w-3.5 text-[var(--color-primary)]" />
            Professional GoPro telemetry overlays
          </div>

          <h1 className="mx-auto max-w-3xl font-[family-name:var(--font-display)] text-4xl font-extrabold tracking-tight sm:text-5xl md:text-6xl">
            Transform your GoPro footage with{" "}
            <span className="bg-gradient-to-r from-[var(--color-primary)] to-sky-400 bg-clip-text text-transparent">
              stunning overlays
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-[var(--color-muted-foreground)] sm:text-xl">
            Upload your GPX track and GoPro clips, choose from professional themes and layouts,
            and render polished telemetry overlays in minutes.
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="/studio"
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--color-primary)] px-7 py-3 text-base font-semibold text-white shadow-lg shadow-[var(--color-primary)]/25 no-underline transition-all hover:-translate-y-0.5 hover:shadow-xl hover:shadow-[var(--color-primary)]/30"
            >
              Open Studio
              <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href="#features"
              className="inline-flex items-center gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]/60 px-7 py-3 text-base font-medium no-underline backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:bg-[var(--color-card)]"
            >
              Learn more
            </a>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="border-t border-[var(--color-border)]/60 bg-[var(--color-muted)]/30 py-20 sm:py-28">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="mb-14 text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Everything you need</h2>
            <p className="mt-3 text-lg text-[var(--color-muted-foreground)]">
              A complete pipeline from raw footage to polished, overlay-enhanced videos.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="group rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 transition-all hover:-translate-y-0.5 hover:border-[var(--color-primary)]/30 hover:shadow-lg"
              >
                <div className="mb-4 inline-flex rounded-xl bg-[var(--color-primary)]/10 p-3 text-[var(--color-primary)]">
                  <f.icon className="h-5 w-5" />
                </div>
                <h3 className="mb-2 text-base font-semibold">{f.title}</h3>
                <p className="text-sm leading-relaxed text-[var(--color-muted-foreground)]">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="border-t border-[var(--color-border)]/60 bg-[var(--color-muted)]/20 py-20 sm:py-28">
        <div className="mx-auto max-w-4xl px-4 sm:px-6">
          <div className="mb-14 text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Frequently Asked Questions</h2>
            <p className="mt-3 text-lg text-[var(--color-muted-foreground)]">
              Everything you need to know about POVerlay
            </p>
          </div>

          <div className="space-y-6">
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
              <h3 className="mb-2 text-lg font-semibold">What is POVerlay?</h3>
              <p className="text-[var(--color-muted-foreground)]">
                POVerlay is a professional GoPro telemetry overlay platform that lets you upload GPX tracks and GoPro clips to create stunning video overlays with real-time speed, altitude, maps, and telemetry data. Perfect for skiing, cycling, mountain biking, and all action sports.
              </p>
            </div>

            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
              <h3 className="mb-2 text-lg font-semibold">What file formats are supported?</h3>
              <p className="text-[var(--color-muted-foreground)]">
                POVerlay supports GPX files for GPS tracks and MP4 video files from GoPro cameras. The platform automatically synchronizes your GPS data with your video footage for accurate telemetry overlays.
              </p>
            </div>

            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
              <h3 className="mb-2 text-lg font-semibold">Can I customize the overlay appearance?</h3>
              <p className="text-[var(--color-muted-foreground)]">
                Yes! POVerlay offers six professional color themes and seven unique layout styles. You can customize which telemetry data to display, choose map styles, and adjust the overall look to match your content perfectly.
              </p>
            </div>

            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
              <h3 className="mb-2 text-lg font-semibold">How long does rendering take?</h3>
              <p className="text-[var(--color-muted-foreground)]">
                Rendering time depends on video length and quality settings. Most videos render in real-time or faster. You can monitor progress in the studio and download your videos when complete.
              </p>
            </div>

            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
              <h3 className="mb-2 text-lg font-semibold">Is POVerlay free to use?</h3>
              <p className="text-[var(--color-muted-foreground)]">
                Yes! POVerlay is a free online tool for creating professional GoPro telemetry overlays. Simply upload your files and start rendering.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[var(--color-border)]/60 py-20 sm:py-28">
        <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Ready to get started?</h2>
          <p className="mt-4 text-lg text-[var(--color-muted-foreground)]">
            Open the studio, upload your files, and render your first overlay in minutes.
          </p>
          <Link
            href="/studio"
            className="mt-8 inline-flex items-center gap-2 rounded-xl bg-[var(--color-primary)] px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-[var(--color-primary)]/25 no-underline transition-all hover:-translate-y-0.5 hover:shadow-xl hover:shadow-[var(--color-primary)]/30"
          >
            Open Studio
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

        {/* Footer */}
        <footer className="border-t border-[var(--color-border)]/60 py-8">
          <div className="mx-auto flex max-w-6xl items-center justify-center px-4 sm:px-6">
            <jb-credit data-variant="prominent"></jb-credit>
          </div>
        </footer>
      </main>
    </>
  );
}
