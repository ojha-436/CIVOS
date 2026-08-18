import type { Metadata } from 'next';
import localFont from 'next/font/local';
import { AuthProvider } from '@/lib/auth';
import './globals.css';

/* Typefaces are vendored under app/fonts/ rather than fetched by
   next/font/google at build time.
 *
 * That was not a style preference. On 2026-08-17 a Cloud Build deploy failed
 * because Google Fonts rotated the IBM Plex Sans file hashes: the CSS it served
 * still referenced woff2 URLs that had begun returning 404, so `next build`
 * died with 18 module-not-found errors. Local builds kept passing only because
 * .next/ still held the previously downloaded files — the failure was invisible
 * until it reached CI.
 *
 * Self-hosting removes a live network dependency from the build entirely, which
 * a system that claims to be a Digital Public Good ought not to have had: a
 * ministry building this on a restricted or air-gapped network could never have
 * compiled it. Builds are now reproducible and offline-capable.
 *
 * All three families are SIL OFL 1.1, which permits redistribution.
 * Provenance and licence: docs/FONT-ATTRIBUTION.md
 *
 * Instrument Serif is not an idle choice: the product's own argument is that
 * exposing the weights "converts the engine from an oracle into an instrument."
 * Paired with IBM Plex for the technical register and tabular figures. */

const display = localFont({
  src: [{ path: './fonts/InstrumentSerif-Regular.woff2', weight: '400', style: 'normal' }],
  variable: '--font-display',
  display: 'swap',
  // Georgia is the fallback in globals.css; matching its metrics here keeps the
  // swap from shifting the very large hero headline.
  fallback: ['Georgia', 'serif'],
  adjustFontFallback: 'Times New Roman',
});

const body = localFont({
  src: [
    { path: './fonts/IBMPlexSans-Regular.woff2', weight: '400', style: 'normal' },
    { path: './fonts/IBMPlexSans-Medium.woff2', weight: '500', style: 'normal' },
    { path: './fonts/IBMPlexSans-SemiBold.woff2', weight: '600', style: 'normal' },
  ],
  variable: '--font-body',
  display: 'swap',
  fallback: ['ui-sans-serif', 'system-ui', 'sans-serif'],
  adjustFontFallback: 'Arial',
});

const mono = localFont({
  src: [
    { path: './fonts/IBMPlexMono-Regular.woff2', weight: '400', style: 'normal' },
    { path: './fonts/IBMPlexMono-Medium.woff2', weight: '500', style: 'normal' },
  ],
  variable: '--font-mono',
  display: 'swap',
  fallback: ['ui-monospace', 'monospace'],
});

export const metadata: Metadata = {
  title: {
    default: 'CIVOS — the civic operating system',
    template: '%s · CIVOS-IN',
  },
  description:
    'Citizens report what their area needs by voice, text or photograph, in any language. CIVOS merges duplicates into distinct needs, corrects for the fact that the poorest districts complain the least, and emits a costed project dossier tied to a real government funding scheme.',
  openGraph: {
    title: 'CIVOS — the civic operating system',
    description:
      'A map of complaints is a map of who owns a phone. CIVOS finds the districts with the worst conditions and no voice.',
    type: 'website',
  },
};

/* Applies the stored theme before first paint.
 *
 * This has to be a blocking inline script rather than an effect: setting the
 * attribute after hydration means the page paints dark, then snaps to light,
 * which is worse than having no toggle at all for anyone light-sensitive.
 *
 * Dark is the base — the absence of an attribute means dark — so this only ever
 * writes an override. prefers-color-scheme is deliberately NOT consulted: most
 * browsers report `light` when the user has expressed no preference at all, so
 * honouring it would flip the majority of visitors away from the intended
 * design on the strength of a non-preference. Light is an explicit choice here,
 * and it persists once made.
 *
 * Wrapped in try/catch because localStorage throws outright in Safari private
 * browsing, and a theme preference is not worth taking the page down for. */
const THEME_INIT = `(function(){try{var t=localStorage.getItem('civos-theme');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t)}}catch(e){}})()`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    /* suppressHydrationWarning is required, not cosmetic. THEME_INIT writes
       data-theme onto this element before React hydrates, so the client tree
       legitimately differs from the server tree by exactly that attribute.
       React's default response is to warn on every load — noise that would
       mask a real mismatch later. It suppresses one level only, which is
       precisely the <html> attributes and nothing inside. */
    <html
      lang="en"
      className={`${display.variable} ${body.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
