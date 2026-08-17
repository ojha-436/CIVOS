'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { loadDataset } from '@/lib/data';
import { DEFAULT_WEIGHTS, WEIGHT_META, priority, formatCompact, rampColour } from '@/lib/scoring';
import { QUADRANTS, type Dataset, type QuadrantKey, type Weights } from '@/lib/types';
import Drilldown from '@/components/Drilldown';
import ThemeToggle from '@/components/ThemeToggle';
import { useTheme, MAP_GROUND, QUADRANT_HEX_BY_THEME } from '@/lib/theme';
import type { MapDatum } from '@/components/ChoroplethMap';

const ChoroplethMap = dynamic(() => import('@/components/ChoroplethMap'), { ssr: false });

// `no_data` is listed last and is a disclosure rather than a verdict — but it is
// listed, because otherwise the grey districts on the map look like a rendering
// fault instead of an honest admission that no official value could be loaded.
const QKEYS: QuadrantKey[] = ['act_now', 'silent_need', 'expectation_gap', 'stable', 'no_data'];

/* Literal hex, because the ramp mixes channels numerically and cannot read a
   CSS custom property. Kept in step with the tokens in globals.css. */
/* Quadrant hues for the choropleth now live in lib/theme.ts, keyed by theme —
   the light set is re-picked rather than inverted, because #f3c14b on paper
   measures ~1.6:1 and Silent Need is the one mark that must never be faint. */

export default function Console() {
  const [ds, setDs] = useState<Dataset | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const theme = useTheme();
  const [sector, setSector] = useState('water_sanitation');
  const [adjusted, setAdjusted] = useState(false);
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [onQuads, setOnQuads] = useState<Set<QuadrantKey>>(new Set(QKEYS));
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    loadDataset().then(setDs).catch((e) => console.error(e));
  }, []);

  const districts = useMemo(
    () => new Map((ds?.districts ?? []).map((d) => [d.code, d])),
    [ds],
  );

  /* Rank for the current sector under the current weights. Recomputed on every
     slider move — 594 rows, so it stays well inside a frame. */
  const ranked = useMemo(() => {
    if (!ds) return [];
    return ds.rows
      // A district with no official deficit value cannot be ranked against one
      // that has it. Excluded here rather than scored on a zero, which would
      // silently park every unmatched district at the bottom as if it were fine.
      .filter((r) => r.sector === sector && r.has_deficit)
      .map((r) => ({ row: r, p: priority(r, weights, adjusted) }))
      .sort((a, b) => b.p - a.p);
  }, [ds, sector, weights, adjusted]);

  /* Rank under the OPPOSITE mode, so each row can show how far it travelled when
     the participation correction was applied. The recolour alone is pretty; the
     movement is the argument. */
  const otherRank = useMemo(() => {
    if (!ds) return new Map<string, number>();
    const m = new Map<string, number>();
    ds.rows
      .filter((r) => r.sector === sector && r.has_deficit)
      .map((r) => ({ code: r.code, p: priority(r, weights, !adjusted) }))
      .sort((a, b) => b.p - a.p)
      .forEach((x, i) => m.set(x.code, i + 1));
    return m;
  }, [ds, sector, weights, adjusted]);

  const quadCounts = useMemo(() => {
    const c: Record<QuadrantKey, number> = {
      act_now: 0, silent_need: 0, expectation_gap: 0, stable: 0, no_data: 0,
    };
    ranked.forEach(({ row }) => (c[row.quadrant] += 1));
    ds?.rows.forEach((r) => {
      if (r.sector === sector && !r.has_deficit) c.no_data += 1;
    });
    return c;
  }, [ranked, ds, sector]);

  const mapData = useMemo(() => {
    const hex = QUADRANT_HEX_BY_THEME[theme];
    const ground = MAP_GROUND[theme];
    const m = new Map<string, MapDatum>();
    if (!ranked.length) return m;
    const max = ranked[0].p || 1;
    const min = ranked[ranked.length - 1].p;
    const span = Math.max(max - min, 1e-6);
    ranked.forEach(({ row, p }) => {
      const v = (p - min) / span;
      // Silent Need is boosted so it burns through even at a modest score. It is
      // the one thing the product exists to show, and a correct-but-invisible
      // rendering of it would be a design failure, not a neutral choice.
      const boost = row.quadrant === 'silent_need' ? 1.55 : 1;
      m.set(row.code, {
        colour: rampColour(hex[row.quadrant], v, boost, ground),
        q: row.quadrant,
        visible: onQuads.has(row.quadrant),
      });
    });
    // Unscored districts are painted explicitly rather than left unset, so the
    // absence of official data is visible on the map instead of looking like a
    // rendering gap.
    ds?.rows.forEach((r) => {
      if (r.sector === sector && !r.has_deficit) {
        m.set(r.code, { colour: hex.no_data, q: 'no_data', visible: true });
      }
    });
    return m;
  }, [ranked, onQuads, ds, sector, theme]);

  const visibleRank = useMemo(
    () => ranked.filter(({ row }) => onQuads.has(row.quadrant)),
    [ranked, onQuads],
  );

  const hoverRow = hover ? ranked.find((r) => r.row.code === hover) : null;
  const selRow = selected ? ranked.find((r) => r.row.code === selected) : null;

  const listRef = useRef<HTMLUListElement>(null);
  useEffect(() => {
    if (!selected || !listRef.current) return;
    listRef.current
      .querySelector(`[data-code="${selected}"]`)
      ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selected]);

  if (!ds) {
    return (
      <div className="boot">
        <div className="boot-inner">
          <div className="display">CIVOS</div>
          <div className="label">Loading 594 districts · 2,970 district-sector rows</div>
          <div className="sweep">
            <i />
          </div>
        </div>
      </div>
    );
  }

  const silentTop = visibleRank.filter((r) => r.row.quadrant === 'silent_need').length;
  const coverage = {
    districts: new Set(ds.rows.filter((r) => r.has_deficit).map((r) => r.code)).size,
  };

  return (
    <div className="shell">
      {/* ================= masthead ================= */}
      <header className="masthead">
        <Link href="/" className="wordmark" aria-label="CIVOS home">
          <b className="display">CIVOS</b>
          <span className="instance mono">IN</span>
        </Link>
        <div className="tagline">
          Citizen-signal infrastructure prioritisation · 594 districts · 5 sectors
        </div>
        <div className="masthead-right">
          <ThemeToggle />
          {/* The clickable wordmark is the convention, but an explicit control
              removes any doubt — the console is a deep page and there was no
              visible way back to the top level at all. "←" rather than "↗"
              because this ascends rather than moving sideways. */}
          <Link href="/" className="btn-ghost">
            ← Home
          </Link>
          <Link href="/report" className="btn-ghost">
            Citizen intake ↗
          </Link>
        </div>
      </header>

      {/* ================= calibration strip =================
          P0-16 requires a persistent, visible distinction between the real
          official layer and the synthetic citizen layer. Built as instrument
          calibration rather than a warning banner, because a banner gets
          dismissed and this must not be. */}
      <div className="strip">
        <div className="strip-item">
          <span className="dot real" />
          <span>
            <b>Real</b> — boundaries, names, and <b>NFHS-5 2019-21 deficit values</b> for{' '}
            {coverage.districts}/{ds.meta.counts.districts} districts
          </span>
        </div>
        <div className="strip-item">
          <span className="dot synth" />
          <span>
            <b>Synthetic</b> — citizen signals, generated with a deliberate participation bias
          </span>
        </div>
        <div className="strip-item">
          <span className="dot nodata" />
          <span>
            <b>No data</b> — {quadCounts.no_data} district-sectors this view, excluded from ranking
          </span>
        </div>
        <div className="strip-note">Fixture generated {ds.meta.generated_at}</div>
      </div>

      {/* ================= body ================= */}
      <div className="body">
        <div className="stage">
          <ChoroplethMap
            theme={theme}
            data={mapData}
            selected={selected}
            onHover={setHover}
            onSelect={(c) => setSelected(c)}
            onReady={() => setMapReady(true)}
          />
          <div className="ticks" />

          {hoverRow && (
            <div className="overlay readout">
              <div className="name">{districts.get(hoverRow.row.code)?.name}</div>
              <div className="state">{districts.get(hoverRow.row.code)?.state}</div>
              <dl className="readout-grid">
                <dt>Priority</dt>
                <dd style={{ color: 'var(--gold)' }}>{hoverRow.p.toFixed(1)}</dd>
                <dt>Deficit</dt>
                <dd>{hoverRow.row.deficit.toFixed(1)}</dd>
                <dt>Demand</dt>
                <dd>{(adjusted ? hoverRow.row.adjusted_demand : hoverRow.row.demand).toFixed(1)}</dd>
                <dt>Signals</dt>
                <dd>{formatCompact(hoverRow.row.signals)}</dd>
                <dt>Quadrant</dt>
                <dd style={{ color: QUADRANTS[hoverRow.row.quadrant].colour }}>
                  {QUADRANTS[hoverRow.row.quadrant].label}
                </dd>
              </dl>
            </div>
          )}

          <div className="overlay legend rise d4">
            <h4 className="label">Quadrant · click to filter</h4>
            {QKEYS.map((k) => (
              <button
                key={k}
                className={`q-row${k === 'silent_need' ? ' silent' : ''}`}
                data-on={onQuads.has(k)}
                onClick={() => {
                  const next = new Set(onQuads);
                  next.has(k) ? next.delete(k) : next.add(k);
                  setOnQuads(next.size ? next : new Set(QKEYS));
                }}
              >
                <span className="q-swatch" style={{ background: QUADRANTS[k].colour }} />
                <span>{QUADRANTS[k].label}</span>
                <span className="count">{quadCounts[k]}</span>
              </button>
            ))}
            <p className="legend-foot">{QUADRANTS.silent_need.blurb}</p>
          </div>

          <div className="overlay scale rise d5">
            <div className="scale-labels" style={{ marginBottom: 5, marginTop: 0 }}>
              <span>Hue = quadrant · intensity = priority</span>
            </div>
            <div className="scale-bar" />
            <div className="scale-labels">
              <span>recedes</span>
              <span>acts on this</span>
            </div>
          </div>

          {selRow && (
            <Drilldown
              ds={ds}
              district={districts.get(selRow.row.code)!}
              row={selRow.row}
              sectorKey={sector}
              weights={weights}
              adjusted={adjusted}
              onClose={() => setSelected(null)}
            />
          )}
        </div>

        {/* ================= instrument rail ================= */}
        <aside className="rail">
          <div className="rail-scroll">
            {/* -- sector ------------------------------------------------- */}
            <div className="panel rise d1">
              <h3 className="label">Sector</h3>
              <div className="sectors">
                {ds.sectors.map((s) => (
                  <button
                    key={s.key}
                    className="sector-btn"
                    aria-pressed={sector === s.key}
                    onClick={() => {
                      setSector(s.key);
                      setSelected(null);
                    }}
                  >
                    <span>{s.label}</span>
                    <span className="n">{s.schemes.length} schemes</span>
                  </button>
                ))}
              </div>
            </div>

            {/* -- THE TOGGLE --------------------------------------------- */}
            <div className="toggle-panel rise d2">
              <h3 className="label" style={{ marginBottom: 11 }}>
                Ranking basis
              </h3>
              <div
                className="switch"
                data-adjusted={adjusted}
                role="switch"
                aria-checked={adjusted}
                tabIndex={0}
                onClick={() => setAdjusted((v) => !v)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setAdjusted((v) => !v);
                  }
                }}
              >
                <div className="switch-half">
                  <b>Raw demand</b>
                  <span style={{ fontSize: 9.5 }}>as filed</span>
                </div>
                <div className="switch-half">
                  <b>Equity-adjusted</b>
                  <span style={{ fontSize: 9.5 }}>bias corrected</span>
                </div>
              </div>
              <p className="toggle-caption">
                {adjusted ? (
                  <>
                    Corrected for participation. <em>{silentTop} Silent Need</em>{' '}
                    district-sectors are now visible — severe deficit, almost no
                    citizen voice. Silence is not satisfaction.
                  </>
                ) : (
                  <>
                    Complaint volume only — what a grievance dashboard can see. This
                    is a map of who owns a phone and knows how to complain —{' '}
                    <em>not a map of need</em>.
                  </>
                )}
              </p>
            </div>

            {/* -- weights ------------------------------------------------- */}
            <div className="panel rise d3">
              <h3 className="label">Weights · w₁–w₅</h3>
              {WEIGHT_META.map(({ key, name, note }) => {
                // w2 and w3 are the correction itself, so they do nothing to a raw
                // complaint-volume ranking. Marking them inactive is more honest
                // than leaving live controls that silently have no effect.
                const inactive = !adjusted && (key === 'w2' || key === 'w3');
                return (
                <div key={key} data-inactive={inactive} className="weight-block">
                  <div className="weight">
                    <span className="w-name">
                      <span className="w-key">{key}</span>
                      {name}
                    </span>
                    <span className="w-val">
                      {inactive ? '—' : weights[key].toFixed(2)}
                    </span>
                  </div>
                  <div className="slider-wrap">
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.01}
                      value={weights[key]}
                      aria-label={name}
                      disabled={inactive}
                      onChange={(e) =>
                        setWeights((w) => ({ ...w, [key]: Number(e.target.value) }))
                      }
                    />
                  </div>
                  {inactive ? (
                    <p className="w-note">Not applied to a raw complaint-volume ranking.</p>
                  ) : (
                    note && <p className="w-note">{note}</p>
                  )}
                </div>
                );
              })}
              <button className="reset" onClick={() => setWeights(DEFAULT_WEIGHTS)}>
                Reset to policy default
              </button>
            </div>

            {/* -- ranked list --------------------------------------------- */}
            <div style={{ paddingTop: 15 }}>
              <div className="rank-head">
                <span className="label">#</span>
                <span className="label">District</span>
                <span className="label" style={{ textAlign: 'right' }}>
                  Score
                </span>
              </div>
              {visibleRank.length === 0 && (
                <p
                  style={{
                    padding: '18px 17px',
                    fontSize: 12,
                    lineHeight: 1.6,
                    color: 'var(--paper-3)',
                    margin: 0,
                  }}
                >
                  <strong style={{ color: 'var(--gold)' }}>No official indicator loaded</strong>{' '}
                  for this sector. Road connectivity is not a health-survey measure, so NFHS-5
                  carries no equivalent — it needs PMGSY habitation data, which is not loaded
                  yet. The sector is left visibly empty rather than filled with a proxy: two
                  real sectors beat five mangled ones.
                </p>
              )}
              <ul className="rank-list" ref={listRef}>
                {visibleRank.slice(0, 120).map(({ row, p }, i) => {
                  const d = districts.get(row.code);
                  const prev = otherRank.get(row.code);
                  const moved = prev ? prev - (i + 1) : 0;
                  return (
                    <li key={row.code}>
                      <button
                        className="rank-item"
                        data-code={row.code}
                        data-selected={selected === row.code}
                        onClick={() => setSelected(row.code)}
                      >
                        <span className="rank-n">{String(i + 1).padStart(2, '0')}</span>
                        <span>
                          <span className="rank-name">
                            <span
                              className="qtag"
                              style={{ background: QUADRANTS[row.quadrant].colour }}
                            />
                            {d?.name}
                            {/* Only meaningful in the corrected view, where it reads
                                "rose N places once participation was accounted for".
                                In raw mode the same number means the opposite — a
                                district about to fall — so an up-arrow there lies. */}
                            {adjusted && moved >= 12 && (
                              <span
                                className="delta up"
                                title={`Rose ${moved} places once participation bias was corrected`}
                                key={`${adjusted}-${row.code}`}
                              >
                                ▲{moved}
                              </span>
                            )}
                          </span>
                          <span className="rank-state">
                            {d?.state} · {formatCompact(row.signals)} signals ·{' '}
                            {row.needs} needs
                          </span>
                        </span>
                        <span className="rank-score">{p.toFixed(1)}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
