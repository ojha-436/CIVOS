'use client';

/* One theme mechanism for all three surfaces — landing, console, intake.
 *
 * The source of truth is the `data-theme` attribute on <html>, written before
 * first paint by the blocking script in app/layout.tsx. CSS reads it directly;
 * this module exists for the parts that CSS cannot reach.
 *
 * The console is the reason it has to be observable rather than just readable.
 * Its choropleth is painted imperatively — 594 colours computed in JS and pushed
 * into MapLibre feature-state — so when the theme changes, JS has to recompute.
 * A MutationObserver on the attribute means the toggle stays a one-liner and no
 * page needs to thread a callback down to the map.
 */

import { useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';

export const THEME_KEY = 'civos-theme';

/** Dark is the base: anything other than an explicit 'light' is dark. */
export function readTheme(): Theme {
  if (typeof document === 'undefined') return 'dark';
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}

export function toggleTheme(): Theme {
  const next: Theme = readTheme() === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    /* Safari private browsing throws on write. The theme still applies to this
       page view; it just will not be remembered. Not worth failing over. */
  }
  return next;
}

/**
 * Current theme, re-rendering on change.
 *
 * Starts at 'dark' rather than reading the DOM during render, so the first
 * client render matches the server's. The correction lands in an effect on
 * mount. That is safe here because nothing theme-derived reaches server-rendered
 * markup — the console's ramped colours go into MapLibre feature-state, and the
 * map is not constructed until after data has loaded.
 */
export function useTheme(): Theme {
  const [theme, setTheme] = useState<Theme>('dark');

  useEffect(() => {
    setTheme(readTheme());
    const obs = new MutationObserver(() => setTheme(readTheme()));
    obs.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });
    return () => obs.disconnect();
  }, []);

  return theme;
}

/* ---------------------------------------------------------------------------
   Map ground colours
   ---------------------------------------------------------------------------
   lib/scoring.rampColour mixes each quadrant hue toward the map ground so the
   bottom of the distribution recedes and the top burns through. That argument is
   ground-relative, not dark-specific — it works identically on paper, just
   toward a different colour. These are the two grounds.
   ------------------------------------------------------------------------- */

export const MAP_GROUND: Record<Theme, [number, number, number]> = {
  dark: [13, 18, 25],
  light: [238, 232, 219],
};

/* ---------------------------------------------------------------------------
   Quadrant hues per theme
   ---------------------------------------------------------------------------
   NOT an inversion. --q-silent #f3c14b measures ~1.6:1 on a cream ground, so
   reusing the dark hues on paper would make the single most important signal in
   the product invisible. The light set is re-picked to clear WCAG AA against the
   light ground, and mirrors the CSS tokens in globals.css exactly — the map and
   the legend beside it must not disagree about what "Silent Need" looks like.
   ------------------------------------------------------------------------- */

export const QUADRANT_HEX_BY_THEME: Record<Theme, Record<string, string>> = {
  dark: {
    act_now: '#ff6a45',
    silent_need: '#f3c14b',
    expectation_gap: '#57c4e5',
    stable: '#4a5566',
    no_data: '#1b212b',
  },
  light: {
    act_now: '#b83a17',
    silent_need: '#8a6410',
    expectation_gap: '#10647d',
    stable: '#7c8694',
    /* Cool grey, NOT the warm beige this first was. Ochre mixed toward a warm
       paper ground lands within a few percent of warm beige, so Silent Need and
       "no official data" became hard to tell apart on the map — and Silent Need
       is the one mark that must never be ambiguous. Pulling the absence-of-data
       neutral to the cool side of the wheel separates them by hue rather than by
       lightness alone, which also survives most colour-vision deficiencies. */
    no_data: '#d5d8dc',
  },
};

/** Basemap-layer colours. The map has no tile provider — it is our own GeoJSON
 *  on a flat ground — so a theme change is a handful of setPaintProperty calls
 *  rather than a full setStyle, which would discard all 594 feature-states. */
export const MAP_CHROME: Record<
  Theme,
  { bg: string; ink: string; outlineOpacity: number; empty: string; selected: string; pok: string }
> = {
  dark: {
    bg: '#070a0e',
    ink: '#ece5d8',
    outlineOpacity: 0.13,
    empty: '#0c1017',
    selected: '#f3c14b',
    pok: '#1b212b',
  },
  light: {
    bg: '#eee8db',
    ink: '#16202b',
    // A hairline that reads at 0.13 alpha on near-black needs more weight on
    // paper, where the eye has less contrast headroom to work with.
    outlineOpacity: 0.22,
    // Matches QUADRANT_HEX_BY_THEME.light.no_data — an unscored district and a
    // filtered-out district must not read as two different states.
    empty: '#d5d8dc',
    selected: '#8a6410',
    pok: '#d5d8dc',
  },
};
