"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { UserPlus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { supabase } from "@/lib/supabase";

export default function SignupPage() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setSubmitting(true);

    const { data, error: authError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          display_name: displayName,
        },
      },
    });

    setSubmitting(false);
    if (authError) {
      setError(authError.message);
      return;
    }

    if (data.session) {
      router.replace("/dashboard");
      return;
    }

    setMessage("Check your email to confirm your account, then log in.");
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-6">
      <Card variant="elevated" className="w-full max-w-md">
        <CardHeader>
          <div className="mb-3 h-10 w-10 rounded-md bg-brand-600 flex items-center justify-center">
            <UserPlus className="h-5 w-5 text-white" />
          </div>
          <CardTitle>Create your CommandPilot account</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-red-300 text-sm">
                {error}
              </div>
            )}
            {message && (
              <div className="rounded-lg bg-emerald-950 border border-emerald-800 px-4 py-3 text-emerald-300 text-sm">
                {message}
              </div>
            )}
            <Input
              label="Name"
              autoComplete="name"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
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
              autoComplete="new-password"
              minLength={8}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" loading={submitting} className="w-full">
              Sign up
            </Button>
          </form>
          <p className="mt-4 text-sm text-slate-500">
            Already have an account?{" "}
            <Link href="/login" className="text-brand-400 hover:text-brand-300">
              Log in
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
