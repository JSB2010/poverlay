import type { Metadata } from "next";
import { Inter, Sora } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import { Navbar } from "@/components/navbar";
import { PUBLIC_WEB_CONFIG } from "@/lib/public-config";
import "./globals.css";

const display = Sora({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["600", "700", "800"],
});

const body = Inter({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  metadataBase: new URL(PUBLIC_WEB_CONFIG.siteUrl),
  title: {
    default: "POVerlay — GoPro Telemetry Overlay Studio",
    template: "%s | POVerlay"
  },
  description: "Professional GoPro telemetry overlay rendering platform. Upload GPX tracks and GoPro clips to create stunning overlays with real-time speed, altitude, maps, and telemetry data. Free online tool for action sports video editing.",
  keywords: [
    "GoPro overlay",
    "telemetry overlay",
    "GPX overlay",
    "GoPro telemetry",
    "action camera overlay",
    "video telemetry",
    "GoPro dashboard",
    "GPS overlay",
    "speed overlay",
    "cycling overlay",
    "skiing overlay",
    "mountain biking overlay",
    "action sports video",
    "GoPro editing",
    "telemetry data visualization"
  ],
  authors: [{ name: "POVerlay Team" }],
  creator: "POVerlay",
  publisher: "POVerlay",
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "/",
    title: "POVerlay — GoPro Telemetry Overlay Studio",
    description: "Professional GoPro telemetry overlay rendering platform. Upload GPX tracks and GoPro clips to create stunning overlays with real-time speed, altitude, maps, and telemetry data.",
    siteName: "POVerlay",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "POVerlay - GoPro Telemetry Overlay Studio"
      }
    ]
  },
  twitter: {
    card: "summary_large_image",
    title: "POVerlay — GoPro Telemetry Overlay Studio",
    description: "Professional GoPro telemetry overlay rendering platform. Create stunning overlays with real-time speed, altitude, maps, and telemetry data.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  icons: {
    icon: [
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
    ],
    apple: [
      { url: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
    ],
    other: [
      {
        rel: 'mask-icon',
        url: '/logo.png',
      },
    ],
  },
  manifest: '/site.webmanifest',
  alternates: {
    canonical: '/',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: 'POVerlay',
    applicationCategory: 'MultimediaApplication',
    operatingSystem: 'Web Browser',
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
    },
    description: 'Professional GoPro telemetry overlay rendering platform. Upload GPX tracks and GoPro clips to create stunning overlays with real-time speed, altitude, maps, and telemetry data.',
    url: PUBLIC_WEB_CONFIG.siteUrl,
    image: '/logo.png',
    featureList: [
      'GoPro telemetry overlay rendering',
      'GPX track synchronization',
      'Professional overlay themes',
      'Multiple layout styles',
      'Batch video rendering',
      'Real-time telemetry display',
      'Interactive map integration',
    ],
    browserRequirements: 'Requires JavaScript. Requires HTML5.',
  };

  return (
    <html lang="en" className={`${display.variable} ${body.variable}`} suppressHydrationWarning>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <script src="https://jacobbarkin.com/embed/credit.js" async />
      </head>
      <body>
        <ThemeProvider>
          <Navbar />
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
