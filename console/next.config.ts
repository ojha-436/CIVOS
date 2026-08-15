import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  // API rewrites: when deployed, the console hits the Cloud Run API service.
  // Locally, it hits localhost:8000. The env var overrides the default.
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
