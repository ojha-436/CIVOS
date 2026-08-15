import type { NextConfig } from 'next';

// BACKEND_URL is a server-only env var — never NEXT_PUBLIC_ — so it is read
// at runtime by the standalone server, not baked into the client bundle.
// Locally: http://localhost:8000  |  Cloud Run: set via --set-env-vars
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
