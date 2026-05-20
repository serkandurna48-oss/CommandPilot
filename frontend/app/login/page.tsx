"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Lock } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase";
import { t } from "@/lib/i18n";
import { getUserLanguage } from "@/lib/utils";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";
  const reason = searchParams.get("reason");
  const { user, loading } = useAuth();
  const lang = getUserLanguage();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, next, router, user]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    setSubmitting(false);
    if (authError) {
      setError(authError.message);
      return;
    }

    router.replace(next);
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-6">
      <Card variant="elevated" className="w-full max-w-md">
        <CardHeader>
          <div className="mb-3 h-10 w-10 rounded-md bg-brand-600 flex items-center justify-center">
            <Lock className="h-5 w-5 text-white" />
          </div>
          <CardTitle>{t("login.title", lang)}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {reason === "session_expired" && !error && (
              <div className="rounded-lg bg-amber-950 border border-amber-800 px-4 py-3 text-amber-300 text-sm">
                {t("login.session_expired", lang)}
              </div>
            )}
            {error && (
              <div className="rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-red-300 text-sm">
                {error}
              </div>
            )}
            <Input
              label={t("login.email", lang)}
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label={t("login.password", lang)}
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" loading={submitting} className="w-full">
              {t("login.submit", lang)}
            </Button>
          </form>
          <p className="mt-4 text-sm text-slate-500">
            {t("login.new_here", lang)}{" "}
            <Link href="/signup" className="text-brand-400 hover:text-brand-300">
              {t("login.create_account", lang)}
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
