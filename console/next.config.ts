import type { NextConfig } from 'next';

// Routing: /api/* is handled by app/api/[...proxy]/route.ts at runtime,
// which reads BACKEND_URL from the environment on every request.
// No rewrites needed — and no bake-time URL leaking into the build artifact.

const nextConfig: NextConfig = {
  output: 'standalone',
};

export default nextConfig;
