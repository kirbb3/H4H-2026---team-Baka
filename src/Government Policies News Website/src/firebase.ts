import { initializeApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
} from "firebase/auth";

// TODO: Replace with your Firebase project config from:
// Firebase Console → Project Settings → Your apps → Web app → Config
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY ?? "",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? "",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID ?? "",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET ?? "",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID ?? "",
  appId: import.meta.env.VITE_FIREBASE_APP_ID ?? "",
};

const isConfigured = !!firebaseConfig.apiKey;

const app = isConfigured ? initializeApp(firebaseConfig) : null;
export const auth = isConfigured && app ? getAuth(app) : null;

const googleProvider = new GoogleAuthProvider();

export const signInWithGoogle = () => {
  if (!auth) { alert("Firebase is not configured yet. Add your keys to .env.local"); return Promise.resolve(null); }
  return signInWithPopup(auth, googleProvider);
};
export const signOutUser = () => {
  if (!auth) return Promise.resolve();
  return signOut(auth);
};

export const signInWithEmail = (email: string, password: string) => {
  if (!auth) { alert("Firebase is not configured yet. Add your keys to .env.local"); return Promise.resolve(null); }
  return signInWithEmailAndPassword(auth, email, password);
};

export const signUpWithEmail = (email: string, password: string) => {
  if (!auth) { alert("Firebase is not configured yet. Add your keys to .env.local"); return Promise.resolve(null); }
  return createUserWithEmailAndPassword(auth, email, password);
};
