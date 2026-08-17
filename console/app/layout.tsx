import type { Metadata } from 'next';
import { Instrument_Serif, IBM_Plex_Sans, IBM_Plex_Mono } from 'next/font/google';
import './globals.css';

/* Instrument Serif is not an idle choice: the product's own argument is that
   exposing the weights "converts the engine from an oracle into an instrument."
   Paired with IBM Plex for the technical register and tabular figures. */
const display = Instrument_Serif({
  weight: '400',
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
});

const body = IBM_Plex_Sans({
  weight: ['400', '500', '600'],
  subsets: ['latin'],
  variable: '--font-body',
  display: 'swap',
});

const mono = IBM_Plex_Mono({
  weight: ['400', '500'],
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
