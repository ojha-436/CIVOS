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
  GoogleAuthProvider,
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut as fbSignOut,
  updateProfile as fbUpdateProfile,
  type User,
} from 'firebase/auth';
import { doc, getDoc, serverTimestamp, setDoc } from 'firebase/firestore';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { auth, db } from './firebase';

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
export function authMessage(code: string): string {
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
  };
  return map[code] ?? 'Could not complete that. Please try again.';
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

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
    await signInWithEmailAndPassword(auth, email.trim(), password);
  }, []);

  const signUp = useCallback(async (email: string, password: string, fullName: string) => {
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

  const signInWithGoogle = useCallback(async () => {
    const provider = new GoogleAuthProvider();
    await signInWithPopup(auth, provider);
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
