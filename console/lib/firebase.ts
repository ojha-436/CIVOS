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
import { getAuth, type Auth } from 'firebase/auth';
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
