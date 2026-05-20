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

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";
  const { user, loading } = useAuth();
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
          <CardTitle>Log in to CommandPilot</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-red-300 text-sm">
                {error}
              </div>
            )}
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" loading={submitting} className="w-full">
              Log in
            </Button>
          </form>
          <p className="mt-4 text-sm text-slate-500">
            New here?{" "}
            <Link href="/signup" className="text-brand-400 hover:text-brand-300">
              Create an account
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
