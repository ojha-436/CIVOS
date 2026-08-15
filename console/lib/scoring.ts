/* The prioritisation formula, SPEC §8, computed in the browser.
 *
 * Priority(d,s) = w1·AdjustedDemand + w2·DeficitIndex + w3·max(SilenceGap,0)
 *               + w4·ForecastGrowth + w5·EvidenceStrength
 *
 * It runs client-side on stored terms rather than server-side on a fixed score
 * because the weights are sliders. A ministry will not adopt a ranking it cannot
 * re-weight to its own policy priorities, and re-weighting has to feel immediate
 * or nobody touches it.
 *
 * `raw` mode drops the participation correction — that is the whole argument the
 * console exists to make, so it is a single flag rather than a separate pipeline.
 */

import type { Row, Weights } from './types';

export const DEFAULT_WEIGHTS: Weights = { w1: 0.3, w2: 0.3, w3: 0.25, w4: 0.05, w5: 0.1 };

export const WEIGHT_META: {
  key: keyof Weights;
  name: string;
  note?: string;
}[] = [
  { key: 'w1', name: 'Adjusted demand' },
  { key: 'w2', name: 'Measured deficit' },
  { key: 'w3', name: 'Silence gap' },
  { key: 'w4', name: 'Forecast growth' },
  {
    key: 'w5',
    name: 'Evidence strength',
    note: 'Deliberately the smallest weight. If photographic evidence counted for much, districts where nobody owns a camera would be punished twice. Set it to zero and the argument still holds.',
  },
];

export function priority(row: Row, w: Weights, adjusted: boolean): number {
  if (!adjusted) {
    // RAW: what a conventional grievance dashboard can actually see — complaint
    // volume, and nothing else. Deficit and silence gap are deliberately excluded
    // here, because they come from official data a complaint dashboard has never
    // joined against. Leaving w2·deficit in raw mode was quietly lending the naive
    // view our own correction, which flattened the entire argument: high-deficit
    // silent districts scored well before the correction was applied.
    return w.w1 * row.demand + w.w4 * Math.max(row.forecast, 0) + w.w5 * row.evidence;
  }
  // ADJUSTED: the full SPEC §8 formula.
  return (
    w.w1 * row.adjusted_demand +
    w.w2 * row.deficit +
    w.w3 * Math.max(row.silence_gap, 0) +
    w.w4 * Math.max(row.forecast, 0) +
    w.w5 * row.evidence
  );
}

/** Cost band from published scheme unit costs. Indicative, and labelled as such. */
export function costBand(needs: number, unitCost: number): [number, number] {
  const units = Math.max(1, Math.round(needs * 0.6));
  return [units * unitCost * 0.8, units * unitCost * 1.35];
}

export function formatINR(n: number): string {
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(1)} cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)} lakh`;
  return `₹${Math.round(n).toLocaleString('en-IN')}`;
}

/* Colour model for the choropleth.
 *
 * Hue carries the quadrant, intensity carries priority — and intensity is applied
 * by mixing toward the map ground rather than by lowering opacity. Four saturated
 * hues painted at similar strength across 594 districts reads as confetti: every
 * district shouts and the ranking becomes invisible. Mixing toward the ground lets
 * the bottom of the distribution recede into the map while the top burns through,
 * which is the only part a minister acts on.
 */
const GROUND: [number, number, number] = [13, 18, 25];

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function rampColour(hex: string, v: number, boost = 1): string {
  // Steep gamma: without it the middle of the distribution dominates the frame.
  const t = Math.min(1, Math.pow(Math.max(v, 0), 2.1) * boost);
  const [r, g, b] = hexToRgb(hex);
  const mix = (c: number, i: number) => Math.round(GROUND[i] + (c - GROUND[i]) * (0.06 + t * 0.94));
  return `rgb(${mix(r, 0)},${mix(g, 1)},${mix(b, 2)})`;
}

export function formatCompact(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
  return String(n);
}
