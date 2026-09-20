import type { NextConfig } from 'next';

// Routing: /api/* is handled by app/api/[...proxy]/route.ts at runtime,
// which reads BACKEND_URL from the environment on every request.
// No rewrites needed — and no bake-time URL leaking into the build artifact.

const nextConfig: NextConfig = {
  output: 'standalone',

  /* Cross-Origin-Opener-Policy: same-origin-allow-popups
   *
   * This is what makes "Continue with Google" work.
   *
   * signInWithPopup opens accounts.google.com, which sets its own COOP. That
   * severs the opener relationship, and Chrome then refuses the window.closed
   * and window.close calls Firebase uses to track the popup — visible in the
   * console as four "Cross-Origin-Opener-Policy policy would block the
   * window.closed call" errors per attempt. The SDK is left unable to tell a
   * completed sign-in from an abandoned one.
   *
   * `same-origin-allow-popups` is the narrowest header that fixes it: this
   * document keeps its opener handle on popups it opened itself, while still
   * being isolated from any document that tries to open IT. We were sending no
   * COOP at all, which sounds more permissive but is not — without an explicit
   * value the popup's own policy wins.
   *
   * Applied site-wide rather than to /login alone: the same popup flow is
   * reachable from any page that offers sign-in, and a header that protects one
   * route and not its siblings is a trap for whoever adds the next route.
   */
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Cross-Origin-Opener-Policy', value: 'same-origin-allow-popups' },
        ],
      },
    ];
  },
};

export default nextConfig;
