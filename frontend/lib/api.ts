import type {
  CheckinCreate,
  Checkin,
  DailyPlan,
  GeneratePlanRequest,
  ReviewCreate,
  EveningReview,
  RuleCreate,
  UserRule,
} from "@/types";
import { supabase } from "@/lib/supabase";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    let message: string;
    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object" && "message" in detail) {
      message = String(detail.message);
    } else {
      message = res.statusText || "Request failed";
    }
    throw new Error(message);
  }

  return res.json() as Promise<T>;
}

// ─── Check-ins ─────────────────────────────────────────────────────────────────
export const api = {
  auth: {
    bootstrap: () =>
      request<{ user_id: string; workspace_id: string }>("/api/auth/bootstrap", {
        method: "POST",
      }),
  },

  checkins: {
    create: (data: CheckinCreate) =>
      request<Checkin>("/api/checkins", { method: "POST", body: JSON.stringify(data) }),

    get: (id: string) =>
      request<Checkin>(`/api/checkins/${id}`),

    listMine: () =>
      request<Checkin[]>("/api/checkins/me"),
  },

  // ─── Plans ───────────────────────────────────────────────────────────────────
  plans: {
    generate: (data: GeneratePlanRequest) =>
      request<DailyPlan>("/api/plans/generate", { method: "POST", body: JSON.stringify(data) }),

    get: (id: string) =>
      request<DailyPlan>(`/api/plans/${id}`),

    listMine: () =>
      request<DailyPlan[]>("/api/plans/me"),

    latestMine: () =>
      request<DailyPlan>("/api/plans/me/latest"),
  },

  // ─── Reviews ─────────────────────────────────────────────────────────────────
  reviews: {
    create: (data: ReviewCreate) =>
      request<EveningReview>("/api/reviews", { method: "POST", body: JSON.stringify(data) }),

    get: (id: string) =>
      request<EveningReview>(`/api/reviews/${id}`),

    listMine: () =>
      request<EveningReview[]>("/api/reviews/me"),
  },

  // ─── Rules ───────────────────────────────────────────────────────────────────
  rules: {
    create: (data: RuleCreate) =>
      request<UserRule>("/api/rules", { method: "POST", body: JSON.stringify(data) }),

    listMine: () =>
      request<UserRule[]>("/api/rules/me"),

    update: (id: string, data: Partial<RuleCreate>) =>
      request<UserRule>(`/api/rules/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

    delete: (id: string) =>
      request<{ deleted: boolean }>(`/api/rules/${id}`, { method: "DELETE" }),
  },
};
