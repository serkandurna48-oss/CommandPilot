"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { Session, User } from "@supabase/supabase-js";
import { usePathname, useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { api } from "@/lib/api";

interface AuthContextValue {
  bootstrapError: string | null;
  bootstrapped: boolean;
  loading: boolean;
  session: Session | null;
  user: User | null;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootstrapped, setBootstrapped] = useState(false);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  const bootstrap = useCallback(async (activeSession: Session | null) => {
    if (!activeSession) {
      setBootstrapped(false);
      setBootstrapError(null);
      return;
    }

    try {
      await api.auth.bootstrap();
      setBootstrapped(true);
      setBootstrapError(null);
    } catch (error) {
      setBootstrapped(false);
      setBootstrapError(error instanceof Error ? error.message : "Auth setup failed");
    }
  }, []);

  useEffect(() => {
    let alive = true;

    supabase.auth.getSession().then(async ({ data }) => {
      if (!alive) return;
      setSession(data.session);
      try {
        await bootstrap(data.session);
      } finally {
        if (alive) setLoading(false);
      }
    });

    const { data: listener } = supabase.auth.onAuthStateChange((event, nextSession) => {
      setSession(nextSession);
      // Only run bootstrap on sign-in — token refreshes don't need a new workspace setup
      if (event === "SIGNED_IN") {
        setLoading(true);
        bootstrap(nextSession).finally(() => setLoading(false));
      }
      if (event === "SIGNED_OUT") {
        setBootstrapped(false);
        setBootstrapError(null);
      }
    });

    return () => {
      alive = false;
      listener.subscription.unsubscribe();
    };
  }, [bootstrap]);

  const value = useMemo<AuthContextValue>(
    () => ({
      bootstrapError,
      bootstrapped,
      loading,
      session,
      user: session?.user ?? null,
      signOut: async () => {
        await supabase.auth.signOut();
        setSession(null);
        setBootstrapped(false);
        setBootstrapError(null);
      },
    }),
    [bootstrapError, bootstrapped, loading, session]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { bootstrapError, bootstrapped, loading, user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, pathname, router, user]);

  if (loading || (user && !bootstrapped)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
        {bootstrapError ? (
          <div className="max-w-md rounded-lg border border-red-800 bg-red-950 px-4 py-3 text-sm text-red-300">
            {bootstrapError}
          </div>
        ) : (
          <div className="h-8 w-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        )}
      </div>
    );
  }

  if (!user) return null;

  return <>{children}</>;
}
