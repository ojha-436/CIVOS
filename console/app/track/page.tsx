'use client';

/* The other half of the loop — what happened to the thing you told us about.
 *
 * Ungated on purpose. Every other surface in this console is behind an account
 * because it shows district-level funding decisions; this one is for the person
 * who filed the report, and asking them to create an account to find out whether
 * anyone read it would defeat the point. It is also the only page here that a
 * citizen is ever expected to open.
 *
 * The token is the whole credential and it is deliberately a weak one: it
 * identifies the need, not the reporter, so what it unlocks is the public status
 * of a public need. There is no record of who filed anything to leak.
 */

import { useState } from 'react';
import Link from 'next/link';
import ThemeToggle from '@/components/ThemeToggle';
import { track, type TrackStatus } from '@/lib/allocation';
import './track.css';

const LANE_TONE: Record<string, string> = {
  fund: 'var(--q-act)',
  outreach: 'var(--q-silent)',
  verify_first: 'var(--q-gap)',
  none: 'var(--q-stable)',
  no_data: 'var(--q-nodata)',
};

export default function TrackPage() {
  const [token, setToken] = useState('');
  const [status, setStatus] = useState<TrackStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function lookup(e: React.FormEvent) {
    e.preventDefault();
    const t = token.trim();
    if (!t) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    track(t)
      .then(setStatus)
      .catch((err) => setError(String(err.message ?? err)))
      .finally(() => setBusy(false));
  }

  return (
    <div className="shell-page">
      <header className="masthead">
        <Link href="/" className="wordmark" aria-label="CIVOS home">
          <b className="display">CIVOS</b>
          <span className="instance mono">IN</span>
        </Link>
        <div className="tagline">Check what happened to a report</div>
        <div className="masthead-right">
          <ThemeToggle />
          <Link href="/report" className="btn-ghost">
            File a report ↗
          </Link>
        </div>
      </header>

      <main className="track">
        <h1 className="display">What happened to your report</h1>
        <p className="track-lede">
          Enter the six-character code you were sent. You can also text it back to the same
          number you reported from — no internet needed.
        </p>

        <form className="track-form" onSubmit={lookup}>
          <label htmlFor="token" className="sr-only">
            Tracking code
          </label>
          <input
            id="token"
            className="mono"
            value={token}
            onChange={(e) => setToken(e.target.value.toUpperCase())}
            placeholder="BCD234"
            maxLength={12}
            autoComplete="off"
            spellCheck={false}
          />
          <button type="submit" disabled={busy || !token.trim()}>
            {busy ? 'Checking…' : 'Check'}
          </button>
        </form>

        {error ? <div className="track-error">{error}</div> : null}

        {status ? (
          <section className="track-result" style={{ ['--tone' as string]: LANE_TONE[status.lane] }}>
            <div className="track-place">
              {status.district}
              {status.state ? <span className="dim"> · {status.state}</span> : null}
              <span className="dim"> · {status.sector.replace(/_/g, ' ')}</span>
            </div>
            <h2 className="display">{status.headline}</h2>
            <p className="track-detail">{status.detail}</p>
            {status.scheme ? (
              <p className="track-scheme">
                Scheme: <b>{status.scheme}</b>
              </p>
            ) : null}
            <p className="track-privacy">{status.privacy}</p>
          </section>
        ) : null}

        <p className="track-note">
          This status is computed from the current funding cycle, not copied from a record
          somebody has to remember to update. If the answer changes, it is because the
          decision changed.
        </p>
      </main>
    </div>
  );
}
