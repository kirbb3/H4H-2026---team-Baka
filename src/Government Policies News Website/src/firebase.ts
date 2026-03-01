// firebase.ts
// Initialises the Firebase client SDK and exports auth helper functions.
// All VITE_FIREBASE_* values must be set in a .env.local file in the
// "Government Policies News Website" directory — they are injected at
// build time by Vite and are safe to expose publicly (they identify the
// Firebase project, not a secret key).

import { initializeApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
} from "firebase/auth";

// Firebase project config — values come from environment variables so the
// same codebase works across dev / staging / prod without code changes.
const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY ?? "",
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? "",
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID ?? "",
  storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET ?? "",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID ?? "",
  appId:             import.meta.env.VITE_FIREBASE_APP_ID ?? "",
};

// Guard: if no API key is present (e.g. env vars not set up yet), skip
// initialisation so the app loads without crashing in unconfigured envs.
const isConfigured = !!firebaseConfig.apiKey;

const app = isConfigured ? initializeApp(firebaseConfig) : null;

// `auth` is exported so AuthContext can subscribe to auth-state changes.
// It will be null when Firebase is not configured, and all helper functions
// below handle that case gracefully with an alert.
export const auth = isConfigured && app ? getAuth(app) : null;

// Google OAuth provider — used with a popup so the user never leaves the page.
const googleProvider = new GoogleAuthProvider();

/** Opens a Google sign-in popup and returns the credential result. */
export const signInWithGoogle = () => {
  if (!auth) { alert("Firebase is not configured yet. Add your keys to .env.local"); return Promise.resolve(null); }
  return signInWithPopup(auth, googleProvider);
};

/** Signs the current user out and clears the auth session. */
export const signOutUser = () => {
  if (!auth) return Promise.resolve();
  return signOut(auth);
};

/** Signs in an existing user with their email address and password. */
export const signInWithEmail = (email: string, password: string) => {
  if (!auth) { alert("Firebase is not configured yet. Add your keys to .env.local"); return Promise.resolve(null); }
  return signInWithEmailAndPassword(auth, email, password);
};

/** Creates a brand-new account with an email address and password. */
export const signUpWithEmail = (email: string, password: string) => {
  if (!auth) { alert("Firebase is not configured yet. Add your keys to .env.local"); return Promise.resolve(null); }
  return createUserWithEmailAndPassword(auth, email, password);
};
