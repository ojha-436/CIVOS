'use client';

/* The budget workbench — where a ranking becomes a portfolio.
 *
 * Everything else in this console answers "what is worst?". This page answers
 * the question an official actually has to answer: "which of these do I fund
 * with the money I have, and what do I tell the auditor about the rest?"
 *
 * Three lanes, not one portfolio. That is the whole argument of the page and it
 * falls out of the quadrant model rather than being bolted on — a place that has
 * not spoken cannot be funded on its silence, so it gets a reserved budget line
 * for going and asking instead. A generic optimiser has no way to express that,
 * because it has no concept of a district that said nothing.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import AccountMenu from '@/components/AccountMenu';
import RequireAuth from '@/components/RequireAuth';
import ThemeToggle from '@/components/ThemeToggle';
import { formatCompact, formatINR } from '@/lib/scoring';
import {
  DEFAULT_DIALS,
  LANES,
  solve,
  type AllocationResult,
  draftLetter,
  type Award,
  type ConstraintStatus,
  type Dials,
  type LaneKey,
  type LetterResult,
} from '@/lib/allocation';
import './allocate.css';

/* Budget steps rather than a linear range. A linear slider from ten crore to a
   thousand spends nine tenths of its travel in territory nobody demonstrates,
   and the interesting behaviour — constraints starting to bind — all happens in
   the bottom fifth. Discrete rungs also make the demo repeatable: the same drag
   lands on the same number every time. */
const BUDGET_STEPS = [
  1e8, 2e8, 4e8, 6e8, 8e8, 1e9, 1.5e9, 2e9, 3e9, 4e9, 6e9, 8e9, 1e10,
];

function nearestStep(v: number): number {
  let best = 0;
  BUDGET_STEPS.forEach((s, i) => {
    if (Math.abs(s - v) < Math.abs(BUDGET_STEPS[best] - v)) best = i;
  });
  return best;
}

/* The server sends numbers and a prose fallback; the console composes the
 * sentence. Currency grouping is a country convention — lakh and crore here,
 * thousands elsewhere — so it belongs on the rendering side, next to the
 * formatter that knows which convention applies. Without this the chips read
 * "3844084000 of 3844450000", which is technically the truth and practically
 * unreadable. */
function constraintText(c: ConstraintStatus): string {
  // `== null` deliberately: an older API build omits the fields entirely, and
  // `undefined` must fall back to the prose rather than render as "undefined".
  if (c.value == null || c.limit == null) return c.detail;
  const fmt = (n: number) => (c.kind === 'currency' ? formatINR(n) : String(n));
  switch (c.name) {
    case 'budget':
      return `${fmt(c.value)} of ${fmt(c.limit)} committed`;
    case 'equity_floor':
      return `${fmt(c.value)} reaches deprived districts · floor ${fmt(c.limit)}`;
    case 'geographic_spread':
      return `${c.value} states covered · minimum ${c.limit}`;
    case 'sector_cap':
      return c.satisfied
        ? `largest sector ${fmt(c.value)} · ceiling ${fmt(c.limit)}`
        : `over ceiling — ${fmt(c.value)} against ${fmt(c.limit)}`;
    case 'outreach_reserve':
      return `${fmt(c.value)} held for outreach · cap ${fmt(c.limit)}`;
    default:
      return c.detail;
  }
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value display">{value}</div>
      {sub ? <div className="stat-sub">{sub}</div> : null}
    </div>
  );
}

function Dial({
  label,
  hint,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="dial">
      <div className="dial-head">
        <span className="dial-label">{label}</span>
        <span className="dial-value mono">{format(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <div className="dial-hint">{hint}</div>
    </label>
  );
}

function AwardRow({
  a,
  lane,
  onDraft,
}: {
  a: Award;
  lane: LaneKey;
  onDraft: (a: Award) => void;
}) {
  return (
    <li className="award">
      <div className="award-main">
        <span className="award-place">
          {a.district ?? a.code}
          <span className="award-state">{a.state}</span>
        </span>
        <span className="award-scheme mono">{a.scheme}</span>
      </div>
      <div className="award-meta">
        <span className="mono">{formatINR(a.cost)}</span>
        {lane === 'fund' && a.beneficiaries !== null ? (
          <span className="mono dim">{formatCompact(a.beneficiaries)} served</span>
        ) : null}
        <span className="mono dim">conf {a.confidence.toFixed(0)}</span>
        {a.deprived ? <span className="tag-deprived">deprived</span> : null}
        {lane === 'fund' ? (
          <button className="btn-draft" onClick={() => onDraft(a)}>
            Draft note
          </button>
        ) : null}
      </div>
    </li>
  );
}

/* The dispatch note.
 *
 * This is the step between "here is the evidence" and "here is the thing you
 * sign", and it is deliberately the smaller of the two claims. CIVOS drafts; an
 * officer reads; dispatch happens on whatever channel the ministry already runs.
 * The panel says so twice — in the header and at the foot — because a drafted
 * letter on screen is exactly the artefact somebody could mistake for a sent one.
 */
function LetterPanel({
  award,
  result,
  busy,
  onClose,
}: {
  award: Award;
  result: LetterResult | null;
  busy: boolean;
  onClose: () => void;
}) {
  const ev = result?.evidence;
  return (
    <div className="letter-scrim" onClick={onClose}>
      <div className="letter" onClick={(e) => e.stopPropagation()}>
        <header className="letter-head">
          <div>
            <div className="letter-eyebrow">Dispatch note · composed, not sent</div>
            <h3 className="display">
              {award.district} — {award.scheme}
            </h3>
            {ev ? <div className="letter-to">To: {ev.ministry}</div> : null}
          </div>
          <button className="btn-ghost" onClick={onClose}>
            Close
          </button>
        </header>

        {busy ? <p className="letter-busy">Drafting from the cited evidence…</p> : null}

        {result?.error ? (
          <div className="banner-error">
            {result.error} The evidence below is still shown, because it is the part that
            came from the data rather than the model.
          </div>
        ) : null}

        {result?.prose ? <pre className="letter-prose">{result.prose}</pre> : null}

        {ev ? (
          <div className="letter-evidence">
            <h4>Everything the draft was allowed to use</h4>
            <dl>
              <dt>Indicator</dt>
              <dd>
                {ev.indicator} — {ev.deficit}% ({ev.source}, {ev.year}), {ev.percentile}th
                percentile nationally
              </dd>
              <dt>Citizen signal</dt>
              <dd>
                {ev.needs} distinct needs from {ev.signals} reports · confidence{' '}
                {ev.confidence.toFixed(0)}/100
              </dd>
              <dt>Requested</dt>
              <dd>
                {ev.units} × {ev.unit} · {formatINR(ev.cost)}
              </dd>
              <dt>People served</dt>
              <dd>
                {ev.beneficiaries === null
                  ? 'Unavailable — no census population reconciled onto this district. Not estimated.'
                  : formatCompact(ev.beneficiaries)}
              </dd>
              {ev.caveat ? (
                <>
                  <dt>Caveat</dt>
                  <dd>{ev.caveat}</dd>
                </>
              ) : null}
            </dl>
          </div>
        ) : null}

        <p className="letter-foot">
          <b>Nothing has been sent.</b> CIVOS composes the note; dispatch belongs to whatever
          channel the ministry already runs. The citizen reports behind it are synthetic
          demonstration data — the indicator, the boundaries and the unit costs are real.
        </p>
      </div>
    </div>
  );
}

function WorkbenchInner() {
  const [dials, setDials] = useState<Dials>(DEFAULT_DIALS);
  const [result, setResult] = useState<AllocationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lane, setLane] = useState<LaneKey>('fund');
  const [letterFor, setLetterFor] = useState<Award | null>(null);
  const [letter, setLetter] = useState<LetterResult | null>(null);
  const [letterBusy, setLetterBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);

  /* Debounced so a drag issues one solve per pause rather than one per pixel,
     and the in-flight request is aborted rather than left to land out of order —
     without that, releasing the slider can leave the screen showing the answer
     to a budget the user has already moved past. */
  useEffect(() => {
    const t = setTimeout(() => {
      abort.current?.abort();
      const ctrl = new AbortController();
      abort.current = ctrl;
      setBusy(true);
      solve(dials, ctrl.signal)
        .then((r) => {
          setResult(r);
          setError(null);
        })
        .catch((e) => {
          if (e?.name !== 'AbortError') setError(String(e));
        })
        .finally(() => {
          if (!ctrl.signal.aborted) setBusy(false);
        });
    }, 160);
    return () => clearTimeout(t);
  }, [dials]);

  const set = useCallback(
    <K extends keyof Dials>(k: K, v: Dials[K]) => setDials((d) => ({ ...d, [k]: v })),
    [],
  );

  const onDraft = useCallback((a: Award) => {
    setLetterFor(a);
    setLetter(null);
    setLetterBusy(true);
    draftLetter(a.code, a.sector, a.scheme)
      .then(setLetter)
      .catch((e) => setLetter({ prose: null, evidence: null as never, error: String(e) }))
      .finally(() => setLetterBusy(false));
  }, []);

  const awards = useMemo(() => {
    if (!result) return [];
    return lane === 'fund' ? result.funded : lane === 'verify' ? result.verify : result.outreach;
  }, [result, lane]);

  const s = result?.summary;

  return (
    <div className="shell">
      <header className="masthead">
        <Link href="/" className="wordmark" aria-label="CIVOS home">
          <b className="display">CIVOS</b>
          <span className="instance mono">IN</span>
        </Link>
        <div className="tagline wb-tagline">
          Budget workbench · what the ranking costs, and who it reaches
        </div>
        <div className="masthead-right">
          <AccountMenu />
          <ThemeToggle />
          <Link href="/console" className="btn-ghost">
            ← Console
          </Link>
        </div>
      </header>

      <div className="wb">
        {/* ── controls ─────────────────────────────────────────────── */}
        <aside className="wb-controls">
          <div className="budget-block">
            <div className="budget-label">Delivery envelope</div>
            <div className="budget-value display">{formatINR(dials.budget)}</div>
            <input
              className="budget-slider"
              type="range"
              min={0}
              max={BUDGET_STEPS.length - 1}
              step={1}
              value={nearestStep(dials.budget)}
              onChange={(e) => set('budget', BUDGET_STEPS[Number(e.target.value)])}
              aria-label="Delivery envelope"
            />
            <div className="budget-ends mono">
              <span>{formatINR(BUDGET_STEPS[0])}</span>
              <span>{formatINR(BUDGET_STEPS[BUDGET_STEPS.length - 1])}</span>
            </div>
          </div>

          <div className="dials">
            <Dial
              label="Sector ceiling"
              hint="No single sector may absorb more than this share. Stops a portfolio becoming one programme."
              value={dials.sector_cap_share}
              min={0.15}
              max={1}
              step={0.05}
              format={(v) => `${Math.round(v * 100)}%`}
              onChange={(v) => set('sector_cap_share', v)}
            />
            <Dial
              label="Equity floor"
              hint="Minimum share that must reach districts in the worst third on their sector's indicator."
              value={dials.equity_floor_share}
              min={0}
              max={0.8}
              step={0.05}
              format={(v) => `${Math.round(v * 100)}%`}
              onChange={(v) => set('equity_floor_share', v)}
            />
            <Dial
              label="Geographic spread"
              hint="Minimum number of states that must receive something."
              value={dials.min_groups}
              min={1}
              max={28}
              step={1}
              format={(v) => `${v} states`}
              onChange={(v) => set('min_groups', v)}
            />
            <Dial
              label="Outreach reserve"
              hint="Held back to send enumerators into districts that never reported. This is what replaces funding silence."
              value={dials.outreach_reserve_share}
              min={0}
              max={0.2}
              step={0.01}
              format={(v) => `${Math.round(v * 100)}%`}
              onChange={(v) => set('outreach_reserve_share', v)}
            />
            <Dial
              label="Verification reserve"
              hint="Held back to field-check needs the trust model could not confirm."
              value={dials.verify_reserve_share}
              min={0}
              max={0.2}
              step={0.01}
              format={(v) => `${Math.round(v * 100)}%`}
              onChange={(v) => set('verify_reserve_share', v)}
            />
            <Dial
              label="Confidence floor"
              hint="Below this, a need is verified before it is funded — never discarded."
              value={dials.confidence_floor}
              min={0}
              max={90}
              step={5}
              format={(v) => `${v}`}
              onChange={(v) => set('confidence_floor', v)}
            />
          </div>

          <button className="btn-reset" onClick={() => setDials(DEFAULT_DIALS)}>
            Reset to defaults
          </button>
        </aside>

        {/* ── results ──────────────────────────────────────────────── */}
        <main className="wb-main">
          <div className={`stats${busy ? ' is-busy' : ''}`}>
            <Stat
              label="Committed to delivery"
              value={s ? formatINR(s.funded_cost) : '—'}
              sub={s ? `${s.funded} projects` : undefined}
            />
            <Stat
              label="People reached"
              value={s ? formatCompact(s.beneficiaries) : '—'}
              sub="capped at the deprived population"
            />
            <Stat
              label="Cost per person"
              value={s?.cost_per_beneficiary ? formatINR(s.cost_per_beneficiary) : '—'}
              sub="the number the optimiser maximises against"
            />
            <Stat
              label="Sent to outreach"
              value={s ? String(s.outreach) : '—'}
              sub="districts with deficit and no voice"
            />
          </div>

          {error ? <div className="banner-error">Could not solve: {error}</div> : null}

          {s?.infeasible?.length ? (
            <div className="banner-infeasible">
              <b>Cannot satisfy every constraint at this envelope.</b>
              <ul>
                {s.infeasible.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
              Shown rather than resolved by quietly relaxing a dial.
            </div>
          ) : null}

          <div className="constraints">
            {result?.constraints.map((c) => (
              <div key={c.name} className={`chip${c.satisfied ? '' : ' chip-bad'}`}>
                <span className="chip-name mono">{c.name.replace(/_/g, ' ')}</span>
                <span className="chip-detail">{constraintText(c)}</span>
              </div>
            ))}
          </div>

          <div className="lanes">
            {(Object.keys(LANES) as LaneKey[]).map((k) => {
              const n = k === 'fund' ? s?.funded : k === 'verify' ? s?.verify : s?.outreach;
              return (
                <button
                  key={k}
                  className={`lane-tab${lane === k ? ' is-on' : ''}`}
                  style={{ ['--lane' as string]: LANES[k].colour }}
                  onClick={() => setLane(k)}
                >
                  <span className="lane-name">{LANES[k].label}</span>
                  <span className="lane-count mono">{n ?? '—'}</span>
                </button>
              );
            })}
          </div>

          <p className="lane-hint">{LANES[lane].hint}</p>

          <ul className="awards">
            {awards.slice(0, 120).map((a) => (
              <AwardRow key={a.id} a={a} lane={lane} onDraft={onDraft} />
            ))}
          </ul>
          {awards.length > 120 ? (
            <p className="more mono">
              showing 120 of {awards.length} — the full set is in the API response
            </p>
          ) : null}

          {result ? (
            <details className="dropped">
              <summary>
                Why was something not funded? <span className="mono">{result.dropped_total}</span>{' '}
                candidates were rejected
              </summary>
              <ul>
                {result.dropped_sample.map((d) => (
                  <li key={d.id}>
                    <span className="mono">{d.id}</span>
                    <span>{d.reason}</span>
                  </li>
                ))}
              </ul>
              <p className="note">
                A sample of the first fifty. Every rejection carries a reason; the list is not
                printed in full because four thousand of them is a download, not an explanation.
              </p>
            </details>
          ) : null}

          {s ? <p className="optimality">{s.optimality_note}</p> : null}

          {/* Said on screen because its most visible effect is an absence, and an
              absence explains nothing by itself. A reader who knows the scheme
              catalogue will notice the urban programme never appears and should
              find the reason here rather than assume a bug. */}
          <p className="optimality">
            A scheme is proposed only where its published settlement scope overlaps what the
            sector&rsquo;s indicator actually measures. The roads indicator is the Census Village
            Directory, which counts villages and has no urban universe, so no urban roads
            programme is proposed anywhere in this build.
          </p>
        </main>
      </div>

      {letterFor ? (
        <LetterPanel
          award={letterFor}
          result={letter}
          busy={letterBusy}
          onClose={() => {
            setLetterFor(null);
            setLetter(null);
          }}
        />
      ) : null}
    </div>
  );
}

export default function Workbench() {
  return (
    <RequireAuth>
      <WorkbenchInner />
    </RequireAuth>
  );
}
