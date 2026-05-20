import { Sidebar } from "./Sidebar";
import { MobileNav } from "./MobileNav";
import { ProtectedRoute } from "@/lib/auth";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <div className="flex min-h-screen bg-slate-950 text-slate-100">
        <Sidebar />
        <main className="flex-1 overflow-y-auto pb-16 md:pb-0">
          <div className="max-w-4xl mx-auto px-4 md:px-6 py-8">{children}</div>
        </main>
        <MobileNav />
      </div>
    </ProtectedRoute>
  );
}
