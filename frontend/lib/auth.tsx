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
import { setUserLanguage } from "@/lib/utils";
import type { Lang } from "@/lib/i18n";

interface AuthContextValue {
  bootstrapError: string | null;
  bootstrapped: boolean;
  language: Lang;
  loading: boolean;
  session: Session | null;
  sessionExpired: boolean;
  user: User | null;
  setLanguage: (lang: Lang) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Returns true when the error message indicates the Supabase token is
 * invalid or revoked — e.g. deleted account, expired refresh token,
 * or a session that pre-dates a password reset.
 * Only matches auth-layer errors, not workspace-setup failures.
 */
function isStaleSessionError(message: string): boolean {
  const lower = message.toLowerCase();
  return (
    lower === "invalid or expired session" ||
    (lower.includes("invalid") && lower.includes("session")) ||
    (lower.includes("expired") && lower.includes("session")) ||
    lower.includes("jwt expired")
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootstrapped, setBootstrapped] = useState(false);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [language, _setLanguage] = useState<Lang>("en");

  /** Update language in React state and sync to localStorage so formatDate stays correct. */
  const setLanguage = useCallback((lang: Lang) => {
    _setLanguage(lang);
    setUserLanguage(lang);
  }, []);

  const bootstrap = useCallback(
    async (activeSession: Session | null) => {
      if (!activeSession) {
        setBootstrapped(false);
        setBootstrapError(null);
        return;
      }

      try {
        const result = await api.auth.bootstrap();
        // Read language from profile; fall back to "en" for any unknown value.
        const profileLang = result.profile?.language;
        setLanguage(profileLang === "de" ? "de" : "en");
        setBootstrapped(true);
        setBootstrapError(null);
        setSessionExpired(false);
      } catch (error) {
        const msg = error instanceof Error ? error.message : "Auth setup failed";

        if (isStaleSessionError(msg)) {
          // Stale/deleted/revoked token — sign out silently.
          // onAuthStateChange SIGNED_OUT will fire and null out the session;
          // ProtectedRoute will then redirect to /login?reason=session_expired.
          setSessionExpired(true);
          setBootstrapped(false);
          setBootstrapError(null);
          await supabase.auth.signOut();
        } else {
          // Non-auth failure (e.g. workspace setup error, network blip).
          setBootstrapped(false);
          setBootstrapError(msg);
        }
      }
    },
    [setLanguage]
  );

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

      if (event === "SIGNED_IN") {
        // Reset any previous session-expired flag on a fresh login.
        setSessionExpired(false);
        setLoading(true);
        bootstrap(nextSession).finally(() => setLoading(false));
      }

      if (event === "SIGNED_OUT") {
        setBootstrapped(false);
        setBootstrapError(null);
        // sessionExpired is intentionally NOT reset here — ProtectedRoute reads
        // it to append reason=session_expired to the redirect URL.
        // It is cleared on the next successful SIGNED_IN / bootstrap.
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
      language,
      loading,
      session,
      sessionExpired,
      user: session?.user ?? null,
      setLanguage,
      signOut: async () => {
        await supabase.auth.signOut();
        setSession(null);
        setBootstrapped(false);
        setBootstrapError(null);
        setSessionExpired(false);
      },
    }),
    [bootstrapError, bootstrapped, language, loading, session, sessionExpired, setLanguage]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { bootstrapError, bootstrapped, loading, sessionExpired, signOut, user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      const reason = sessionExpired ? "&reason=session_expired" : "";
      router.replace(`/login?next=${encodeURIComponent(pathname)}${reason}`);
    }
  }, [loading, pathname, router, sessionExpired, user]);

  if (loading || (user && !bootstrapped)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
        {bootstrapError ? (
          // Non-auth setup failure — give the user an explicit escape.
          <div className="flex max-w-md flex-col gap-3">
            <div className="rounded-lg border border-red-800 bg-red-950 px-4 py-3 text-sm text-red-300">
              {bootstrapError}
            </div>
            <button
              onClick={signOut}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              Sign out and try again
            </button>
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
