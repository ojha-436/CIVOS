'use client';

/* Authentication and profile state for the whole console.
 *
 * Scope decision, recorded because it cuts against something the product says
 * elsewhere: BOTH the policymaker console and the WEB citizen intake require an
 * account. That was an explicit product decision on 18 Aug 2026.
 *
 * It has a cost worth naming. CIVOS's argument is that the poorest, least
 * connected citizens cannot navigate a grievance process, so every barrier
 * between a citizen and a report excludes exactly the people the product exists
 * to reach. A login is such a barrier.
 *
 * What keeps the argument intact is the Telegram channel: `@Civos_in_bot` takes
 * voice, text and photographs with **no CIVOS account at all**, because Telegram
 * is the identity layer. So the accessibility floor still exists — it just runs
 * through the messaging channel rather than the web form, and the copy on the
 * landing page now says exactly that instead of claiming the web form needs no
 * account.
 */

import {
  createUserWithEmailAndPassword,
  getRedirectResult,
  GoogleAuthProvider,
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
  signOut as fbSignOut,
  updateProfile as fbUpdateProfile,
  type User,
} from 'firebase/auth';
import { doc, getDoc, serverTimestamp, setDoc } from 'firebase/firestore';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { auth, authPersistenceReady, db } from './firebase';

export interface Profile {
  fullName: string;
  role: string;
  organisation: string;
  state: string;
  district: string;
  phone: string;
  updatedAt?: unknown;
}

export const EMPTY_PROFILE: Profile = {
  fullName: '',
  role: '',
  organisation: '',
  state: '',
  district: '',
  phone: '',
};

interface AuthState {
  user: User | null;
  profile: Profile | null;
  /** True until Firebase has reported the initial auth state. Guards must wait on
   *  this, or a signed-in user is bounced to /login on every hard refresh. */
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  saveProfile: (p: Profile) => Promise<void>;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

/** Firebase error codes are not user-facing English. */
export function authMessage(code: string, fallbackDetail?: string): string {
  const map: Record<string, string> = {
    'auth/invalid-email': 'That does not look like an email address.',
    'auth/missing-password': 'Enter a password.',
    'auth/weak-password': 'Use at least six characters.',
    'auth/email-already-in-use': 'An account already exists for that email. Try signing in.',
    'auth/invalid-credential': 'Email or password is incorrect.',
    'auth/user-not-found': 'No account for that email.',
    'auth/wrong-password': 'Email or password is incorrect.',
    'auth/too-many-requests': 'Too many attempts. Wait a minute and try again.',
    'auth/popup-closed-by-user': 'Sign-in window closed before finishing.',
    'auth/popup-blocked': 'Your browser blocked the sign-in window. Allow popups and retry.',
    // The one a reviewer is most likely to hit, so it says what to do about it.
    'auth/operation-not-allowed':
      'Google sign-in is not enabled on this project yet. Use email and password, ' +
      'or enable the Google provider in Firebase Authentication.',
    'auth/unauthorized-domain':
      'This domain is not in the Firebase authorised-domains list.',
    // The popup path fails for reasons that have nothing to do with the project
    // config — a blocked third-party cookie, a severed opener, a cancelled
    // second popup. signInWithGoogle retries these via redirect, so a user
    // should rarely read them; they are mapped because when the retry ALSO
    // fails, an unexplained failure is what the reviewer is left with.
    'auth/cancelled-popup-request': 'Another sign-in window was already open.',
    'auth/internal-error':
      'Google sign-in could not complete in this browser — usually a blocked ' +
      'third-party cookie. Try again, use a normal (non-private) window, or sign ' +
      'in with email and password.',
    'auth/network-request-failed': 'Network error reaching Firebase. Check the connection and retry.',
    'auth/web-storage-unsupported':
      'This browser is blocking the storage Firebase sign-in needs. Allow site data, or use email and password.',
    'auth/account-exists-with-different-credential':
      'An account already exists for that email with a different sign-in method. Sign in with email and password.',
    'auth/configuration-not-found':
      'Firebase Authentication is not configured for this project.',
    'auth/admin-restricted-operation': 'Sign-ups are restricted on this project.',
  };
  /* An unmapped code used to render as a bare "Could not complete that", which
   * is where this function's usefulness ended: the reviewer sees a dead end and
   * whoever is debugging it has nothing to search for. The code now travels with
   * the message. It is a Firebase error identifier, not a secret — it names
   * which precondition failed, never who failed it. */
  if (map[code]) return map[code];
  if (code) return `Could not complete that (${code}). Please try again.`;
  /* Not every failure is a FirebaseError. The one that broke Google sign-in was
   * a bare `Error: Database is closing/hidden` thrown by the IndexedDB
   * persistence layer — no `code` to look up, so this function had nothing to
   * say and the screen showed a dead end. When there is no code, show whatever
   * the throw actually said; a strange sentence a reviewer can search for beats
   * a polished one that identifies nothing. */
  const detail = (fallbackDetail ?? '').trim().slice(0, 120);
  return detail
    ? `Could not complete that: ${detail}`
    : 'Could not complete that. Please try again.';
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  /* Collect the result of a redirect sign-in.
   *
   * `onAuthStateChanged` below picks the session up on its own, so this is not
   * what signs the user in — it is what stops a redirect that FAILED from
   * looking like one the user abandoned. Without it the page comes back signed
   * out, with no error anywhere, which is indistinguishable from the bug this
   * fallback was added to fix. */
  useEffect(() => {
    getRedirectResult(auth).catch((e: unknown) => {
      const code = (e as { code?: string })?.code ?? 'unknown';
      console.warn('[civos] Google redirect sign-in failed:', code, e);
    });
  }, []);

  useEffect(() => {
    return onAuthStateChanged(auth, async (u) => {
      setUser(u);
      if (u) {
        try {
          const snap = await getDoc(doc(db, 'profiles', u.uid));
          setProfile(
            snap.exists()
              ? ({ ...EMPTY_PROFILE, ...(snap.data() as Profile) })
              : { ...EMPTY_PROFILE, fullName: u.displayName ?? '' },
          );
        } catch {
          // Firestore unreachable or rules deny — the session is still valid, so
          // sign-in must not fail just because the profile could not be read.
          setProfile({ ...EMPTY_PROFILE, fullName: u.displayName ?? '' });
        }
      } else {
        setProfile(null);
      }
      setLoading(false);
    });
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    await authPersistenceReady;
    await signInWithEmailAndPassword(auth, email.trim(), password);
  }, []);

  const signUp = useCallback(async (email: string, password: string, fullName: string) => {
    await authPersistenceReady;
    const cred = await createUserWithEmailAndPassword(auth, email.trim(), password);
    const name = fullName.trim();
    if (name) await fbUpdateProfile(cred.user, { displayName: name });
    try {
      await setDoc(doc(db, 'profiles', cred.user.uid), {
        ...EMPTY_PROFILE,
        fullName: name,
        updatedAt: serverTimestamp(),
      });
    } catch {
      /* profile row is created on first save instead */
    }
    // Set the profile state directly, and do not rely on onAuthStateChanged to
    // pick it up. That listener fires the instant the account is created — which
    // is BEFORE updateProfile and setDoc above have completed — so it reads a
    // document that does not exist yet and a displayName that is still null.
    // The visible symptom was the name field arriving empty on /profile straight
    // after signing up.
    setProfile({ ...EMPTY_PROFILE, fullName: name });
  }, []);

  /* Popup first, redirect as the fallback.
   *
   * `signInWithPopup` alone is why "Continue with Google" failed. The project is
   * configured correctly — the Google IdP is enabled and both localhost and the
   * Cloud Run host are in authorisedDomains — but the popup flow depends on
   * things the browser increasingly refuses: a third-party cookie on
   * civos-in.firebaseapp.com, and an opener handle the page is allowed to poll.
   * When either is withheld the SDK throws a code the UI had no mapping for, so
   * the failure surfaced as a generic "Could not complete that" and looked like
   * a broken button rather than a blocked popup.
   *
   * Redirect does not need the opener and survives stricter cookie policies. It
   * costs a full page navigation, which is why it is the fallback and not the
   * default — but a slower sign-in that works beats a faster one that does not.
   * Only popup-environment failures fall through; a genuinely disabled provider
   * or an unauthorised domain would fail identically on redirect, so those are
   * re-thrown for the caller to display.
   */
  const signInWithGoogle = useCallback(async () => {
    await authPersistenceReady;
    const provider = new GoogleAuthProvider();
    try {
      await signInWithPopup(auth, provider);
    } catch (e: unknown) {
      const code = (e as { code?: string })?.code ?? '';
      const popupEnvironmentFailed = [
        'auth/popup-blocked',
        'auth/popup-closed-by-user',
        'auth/cancelled-popup-request',
        'auth/internal-error',
        'auth/web-storage-unsupported',
        'auth/operation-not-supported-in-this-environment',
      ].includes(code);
      if (!popupEnvironmentFailed) throw e;
      // Navigates away; the result is collected by getRedirectResult below.
      await signInWithRedirect(auth, provider);
    }
  }, []);

  const resetPassword = useCallback(async (email: string) => {
    await sendPasswordResetEmail(auth, email.trim());
  }, []);

  const saveProfile = useCallback(
    async (p: Profile) => {
      if (!auth.currentUser) throw new Error('not signed in');
      await setDoc(
        doc(db, 'profiles', auth.currentUser.uid),
        { ...p, updatedAt: serverTimestamp() },
        { merge: true },
      );
      if (p.fullName && p.fullName !== auth.currentUser.displayName) {
        await fbUpdateProfile(auth.currentUser, { displayName: p.fullName });
      }
      setProfile(p);
    },
    [],
  );

  const signOut = useCallback(async () => {
    await fbSignOut(auth);
  }, []);

  return (
    <Ctx.Provider
      value={{ user, profile, loading, signIn, signUp, signInWithGoogle, resetPassword, saveProfile, signOut }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth must be used inside <AuthProvider>');
  return v;
}
