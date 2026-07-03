import { Sidebar } from "./Sidebar";
import { MobileNav } from "./MobileNav";
import { ProtectedRoute } from "@/lib/auth";

export function AppShell({
  children,
  wide,
}: {
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <ProtectedRoute>
      <div className="flex min-h-screen bg-slate-950 text-slate-100">
        <Sidebar />
        <main className="flex-1 overflow-y-auto pb-16 md:pb-0">
          <div className={
            wide
              ? "w-full px-4 md:px-8 py-6"
              : "max-w-4xl mx-auto px-4 md:px-6 py-8"
          }>
            {children}
          </div>
        </main>
        <MobileNav />
      </div>
    </ProtectedRoute>
  );
}
