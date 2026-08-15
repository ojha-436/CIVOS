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
        },
        layers: [
          { id: 'bg', type: 'background', paint: { 'background-color': '#070a0e' } },
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
      // Overridden by fitBounds once the geometry lands. A fixed centre/zoom left
      // the country floating in a third of the frame on a wide display.
      center: [82.5, 22.4],
      zoom: 3.6,
      minZoom: 3,
      maxZoom: 9,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
    });

    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    m.on('load', () => {
      loaded.current = true;
      onReady();
    });

    // Frame the country to the stage once, from the geometry itself, so the map
    // fills whatever aspect ratio the display happens to be. Left padding clears
    // the calibration ticks; bottom padding clears the legend and scale bar.
    let framed = false;
    m.on('sourcedata', (e) => {
      if (framed || e.sourceId !== 'districts' || !m.isSourceLoaded('districts')) return;
      const feats = m.querySourceFeatures('districts');
      if (!feats.length) return;
      framed = true;

      // Fit to the central mass of district centroids, not to the full extent.
      // Outlying island territories are real and stay drawn, but including them
      // in the bounds drags the frame south-east and leaves the mainland — where
      // 99% of the districts are — small and off-centre.
      const cx: number[] = [];
      const cy: number[] = [];
      for (const f of feats) {
        const g = f.geometry;
        const rings =
          g.type === 'Polygon' ? g.coordinates : g.type === 'MultiPolygon' ? g.coordinates.flat() : [];
        let sx = 0, sy = 0, n = 0;
        for (const ring of rings)
          for (const c of ring as [number, number][]) {
            sx += c[0];
            sy += c[1];
            n++;
          }
        if (n) {
          cx.push(sx / n);
          cy.push(sy / n);
        }
      }
      if (!cx.length) return;

      cx.sort((a, z) => a - z);
      cy.sort((a, z) => a - z);
      const pct = (arr: number[], p: number) => arr[Math.floor((arr.length - 1) * p)];
      const pad = 1.1; // degrees, so edge districts are not clipped by their centroid

      m.fitBounds(
        new maplibregl.LngLatBounds(
          [pct(cx, 0.004) - pad, pct(cy, 0.01) - pad],
          [pct(cx, 0.996) + pad, pct(cy, 0.999) + pad],
        ),
        { padding: { top: 34, right: 34, bottom: 96, left: 56 }, duration: 0 },
      );
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
