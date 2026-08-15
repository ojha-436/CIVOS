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
  title: 'CIVOS-IN — citizen-signal infrastructure prioritisation',
  description:
    'Aggregates citizen development requests by voice, text and photograph, corrects for participation bias, and emits budget-ready project dossiers tied to real funding schemes.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
