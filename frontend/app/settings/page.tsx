"use client";

import { AppShell } from "@/components/layout/AppShell";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const { signOut, user } = useAuth();

  return (
    <AppShell>
      <Header
        title="Settings"
        subtitle="Account, preferences, and integrations."
      />

      <div className="space-y-4">
        <Card>
          <CardHeader><CardTitle>Account</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Signed in as</p>
              <p className="text-slate-300 text-sm">{user?.email}</p>
              <p className="text-slate-600 font-mono text-xs mt-1">{user?.id}</p>
            </div>
            <Button variant="secondary" size="sm" onClick={() => signOut()}>
              Sign out
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Preferences</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Language</p>
              <p className="text-slate-400 text-sm">German (DE) - configurable per user in future version</p>
            </div>
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">AI Model</p>
              <p className="text-slate-400 text-sm">GPT-4o - set in backend .env</p>
            </div>
          </CardContent>
        </Card>

        <Card variant="bordered">
          <CardContent className="py-4">
            <p className="text-slate-500 text-sm">
              Full settings (timezone, language, notification preferences, team access) coming in v0.2.
            </p>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
