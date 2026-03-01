import { createContext, useContext, useEffect, useState } from "react";
import type { User } from "firebase/auth";
import { onAuthStateChanged } from "firebase/auth";
import { auth, signInWithGoogle, signOutUser, signInWithEmail, signUpWithEmail } from "./firebase";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  authError: string | null;
  signIn: () => Promise<void>;
  signInEmail: (email: string, password: string) => Promise<void>;
  signUpEmail: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    if (!auth) { setLoading(false); return; }
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

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

  const signInEmail = async (email: string, password: string) => {
    setAuthError(null);
    await signInWithEmail(email, password);
  };

  const signUpEmail = async (email: string, password: string) => {
    setAuthError(null);
    await signUpWithEmail(email, password);
  };

  const signOut = async () => { await signOutUser(); };

  return (
    <AuthContext.Provider value={{ user, loading, authError, signIn, signInEmail, signUpEmail, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
