'use client';

/* Signed-in identity in the header: who you are, profile, sign out.
 *
 * Deliberately a plain details/summary rather than a custom dropdown — it gets
 * keyboard behaviour, focus handling and click-outside for free, and this is not
 * a control that benefits from bespoke interaction.
 */

import Link from 'next/link';
import { useAuth } from '@/lib/auth';

export default function AccountMenu() {
  const { user, profile, signOut } = useAuth();
  if (!user) return null;

  const name = profile?.fullName || user.displayName || user.email || 'Account';
  const initial = name.trim().charAt(0).toUpperCase();

  return (
    <details className="acct">
      <summary aria-label={`Account: ${name}`}>
        <span className="acct-av">{initial}</span>
      </summary>
      <div className="acct-menu">
        <div className="acct-who">
          <b>{name}</b>
          <span>{user.email}</span>
        </div>
        <Link href="/profile">Profile</Link>
        <button type="button" onClick={() => signOut()}>
          Sign out
        </button>
      </div>
    </details>
  );
}
