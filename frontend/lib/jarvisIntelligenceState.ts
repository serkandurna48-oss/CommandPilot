// Jarvis Intelligence States — a presentation-only concept, not a backend
// agent system. It never holds real state itself; it's derived fresh on
// every render from what JarvisChat already tracks (route/entity context,
// the message list, the loading flag, and whether the last real response
// carried suggested_actions). Five modes, no transitions to manage:
//
//   idle     — reserved; unreachable today because JarvisContextInfo is
//              synchronous (built from data the page already has), so there
//              is never a moment with no context to show. Kept in the type
//              so a future async context source has a place to land.
//   context  — nothing asked yet: show the context snapshot + quick actions.
//   thinking — a request is in flight: show a working-state label.
//   answer   — the latest real reply, rendered as analysis.
//   actions  — same as answer, but the reply came with real Suggested
//              Actions to decide on.
export type JarvisIntelligenceMode = "idle" | "context" | "thinking" | "answer" | "actions";

export function deriveJarvisIntelligenceMode(params: {
  hasMessages: boolean;
  loading: boolean;
  lastAssistantHasActions: boolean;
}): JarvisIntelligenceMode {
  if (params.loading) return "thinking";
  if (!params.hasMessages) return "context";
  if (params.lastAssistantHasActions) return "actions";
  return "answer";
}
