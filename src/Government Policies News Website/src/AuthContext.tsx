// AuthContext.tsx
// Provides a React context that makes the current Firebase auth state
// (user, loading, errors) and sign-in/out actions available to any
// component in the tree without prop-drilling.
//
// Usage:
//   1. Wrap the app root with <AuthProvider> (done in main.tsx).
//   2. Inside any component, call `const { user, signIn } = useAuth()`.

import { createContext, useContext, useEffect, useState } from "react";
import type { User } from "firebase/auth";
import { onAuthStateChanged } from "firebase/auth";
import { auth, signInWithGoogle, signOutUser, signInWithEmail, signUpWithEmail } from "./firebase";

// Shape of the value exposed through the context.
interface AuthContextType {
  user: User | null;          // currently signed-in Firebase user, or null
  loading: boolean;           // true while we're waiting for Firebase to confirm the session
  authError: string | null;   // last sign-in error message (Google path only)
  signIn: () => Promise<void>;                                      // Google OAuth popup
  signInEmail: (email: string, password: string) => Promise<void>; // email + password sign-in
  signUpEmail: (email: string, password: string) => Promise<void>; // create new account
  signOut: () => Promise<void>;                                     // sign out any method
}

// The context itself — initialised to null so useAuth() can detect
// components that forgot to be wrapped in AuthProvider.
const AuthContext = createContext<AuthContextType | null>(null);

/** Wraps children with the auth context. Place this at the app root. */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);       // starts true; flips to false after first Firebase callback
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    // If Firebase is not configured, skip the listener and stop the loading spinner.
    if (!auth) { setLoading(false); return; }

    // onAuthStateChanged fires immediately with the current user (or null) and
    // then again whenever the user signs in or out.  The returned function
    // unsubscribes when the provider unmounts (avoids memory leaks).
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  // ── Sign-in methods ──────────────────────────────────────────────────────

  /** Google OAuth: opens a popup; errors are stored in authError. */
  const signIn = async () => {
    setAuthError(null);
    try {
      await signInWithGoogle();
    } catch (e: unknown) {
      const msg = (e as { message?: string })?.message ?? String(e);
      setAuthError(msg);
      console.error("Sign-in error:", e);
    }
  };

  /** Email + password sign-in — errors propagate to the caller (UserMenu). */
  const signInEmail = async (email: string, password: string) => {
    setAuthError(null);
    await signInWithEmail(email, password);
  };

  /** Create a new account with email + password — errors propagate to caller. */
  const signUpEmail = async (email: string, password: string) => {
    setAuthError(null);
    await signUpWithEmail(email, password);
  };

  /** Signs out the current user regardless of which method they used to sign in. */
  const signOut = async () => { await signOutUser(); };

  return (
    <AuthContext.Provider value={{ user, loading, authError, signIn, signInEmail, signUpEmail, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook for consuming the auth context inside any component.
 * Throws if used outside of an AuthProvider.
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
