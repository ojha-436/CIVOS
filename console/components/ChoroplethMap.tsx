'use client';

import { useEffect, useRef } from 'react';
import maplibregl, { Map as MLMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { QuadrantKey } from '@/lib/types';

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
}

export default function ChoroplethMap({ data, selected, onHover, onSelect, onReady }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const loaded = useRef(false);
  const hovered = useRef<string | null>(null);

  // -- init ---------------------------------------------------------------
  useEffect(() => {
    if (!holder.current || map.current) return;

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
          { id: 'bg', type: 'background', paint: { 'background-color': '#070a0e' } },
          {
            // POK fill — same dark grey as no-data districts, indicating the
            // area is part of India per official Survey of India boundary but
            // district-level administration data is not available.
            id: 'pok-fill',
            type: 'fill',
            source: 'pok',
            paint: { 'fill-color': '#1b212b', 'fill-opacity': 0.85 },
          },
          {
            // POK border — thin dashed-looking line marking the official claim
            id: 'pok-outline',
            type: 'line',
            source: 'pok',
            paint: { 'line-color': '#ece5d8', 'line-width': 0.8, 'line-opacity': 0.4, 'line-dasharray': [3, 3] },
          },
          {
            id: 'fill',
            type: 'fill',
            source: 'districts',
            paint: {
              'fill-color': [
                'case',
                ['==', ['feature-state', 'visible'], false],
                '#0c1017',
                ['coalesce', ['feature-state', 'colour'], '#0c1017'],
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
              'line-color': '#ece5d8',
              'line-width': 0.4,
              'line-opacity': 0.13,
            },
          },
          {
            id: 'hover',
            type: 'line',
            source: 'districts',
            filter: ['==', ['get', 'code'], ''],
            paint: { 'line-color': '#ece5d8', 'line-width': 1.4, 'line-opacity': 0.9 },
          },
          {
            id: 'selected',
            type: 'line',
            source: 'districts',
            filter: ['==', ['get', 'code'], ''],
            paint: { 'line-color': '#f3c14b', 'line-width': 2.2 },
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

  // -- selection ring ------------------------------------------------------
  useEffect(() => {
    const m = map.current;
    if (!m || !loaded.current) return;
    m.setFilter('selected', ['==', ['get', 'code'], selected ?? '']);
  }, [selected]);

  return <div ref={holder} className="map" />;
}
