/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
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
