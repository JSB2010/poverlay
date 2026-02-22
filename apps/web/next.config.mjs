/** @type {import('next').NextConfig} */
// Applies only when Next.js itself proxies /api requests.
const proxyClientMaxBodySize = process.env.NEXT_PROXY_CLIENT_MAX_BODY_SIZE || "64gb";

const nextConfig = {
  output: "standalone",

  // Performance optimizations
  compress: true,
  poweredByHeader: false,

  experimental: {
    proxyClientMaxBodySize,
  },

  // Image optimization
  images: {
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
  },

  // Security headers
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on'
          },
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN'
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff'
          },
          {
            key: 'Referrer-Policy',
            value: 'origin-when-cross-origin'
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()'
          }
        ]
      }
    ];
  },

  async rewrites() {
    const apiTarget = process.env.API_PROXY_TARGET || "http://127.0.0.1:8787";
    return [
      {
        source: "/api/:path*",
        destination: `${apiTarget}/api/:path*`
      }
    ];
  }
};

export default nextConfig;
