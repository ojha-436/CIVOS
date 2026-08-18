'use client';

/* Client-side route guard for /console and /report.
 *
 * Honest about what this is: a client-side guard controls the UI, not the data.
 * Anything that must actually be protected has to be enforced server-side — for
 * CIVOS that means Firestore security rules (firestore.rules) and, when the
 * intelligence layer lands, an ID-token check on the API. Written down because a
 * redirect that looks like security and is not is worse than no redirect.
 *
 * The `next` parameter matters: a policymaker who lands on a deep console link
 * and gets bounced to sign in should arrive back where they were pointed, not at
 * the home page.
 */

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { useAuth } from '@/lib/auth';

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Waiting on `loading` is what stops a signed-in user being bounced on every
    // hard refresh, before Firebase has restored the session.
    if (!loading && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname || '/console')}`);
    }
  }, [loading, user, router, pathname]);

  if (loading || !user) {
    return (
      <div className="boot">
        <div className="boot-inner">
          <div className="display">CIVOS</div>
          <div className="label">{loading ? 'Restoring session' : 'Redirecting to sign in'}</div>
          <div className="sweep">
            <i />
          </div>
          {!loading && !user && (
            <div style={{ marginTop: 18 }}>
              <Link href="/login" className="btn-ghost">
                Sign in
              </Link>
            </div>
          )}
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
