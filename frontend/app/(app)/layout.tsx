"use client";

import { FocusDeckShell } from "@/components/layout/FocusDeckShell";

// Gemeinsames Layout für ALLE authentifizierten App-Routen (Focus-Deck-
// Auftrag, Slice 2). Next.js mountet ein Layout nicht neu, wenn zwischen
// Geschwister-Routen darunter gewechselt wird — genau das ist der
// Mechanismus, der die Jarvis-Rail (und damit die Konversation) über
// Settings -> Projects -> Daily Plan -> Operator -> Jarvis hinweg am Leben
// hält, ganz ohne eigenen State-Manager. Login/Signup liegen bewusst
// außerhalb dieser Route-Gruppe (app/login, app/signup) und bekommen diese
// Shell nicht.
export default function AuthenticatedAppLayout({ children }: { children: React.ReactNode }) {
  return <FocusDeckShell>{children}</FocusDeckShell>;
}
