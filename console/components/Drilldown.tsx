'use client';

import type { Dataset, District, Row, Weights } from '@/lib/types';
import { QUADRANTS } from '@/lib/types';
import { costBand, formatINR, priority } from '@/lib/scoring';

interface Props {
  ds: Dataset;
  district: District;
  row: Row;
  sectorKey: string;
  weights: Weights;
  adjusted: boolean;
  onClose: () => void;
}

export default function Drilldown({ ds, district, row, sectorKey, weights, adjusted, onClose }: Props) {
  const sector = ds.sectors.find((s) => s.key === sectorKey)!;
  const q = QUADRANTS[row.quadrant];
  const p = priority(row, weights, adjusted);
  const quotes = row.quotes.map((i) => ds.quote_pool[sectorKey]?.[i]).filter(Boolean);
  const scheme = sector.schemes[0];
  const [lo, hi] = costBand(row.needs, scheme.unit_cost_inr);

  // Population affected: share of the district carrying the deficit. Placeholder
  // population until Phase 1, and the dossier says so rather than implying census
  // precision it does not have.
  const affected = Math.round((district.population * row.deficit) / 100);

  const terms: { name: string; v: number; max: number; gold?: boolean }[] = [
    { name: adjusted ? 'Adjusted demand' : 'Demand index', v: adjusted ? row.adjusted_demand : row.demand, max: 100 },
    { name: 'Deficit index', v: row.deficit, max: 100 },
    { name: 'Silence gap', v: Math.max(row.silence_gap, 0), max: 100, gold: row.quadrant === 'silent_need' },
    { name: 'Forecast growth (90d)', v: Math.max(row.forecast, 0), max: 20 },
    { name: 'Evidence strength', v: row.evidence, max: 100 },
  ];

  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <section className="drawer" role="dialog" aria-label={`${district.name} dossier`}>
        <header className="drawer-head">
          <div className="drawer-title" style={{ flex: 1 }}>
            <h2 className="display">{district.name}</h2>
            <div className="sub">
              {district.state} · {sector.label} · {district.code}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <span className="quadrant-badge" style={{ color: q.colour }}>
              {q.label}
            </span>
            <button className="close-x" onClick={onClose} aria-label="Close">
              ×
            </button>
          </div>
        </header>

        <div className="drawer-body">
          {/* -- column 1: the score, term by term -------------------------- */}
          <div className="col">
            <h4 className="label">Priority — every term</h4>
            <div className="terms">
              {terms.map((t) => (
                <div key={t.name}>
                  <div className="term">
                    <span className="term-name">{t.name}</span>
                    <span className="v">{t.v.toFixed(1)}</span>
                    <div className={`term-bar${t.gold ? ' gold' : ''}`}>
                      <i style={{ width: `${Math.min(100, (t.v / t.max) * 100)}%` }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="priority-line">
              <span className="label">Priority score</span>
              <span className="big">{p.toFixed(1)}</span>
            </div>

            <div style={{ marginTop: 16 }}>
              <h4 className="label">Signal composition</h4>
              <dl className="readout-grid" style={{ borderTop: 0, paddingTop: 0, marginTop: 8 }}>
                <dt>Raw signals</dt>
                <dd>{row.signals.toLocaleString('en-IN')}</dd>
                <dt>Distinct needs</dt>
                <dd>{row.needs.toLocaleString('en-IN')}</dd>
                <dt>Languages</dt>
                <dd>{row.languages}</dd>
                <dt>With photograph</dt>
                <dd>{row.images}</dd>
                <dt>Participation / 1k</dt>
                <dd>{row.participation.toFixed(2)}</dd>
                <dt>Voice correction</dt>
                <dd style={{ color: row.voice_correction > 1.4 ? 'var(--gold)' : undefined }}>
                  ×{row.voice_correction.toFixed(2)}
                </dd>
                <dt>Population affected</dt>
                <dd title="Derived from a placeholder district population — no census population is loaded yet">
                  {affected.toLocaleString('en-IN')}{' '}
                  <span style={{ color: 'var(--q-silent)', fontSize: 10 }}>est.</span>
                </dd>
              </dl>
            </div>
          </div>

          {/* -- column 2: what citizens actually said ---------------------- */}
          <div className="col">
            <h4 className="label">
              Representative signals — cluster centroids
            </h4>
            {quotes.length ? (
              quotes.map((qt, i) => (
                <blockquote className="quote" key={i}>
                  <div className="orig">{qt.original}</div>
                  <div className="eng">{qt.english}</div>
                  <div className="lang">
                    {qt.lang} → en · cluster C-{String(i + 1).padStart(2, '0')}
                  </div>
                </blockquote>
              ))
            ) : (
              <p style={{ fontSize: 12, color: 'var(--paper-3)', lineHeight: 1.55 }}>
                No citizen signals from this district in this sector. That absence is
                the finding, not a gap in the data — it is why this district appears
                in the ranking at all.
              </p>
            )}

            <h4 className="label" style={{ marginTop: 18 }}>
              Evidence strip — {row.images} photograph{row.images === 1 ? '' : 's'}
            </h4>
            {row.assets.length ? (
              <div className="evidence">
                {row.assets.map((a, i) => (
                  <figure className="ev" key={i}>
                    <span className="sev">S{a.severity}</span>
                    <figcaption className="t">
                      {a.type.replace(/_/g, ' ')}
                      <br />
                      <span style={{ color: 'var(--q-act)' }}>{a.flag.replace(/_/g, ' ')}</span>
                    </figcaption>
                  </figure>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 11, color: 'var(--paper-4)', lineHeight: 1.5, margin: 0 }}>
                No photographic corroboration. Evidence strength carries the smallest
                weight precisely so this does not push a district down the ranking.
              </p>
            )}
          </div>

          {/* -- column 3: the funding route -------------------------------- */}
          <div className="col">
            <h4 className="label">Deficit evidence</h4>
            <div className="scheme" style={{ background: 'var(--ink-700)' }}>
              <div style={{ fontSize: 12, color: 'var(--paper-2)', lineHeight: 1.5 }}>
                {sector.indicator}
              </div>
              <div className="cost" style={{ marginTop: 8 }}>
                <span className="label">District value</span>
                <span className="amt">{row.deficit.toFixed(1)}%</span>
              </div>
              <div className="elig" style={{ marginTop: 8 }}>
                Source: <strong>NFHS-5 {sector.year}</strong> — National Family Health Survey,
                IIPS &amp; Ministry of Health and Family Welfare, Government of India.{' '}
                <span style={{ color: 'var(--q-gap)' }}>Real measured value</span>, reconciled
                onto this district and cross-validated against an independent extraction.
              </div>
            </div>

            <h4 className="label" style={{ marginTop: 16 }}>
              Funding route
            </h4>
            <div className="scheme">
              <div className="nm">{scheme.name}</div>
              <div className="min">{scheme.ministry}</div>
              <div className="elig">{scheme.eligibility}</div>
              <div className="cost">
                <span className="label">Indicative band</span>
                <span className="amt">
                  {formatINR(lo)} – {formatINR(hi)}
                </span>
              </div>
              <div className="min" style={{ marginTop: 6 }}>
                Derived from published unit cost per {scheme.unit}
              </div>
            </div>

            {row.quadrant === 'silent_need' ? (
              <div className="outreach">
                <p>
                  <strong style={{ color: 'var(--gold)' }}>Silent Need.</strong> Severe
                  measured deficit and almost no citizen voice. CIVOS does not
                  recommend funding on silence — that would replace one guess with
                  another. It recommends going to listen.
                </p>
                <button className="btn-gold" onClick={() => alert('Outreach dispatch — wired in Phase 5')}>
                  Dispatch outreach
                </button>
              </div>
            ) : (
              <button className="btn-gold" onClick={() => alert('Dossier generation — wired in Phase 5')}>
                Generate full dossier
              </button>
            )}

            <p style={{ fontSize: 10.5, color: 'var(--paper-4)', lineHeight: 1.5, marginTop: 12 }}>
              Every claim above resolves to a signal cluster, an image ID or a dataset
              row. Dossier prose is generated only from a retrieved evidence bundle —
              no claim can appear that is not in it.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
