'use client';

/* Firebase client — Auth and Firestore.
 *
 * On the config being committed: a Firebase web config is **designed to be
 * public**. It ships inside every client bundle by necessity, and it is an
 * identifier, not a credential — `apiKey` here is a project locator, not a
 * secret. What actually protects the data is Firebase Auth plus Firestore
 * security rules (see firestore.rules), not the obscurity of these strings.
 * Google documents this explicitly. Contrast with TELEGRAM_BOT_TOKEN, which is a
 * real credential and lives only in .env.
 *
 * Environment variables still override every value, so a second deployment (a
 * different ministry, a different country instance) points at its own project
 * without editing code.
 */

import { getApp, getApps, initializeApp, type FirebaseOptions } from 'firebase/app';
import {
  browserLocalPersistence,
  getAuth,
  setPersistence,
  type Auth,
} from 'firebase/auth';
import { getFirestore, type Firestore } from 'firebase/firestore';

const config: FirebaseOptions = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? 'AIzaSyCF_-cfKhH2Ox7sc4cLAsLoOQg4lRyv_Zc',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? 'civos-in.firebaseapp.com',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? 'civos-in',
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET ?? 'civos-in.firebasestorage.app',
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_SENDER_ID ?? '924096812044',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? '1:924096812044:web:821a44c6833798bb420a29',
};

/* Next renders these components on the server too, and initializeApp is not
   idempotent across hot reloads — getApps() keeps it to one instance. */
export const firebaseApp = getApps().length ? getApp() : initializeApp(config);
export const auth: Auth = getAuth(firebaseApp);
export const db: Firestore = getFirestore(firebaseApp);

/* Persist the session in localStorage rather than IndexedDB.
 *
 * The second half of why "Continue with Google" failed. Firebase Auth defaults
 * to IndexedDB, and the OAuth handshake was actually SUCCEEDING — the throw came
 * afterwards, on the write that stores the user:
 *
 *   Error: Database is closing/hidden
 *     at tM._openDb → _withRetries → _withPendingWrite → _set
 *     at setCurrentUser → directlySetCurrentUser
 *
 * Firebase closes its IndexedDB handle when the document is hidden, which is
 * exactly what the sign-in popup does to the opener. The pending write then
 * lands on a closing database and throws. Note it is a bare Error with no
 * `code`, which is why the UI could only say "Could not complete that" — there
 * was no auth/* identifier to map.
 *
 * localStorage is synchronous and has no open/close lifecycle to lose, so the
 * write cannot be orphaned by a visibility change. What it costs: sessions are
 * not shared across browser tabs the way IndexedDB allows, which for a console
 * a policymaker opens in one tab is not a cost worth the failure mode.
 *
 * Awaited before any sign-in call (see lib/auth.tsx) — setPersistence applied
 * after a sign-in has begun does not govern that sign-in.
 */
export const authPersistenceReady: Promise<void> =
  typeof window === 'undefined'
    ? Promise.resolve()
    : setPersistence(auth, browserLocalPersistence).catch((e: unknown) => {
        // Non-fatal: Firebase keeps its default. Sign-in may still work, and a
        // hard failure here would lock out a browser that merely dislikes one
        // storage backend.
        console.warn('[civos] could not set auth persistence to localStorage:', e);
      });
