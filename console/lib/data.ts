/* Single fetch point.
 *
 * Today this reads the generated fixture. When the API lands (Phase 3–4) the URL
 * becomes `${API}/aggregate` and the shape does not change, because the fixture
 * was generated to match `Warehouse.aggregate_scores()` in the first place.
 */

import type { Dataset } from './types';

let cache: Promise<Dataset> | null = null;

export function loadDataset(): Promise<Dataset> {
  if (!cache) {
    cache = fetch('/data/scores.json').then((r) => {
      if (!r.ok) throw new Error(`scores.json ${r.status}`);
      return r.json() as Promise<Dataset>;
    });
  }
  return cache;
}
