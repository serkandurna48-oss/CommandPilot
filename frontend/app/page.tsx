import { redirect } from "next/navigation";

// Root redirects to dashboard. Landing page marketing can go here later.
export default function RootPage() {
  redirect("/dashboard");
}
