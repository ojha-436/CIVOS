/* The console's data contract.
 *
 * This mirrors `Warehouse.aggregate_scores()` in core/interfaces/warehouse.py.
 * When Phase 4 lands, the fetch in lib/data.ts points at the API instead of the
 * fixture and nothing else in the console changes. That is the entire reason the
 * console was built before the data layer.
 */

export type QuadrantKey = 'act_now' | 'silent_need' | 'expectation_gap' | 'stable';

export interface Row {
  code: string;
  sector: string;
  signals: number;
  needs: number;
  languages: number;
  images: number;
  /** DemandIndex — percentile-normalised raw demand, 0–100 */
  demand: number;
  /** DeficitIndex — normalised official deprivation, 0–100 */
  deficit: number;
  /** Signals per 1,000 population */
  participation: number;
  /** EvidenceStrength — share of needs backed by >= 1 photo */
  evidence: number;
  /** ARIMA_PLUS 90-day slope */
  forecast: number;
  suppressed: boolean;
  voice_correction: number;
  adjusted_demand: number;
  silence_gap: number;
  quadrant: QuadrantKey;
  /** Indices into quote_pool[sector] */
  quotes: number[];
  assets: { type: string; flag: string; severity: number }[];
}

export interface District {
  code: string;
  name: string;
  state: string;
  lon: number;
  lat: number;
  population: number;
}

export interface Scheme {
  name: string;
  ministry: string;
  eligibility: string;
  unit: string;
  unit_cost_inr: number;
}

export interface Sector {
  key: string;
  label: string;
  short: string;
  indicator: string;
  source: string;
  year: number;
  schemes: Scheme[];
}

export interface Quote {
  lang: string;
  original: string;
  english: string;
}

export interface Dataset {
  meta: {
    generated_at: string;
    instance: string;
    provenance: Record<string, string>;
    median_participation_rate: number;
    counts: { districts: number; rows: number };
  };
  quote_pool: Record<string, Quote[]>;
  sectors: Sector[];
  districts: District[];
  rows: Row[];
}

export interface Weights {
  w1: number; // AdjustedDemand
  w2: number; // DeficitIndex
  w3: number; // max(SilenceGap, 0)
  w4: number; // ForecastGrowth
  w5: number; // EvidenceStrength
}

export const QUADRANTS: Record<
  QuadrantKey,
  { label: string; colour: string; blurb: string }
> = {
  act_now: {
    label: 'Act Now',
    colour: 'var(--q-act)',
    blurb: 'Corroborated need — citizens and official data agree. Fund it.',
  },
  silent_need: {
    label: 'Silent Need',
    colour: 'var(--q-silent)',
    blurb: 'Severe deficit, no citizen voice. Dispatch outreach — never auto-fund.',
  },
  expectation_gap: {
    label: 'Expectation Gap',
    colour: 'var(--q-gap)',
    blurb: 'Complaints exceed measured deficit. Your dataset may be stale.',
  },
  stable: {
    label: 'Stable',
    colour: 'var(--q-stable)',
    blurb: 'No action indicated.',
  },
};
