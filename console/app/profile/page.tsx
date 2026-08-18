'use client';

/* Profile — the details a signed-in official can fill in.
 *
 * Fields are chosen to be the ones a CIVOS deployment would actually use: which
 * organisation the person belongs to and which state/district they work on, so a
 * future version can scope the console to their jurisdiction. Nothing here is
 * required — an empty profile still gets full access, because a mandatory form is
 * the same barrier the product spends its whole argument objecting to.
 *
 * Stored in Firestore under profiles/{uid}. Rules restrict each document to its
 * owner (firestore.rules).
 */

import Link from 'next/link';
import { useEffect, useState } from 'react';
import RequireAuth from '@/components/RequireAuth';
import ThemeToggle from '@/components/ThemeToggle';
import { EMPTY_PROFILE, useAuth, type Profile } from '@/lib/auth';
import '../login/auth.css';

const ROLES = [
  '',
  'District officer',
  'State government',
  'Central ministry',
  'Analyst / researcher',
  'Civil society',
  'Evaluator / reviewer',
  'Other',
];

function ProfileInner() {
  const { user, profile, saveProfile, signOut } = useAuth();
  const [form, setForm] = useState<Profile>(EMPTY_PROFILE);
  const [states, setStates] = useState<string[]>([]);
  const [districts, setDistricts] = useState<{ code: string; name: string }[]>([]);
  const [all, setAll] = useState<Record<string, { code: string; name: string }[]>>({});
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (profile) setForm({ ...EMPTY_PROFILE, ...profile });
  }, [profile]);

  // Same government district list the citizen intake uses — one source, so a
  // profile cannot name a district the rest of the product does not know.
  useEffect(() => {
    fetch('/data/india-districts.json')
      .then((r) => r.json())
      .then((d: Record<string, { code: string; name: string }[]>) => {
        setAll(d);
        setStates(Object.keys(d).sort());
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setDistricts(form.state ? all[form.state] ?? [] : []);
  }, [form.state, all]);

  const set = (k: keyof Profile) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setOk(null);
    setErr(null);
    try {
      await saveProfile(form);
      setOk('Profile saved.');
    } catch {
      setErr('Could not save. Check your connection and try again.');
    } finally {
      setBusy(false);
    }
  }

  const initial = (form.fullName || user?.email || '?').trim().charAt(0).toUpperCase();

  return (
    <div className="auth">
      <header className="auth-head">
        <Link href="/" className="wordmark" aria-label="CIVOS home">
          <b className="display">CIVOS</b>
          <span className="instance mono">IN</span>
        </Link>
        <div className="auth-head-right">
          <ThemeToggle />
          <Link href="/console" className="btn-ghost">
            Console ↗
          </Link>
          <button className="btn-ghost" type="button" onClick={() => signOut()}>
            Sign out
          </button>
        </div>
      </header>

      <main className="auth-main">
        <div className="auth-card profile-card">
          <h1>Your profile</h1>
          <p className="auth-sub">
            Every field is optional. CIVOS uses the organisation and jurisdiction to scope what a
            future version shows you first — nothing here gates access.
          </p>

          <div className="profile-id">
            <span className="profile-avatar">{initial}</span>
            <div>
              <div className="em">{user?.email}</div>
              <div className="meta">
                {user?.providerData?.[0]?.providerId === 'google.com' ? 'Google account' : 'Email account'}
                {user?.emailVerified ? ' · verified' : ' · unverified'}
              </div>
            </div>
          </div>

          {ok && <div className="auth-msg ok">{ok}</div>}
          {err && <div className="auth-msg">{err}</div>}

          <form onSubmit={submit}>
            <div className="profile-grid">
              <div className="field">
                <label htmlFor="fullName">Full name</label>
                <input id="fullName" value={form.fullName} onChange={set('fullName')} autoComplete="name" />
              </div>

              <div className="field">
                <label htmlFor="role">Role</label>
                <select id="role" value={form.role} onChange={set('role')}>
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r || 'Select…'}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label htmlFor="organisation">Organisation / department</label>
                <input
                  id="organisation"
                  value={form.organisation}
                  onChange={set('organisation')}
                  placeholder="Ministry of Jal Shakti"
                />
              </div>

              <div className="field">
                <label htmlFor="phone">Phone (optional)</label>
                <input id="phone" value={form.phone} onChange={set('phone')} autoComplete="tel" inputMode="tel" />
              </div>

              <div className="field">
                <label htmlFor="state">State / UT</label>
                <select id="state" value={form.state} onChange={set('state')}>
                  <option value="">Select…</option>
                  {states.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label htmlFor="district">District</label>
                <select id="district" value={form.district} onChange={set('district')} disabled={!form.state}>
                  <option value="">{form.state ? 'Select…' : 'Select a state first'}</option>
                  {districts.map((d) => (
                    <option key={d.code} value={d.name}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button className="auth-submit" type="submit" disabled={busy}>
              {busy ? 'Saving…' : 'Save profile'}
            </button>
          </form>

          <div className="auth-alt">
            Stored against your account only. CIVOS never stores a citizen&apos;s identity — see the
            privacy section of the <Link href="/">landing page</Link>.
          </div>
        </div>
      </main>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <RequireAuth>
      <ProfileInner />
    </RequireAuth>
  );
}
