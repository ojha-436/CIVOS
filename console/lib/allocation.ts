/* The allocator's data contract, mirroring core/allocation/allocator.py.
 *
 * The solve happens server-side rather than in the browser, unlike the SPEC §8
 * priority score. That split is deliberate: priority is five multiplications on
 * a row the browser already holds, so it can run per keystroke on 641 rows. The
 * allocation is a constrained search over ~6,400 candidates with two repair
 * passes, and it has to agree exactly with what a dossier later cites. One
 * implementation, server-side, is the only way those two things stay true at
 * once.
 */

export interface Award {
  id: string;
  code: string;
  district: string | null;
  state: string;
  sector: string;
  scheme: string;
  units: number;
  cost: number;
  priority: number;
  confidence: number;
  beneficiaries: number | null;
  deprived: boolean;
  rationale: string;
}

export interface ConstraintStatus {
  name: string;
  satisfied: boolean;
  /** Prose for a terminal. The UI composes its own from the numbers below. */
  detail: string;
  value: number | null;
  limit: number | null;
  /** 'currency' or 'count' — which formatter to reach for. */
  kind: string;
}

export interface AllocationSummary {
  funded: number;
  verify: number;
  outreach: number;
  dropped: number;
  funded_cost: number;
  verify_cost: number;
  outreach_cost: number;
  total_cost: number;
  beneficiaries: number;
  cost_per_beneficiary: number | null;
  infeasible: string[];
  optimality_note: string;
}

export interface AllocationResult {
  summary: AllocationSummary;
  constraints: ConstraintStatus[];
  funded: Award[];
  verify: Award[];
  outreach: Award[];
  dropped_sample: { id: string; reason: string }[];
  dropped_total: number;
}

export interface Dials {
  budget: number;
  sector_cap_share: number;
  equity_floor_share: number;
  min_groups: number;
  outreach_reserve_share: number;
  verify_reserve_share: number;
  confidence_floor: number;
  sector?: string | null;
}

export const DEFAULT_DIALS: Dials = {
  budget: 4_000_000_000,
  sector_cap_share: 0.4,
  equity_floor_share: 0.3,
  min_groups: 8,
  outreach_reserve_share: 0.05,
  verify_reserve_share: 0.03,
  confidence_floor: 55,
  sector: null,
};

export const LANES = {
  fund: {
    label: 'Fund',
    hint: 'Corroborated need, confidence above the floor. Money moves.',
    colour: 'var(--q-act)',
  },
  verify: {
    label: 'Verify first',
    hint: 'Worth funding, but the evidence is thin. Send somebody to look.',
    colour: 'var(--q-gap)',
  },
  outreach: {
    label: 'Outreach',
    hint: 'Severe measured deficit and nobody has spoken. Go and ask — never auto-fund.',
    colour: 'var(--q-silent)',
  },
} as const;

export type LaneKey = keyof typeof LANES;

export async function solve(dials: Dials, signal?: AbortSignal): Promise<AllocationResult> {
  const res = await fetch('/api/allocate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(dials),
    signal,
  });
  if (!res.ok) throw new Error(`allocate ${res.status}`);
  return (await res.json()) as AllocationResult;
}
