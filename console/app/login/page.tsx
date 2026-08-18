'use client';

/* Sign in / create account, plus Google SSO.
 *
 * One screen with a switch rather than two routes, because a person bounced here
 * from a deep console link should not have to work out which of two pages they
 * need. `?next=` carries them back to where they were pointed.
 */

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import ThemeToggle from '@/components/ThemeToggle';
import { authMessage, useAuth } from '@/lib/auth';
import './auth.css';

function GoogleMark() {
  return (
    <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#4285F4" d="M45.1 24.5c0-1.6-.1-2.8-.4-4H24v7.6h11.8c-.2 2-1.5 4.9-4.4 6.9l-.1.3 6.4 4.9.4.1c4.1-3.8 6.9-9.4 6.9-15.8z" />
      <path fill="#34A853" d="M24 46c5.8 0 10.7-1.9 14.2-5.2l-6.8-5.2c-1.8 1.3-4.3 2.2-7.4 2.2-5.7 0-10.5-3.7-12.2-8.9l-.3.02-6.6 5.1-.1.3C8.2 41 15.5 46 24 46z" />
      <path fill="#FBBC05" d="M11.8 28.9c-.5-1.4-.7-2.9-.7-4.4s.3-3 .7-4.4l-.01-.3-6.7-5.2-.2.1C3.4 17.6 2.6 20.7 2.6 24s.8 6.4 2.3 9.2l6.9-4.3z" />
      <path fill="#EA4335" d="M24 10.7c4 0 6.8 1.7 8.3 3.2l6.1-5.9C34.7 4.6 29.8 2.6 24 2.6 15.5 2.6 8.2 7.6 4.9 14.8l6.9 5.3c1.7-5.2 6.5-9.4 12.2-9.4z" />
    </svg>
  );
}

function LoginInner() {
  const { user, loading, signIn, signUp, signInWithGoogle, resetPassword } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get('next') || '/console';

  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  // Already signed in — nothing to do here.
  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, user, router, next]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setOk(null);
    setBusy(true);
    try {
      if (mode === 'signin') await signIn(email, password);
      else await signUp(email, password, fullName);
      router.replace(mode === 'signup' ? '/profile' : next);
    } catch (e: unknown) {
      const code = (e as { code?: string })?.code ?? '';
      setErr(authMessage(code));
    } finally {
      setBusy(false);
    }
  }

  async function google() {
    setErr(null);
    setBusy(true);
    try {
      await signInWithGoogle();
      router.replace(next);
    } catch (e: unknown) {
      setErr(authMessage((e as { code?: string })?.code ?? ''));
    } finally {
      setBusy(false);
    }
  }

  async function forgot() {
    if (!email.trim()) {
      setErr('Enter your email first, then choose “reset password”.');
      return;
    }
    setErr(null);
    try {
      await resetPassword(email);
      setOk(`Password reset link sent to ${email.trim()}.`);
    } catch (e: unknown) {
      setErr(authMessage((e as { code?: string })?.code ?? ''));
    }
  }

  return (
    <div className="auth">
      <header className="auth-head">
        <Link href="/" className="wordmark" aria-label="CIVOS home">
          <b className="display">CIVOS</b>
          <span className="instance mono">IN</span>
        </Link>
        <div className="auth-head-right">
          <ThemeToggle />
          <Link href="/" className="btn-ghost">
            ← Home
          </Link>
        </div>
      </header>

      <main className="auth-main">
        <div className="auth-card">
          <h1>{mode === 'signin' ? 'Sign in' : 'Create an account'}</h1>
          <p className="auth-sub">
            {mode === 'signin'
              ? 'The policymaker console and the web intake form both need an account.'
              : 'One account covers the console and the web intake form.'}{' '}
            <strong style={{ color: 'var(--paper-2)', fontWeight: 500 }}>
              The Telegram bot needs no account
            </strong>{' '}
            — it takes voice, text and photographs from any citizen without one.
          </p>

          <div className="auth-tabs" data-mode={mode} role="tablist">
            <button type="button" role="tab" aria-selected={mode === 'signin'} onClick={() => setMode('signin')}>
              Sign in
            </button>
            <button type="button" role="tab" aria-selected={mode === 'signup'} onClick={() => setMode('signup')}>
              Sign up
            </button>
          </div>

          {err && <div className="auth-msg">{err}</div>}
          {ok && <div className="auth-msg ok">{ok}</div>}

          <form onSubmit={submit}>
            {mode === 'signup' && (
              <div className="field">
                <label htmlFor="fullName">Full name</label>
                <input
                  id="fullName"
                  autoComplete="name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Prince Kumar Ojha"
                />
              </div>
            )}

            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@ministry.gov.in"
              />
            </div>

            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                required
                minLength={6}
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
              {mode === 'signup' && <div className="field-hint">At least six characters.</div>}
            </div>

            <button className="auth-submit" type="submit" disabled={busy}>
              {busy ? 'Working…' : mode === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <div className="auth-or">or</div>

          <button className="auth-sso" type="button" onClick={google} disabled={busy}>
            <GoogleMark />
            Continue with Google
          </button>

          <div className="auth-alt">
            {mode === 'signin' ? (
              <>
                Forgotten your password?{' '}
                <button type="button" className="auth-link" onClick={forgot}>
                  reset password
                </button>
                .
              </>
            ) : (
              <>Creating an account stores your email and the profile details you choose to add. Nothing else.</>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function LoginPage() {
  // useSearchParams needs a Suspense boundary in the App Router.
  return (
    <Suspense
      fallback={
        <div className="boot">
          <div className="boot-inner">
            <div className="display">CIVOS</div>
            <div className="label">Loading</div>
          </div>
        </div>
      }
    >
      <LoginInner />
    </Suspense>
  );
}
