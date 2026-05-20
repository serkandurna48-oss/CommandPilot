import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "CommandPilot — Personal Operating System",
  description: "Turn chaotic mornings into clear, high-performance daily strategies.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
