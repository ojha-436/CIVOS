'use client';

import { useEffect, useRef, useState } from 'react';
import maplibregl, { Map as MLMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { QuadrantKey } from '@/lib/types';
import { MAP_CHROME, readTheme, type Theme } from '@/lib/theme';

/* No basemap, deliberately.
 *
 * Three reasons, in order of weight: a tile provider means an API key and a
 * billing surface for something the design does not use; the districts ARE the
 * subject, so roads and labels underneath them are noise; and with no external
 * tile request the console renders identically offline, which matters when the
 * demo is being filmed. What is drawn is our own simplified boundary GeoJSON on
 * an unlit ground. */

export interface MapDatum {
  /** Final fill, already ramped by priority in lib/scoring.rampColour */
  colour: string;
  q: QuadrantKey;
  visible: boolean;
}

interface Props {
  data: Map<string, MapDatum>;
  selected: string | null;
  onHover: (code: string | null) => void;
  onSelect: (code: string) => void;
  onReady: () => void;
  theme?: Theme;
}

export default function ChoroplethMap({
  data,
  selected,
  onHover,
  onSelect,
  onReady,
  theme,
}: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const loaded = useRef(false);
  const hovered = useRef<string | null>(null);
  /* Bumped once the style is ready. The theme effect below reads `loaded` and
     would otherwise bail out and never re-run if a theme change (or the parent's
     first post-mount theme correction) landed before `load` fired. */
  const [styleReady, setStyleReady] = useState(0);

  // -- init ---------------------------------------------------------------
  useEffect(() => {
    if (!holder.current || map.current) return;

    /* Read the theme directly here rather than using the prop. The map is built
       once, in a mount effect, and the parent's useTheme() has not corrected
       from its SSR-safe 'dark' default yet at that moment — building with the
       prop would construct a dark map and repaint it a frame later. */
    const c0 = MAP_CHROME[readTheme()];

    const m = new maplibregl.Map({
      container: holder.current,
      style: {
        // No `glyphs` key at all — MapLibre's style validator rejects an explicit
        // `undefined` and throws before a single layer is drawn. There are no
        // symbol layers here, so glyphs are genuinely not needed.
        version: 8,
        sources: {
          districts: {
            type: 'geojson',
            data: '/data/districts.geojson',
            promoteId: 'code',
          },
          pok: {
            type: 'geojson',
            data: '/data/pok-boundary.geojson',
          },
        },
        layers: [
          { id: 'bg', type: 'background', paint: { 'background-color': c0.bg } },
          {
            // POK fill — same neutral as no-data districts, indicating the area
            // is part of India per official Survey of India boundary but
            // district-level administration data is not available.
            id: 'pok-fill',
            type: 'fill',
            source: 'pok',
            paint: { 'fill-color': c0.pok, 'fill-opacity': 0.85 },
          },
          {
            // POK border — thin dashed-looking line marking the official claim
            id: 'pok-outline',
            type: 'line',
            source: 'pok',
            paint: {
              'line-color': c0.ink,
              'line-width': 0.8,
              'line-opacity': 0.4,
              'line-dasharray': [3, 3],
            },
          },
          {
            id: 'fill',
            type: 'fill',
            source: 'districts',
            paint: {
              'fill-color': [
                'case',
                ['==', ['feature-state', 'visible'], false],
                c0.empty,
                ['coalesce', ['feature-state', 'colour'], c0.empty],
              ],
              'fill-opacity': [
                'case',
                ['==', ['feature-state', 'visible'], false],
                0.5,
                0.95,
              ],
            },
          },
          {
            id: 'outline',
            type: 'line',
            source: 'districts',
            paint: {
              'line-color': c0.ink,
              'line-width': 0.4,
              'line-opacity': c0.outlineOpacity,
            },
          },
          {
            id: 'hover',
            type: 'line',
            source: 'districts',
            filter: ['==', ['get', 'code'], ''],
            paint: { 'line-color': c0.ink, 'line-width': 1.4, 'line-opacity': 0.9 },
          },
          {
            id: 'selected',
            type: 'line',
            source: 'districts',
            filter: ['==', ['get', 'code'], ''],
            paint: { 'line-color': c0.selected, 'line-width': 2.2 },
          },
        ],
      },
      // Centre of official India (incl. J&K+POK). fitBounds on load overrides
      // this, but having the right initial value prevents a flash of wrong framing.
      center: [82.5, 22.0],
      zoom: 3.8,
      minZoom: 3,
      maxZoom: 9,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
    });

    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');

    m.on('load', () => {
      loaded.current = true;
      setStyleReady((t) => t + 1);

      // Official Survey of India bounds — includes:
      //   West : 68.0°E  (Gujarat / Rajasthan)
      //   East : 97.5°E  (Arunachal Pradesh)
      //   South:  6.5°N  (Kanyakumari + Andaman & Nicobar)
      //   North: 37.6°N  (J&K including Pakistan-Occupied Kashmir —
      //                   official Indian government position per Survey of India)
      // querySourceFeatures only sees viewport tiles, so centroid-based fitting
      // produces wrong bounds when the initial viewport is partial. Hardcoded
      // bounds are reliable, unambiguous, and match the constitutional claim.
      m.fitBounds(
        new maplibregl.LngLatBounds([68.0, 6.5], [97.5, 37.6]),
        { padding: { top: 40, right: 40, bottom: 100, left: 60 }, duration: 0 },
      );

      onReady();
    });

    m.on('mousemove', 'fill', (e) => {
      const f = e.features?.[0];
      const code = (f?.properties?.code as string) ?? null;
      if (code !== hovered.current) {
        hovered.current = code;
        m.setFilter('hover', ['==', ['get', 'code'], code ?? '']);
        m.getCanvas().style.cursor = code ? 'pointer' : '';
        onHover(code);
      }
    });

    m.on('mouseleave', 'fill', () => {
      hovered.current = null;
      m.setFilter('hover', ['==', ['get', 'code'], '']);
      m.getCanvas().style.cursor = '';
      onHover(null);
    });

    m.on('click', 'fill', (e) => {
      const code = e.features?.[0]?.properties?.code as string | undefined;
      if (code) onSelect(code);
    });

    // MapLibre measures its container once, at construction. Inside a CSS grid
    // that has not finished laying out, that measurement is wrong — the canvas
    // came out 1016×300 instead of filling the stage. Observing the container
    // and resizing is the fix, and it also covers window resize for free.
    const ro = new ResizeObserver(() => m.resize());
    ro.observe(holder.current);

    map.current = m;
    return () => {
      ro.disconnect();
      m.remove();
      map.current = null;
      loaded.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -- paint via feature-state -------------------------------------------
  // Repainting through feature-state rather than rebuilding the style keeps the
  // weight sliders responsive: 594 state writes per frame is cheap, recompiling
  // a 594-branch match expression is not.
  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const apply = () => {
      data.forEach((d, code) => {
        m.setFeatureState(
          { source: 'districts', id: code },
          { colour: d.colour, visible: d.visible },
        );
      });
    };

    // `load` fires when the STYLE is ready, which can be before the GeoJSON has
    // arrived — and setFeatureState on a feature that does not exist yet is
    // silently discarded, leaving an unpainted map with no error. So wait for the
    // source itself, then keep applying until it reports loaded.
    if (loaded.current && m.isSourceLoaded('districts')) {
      apply();
      return;
    }
    const onData = (e: maplibregl.MapSourceDataEvent) => {
      if (e.sourceId === 'districts' && m.isSourceLoaded('districts')) {
        apply();
        m.off('sourcedata', onData);
      }
    };
    m.on('sourcedata', onData);
    return () => {
      m.off('sourcedata', onData);
    };
  }, [data]);

  // -- theme -----------------------------------------------------------------
  // Repainted layer by layer rather than with setStyle(). setStyle would rebuild
  // the sources and discard every feature-state with them, so all 594 district
  // fills would go blank until the next data pass rewrote them. Six
  // setPaintProperty calls are also just cheaper.
  useEffect(() => {
    const m = map.current;
    if (!m || !loaded.current || !theme) return;
    const c = MAP_CHROME[theme];

    m.setPaintProperty('bg', 'background-color', c.bg);
    m.setPaintProperty('pok-fill', 'fill-color', c.pok);
    m.setPaintProperty('pok-outline', 'line-color', c.ink);
    m.setPaintProperty('outline', 'line-color', c.ink);
    m.setPaintProperty('outline', 'line-opacity', c.outlineOpacity);
    m.setPaintProperty('hover', 'line-color', c.ink);
    m.setPaintProperty('selected', 'line-color', c.selected);
    m.setPaintProperty('fill', 'fill-color', [
      'case',
      ['==', ['feature-state', 'visible'], false],
      c.empty,
      ['coalesce', ['feature-state', 'colour'], c.empty],
    ]);
  }, [theme, styleReady]);

  // -- selection ring ------------------------------------------------------
  useEffect(() => {
    const m = map.current;
    if (!m || !loaded.current) return;
    m.setFilter('selected', ['==', ['get', 'code'], selected ?? '']);
  }, [selected]);

  return <div ref={holder} className="map" />;
}
