import type {
  CheckinCreate,
  Checkin,
  DailyPlan,
  GeneratePlanRequest,
  ReviewCreate,
  EveningReview,
  RuleCreate,
  UserRule,
  Project,
  ProjectCreate,
  ProjectUpdate,
  JarvisChatRequest,
  JarvisChatResponse,
  JarvisSuggestedActionDecisionRequest,
  JarvisSuggestedActionDecisionResponse,
  JarvisSuggestedActionDecisionListResponse,
} from "@/types";
import { supabase } from "@/lib/supabase";
import type {
  ApiWorkOrder,
  ApiWorkOrderDetail,
  ApiWorkOrderStep,
  ApiAgentRun,
  ApiActivityLogEntry,
  ApiArtifact,
  ApiReviewPackage,
  ApiWorkOrderUpdate,
  ApiWorkOrderStepCreate,
  ApiWorkOrderStepUpdate,
  ApiActivityLogCreate,
  ApiAgentRunCreate,
  ApiAgentRunUpdate,
  ApiArtifactCreate,
  ApiReviewPackageCreate,
} from "@/lib/workOrderMapper";
import { mapWorkOrderCreateToApi, type WorkOrderCreateInput } from "@/lib/workOrderMapper";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  code?: string;
  planId?: string;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;

    if (detail && typeof detail === "object") {
      if ("code" in detail) this.code = String(detail.code);
      if ("plan_id" in detail) this.planId = String(detail.plan_id);
    }
  }
}

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
    } else if (Array.isArray(detail)) {
      // FastAPI/Pydantic validation errors (422) — e.g. the ApprovalScope
      // blocked-action validator — come back as a list of {msg, loc, ...},
      // not a string or {message}. Without this, a 422 rendered as an
      // unhelpful "Unprocessable Entity" instead of the actual reason.
      message = detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : JSON.stringify(d)))
        .join("; ");
    } else if (detail && typeof detail === "object" && "message" in detail) {
      message = String(detail.message);
    } else {
      message = res.statusText || "Request failed";
    }
    throw new ApiError(message, res.status, detail);
  }

  return res.json() as Promise<T>;
}

// ─── Check-ins ─────────────────────────────────────────────────────────────────
export const api = {
  auth: {
    bootstrap: () =>
      request<{ user_id: string; workspace_id: string; profile: { language: string } | null }>(
        "/api/auth/bootstrap",
        { method: "POST" }
      ),
  },

  profile: {
    update: (data: { language: "en" | "de" }) =>
      request<{ language: string }>("/api/auth/profile", {
        method: "PATCH",
        body: JSON.stringify(data),
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

  // ─── Projects ─────────────────────────────────────────────────────────────────
  projects: {
    listMine: () =>
      request<Project[]>("/api/projects/me"),

    create: (data: ProjectCreate) =>
      request<Project>("/api/projects", { method: "POST", body: JSON.stringify(data) }),

    update: (id: string, data: ProjectUpdate) =>
      request<Project>(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  },

  // ─── Jarvis (second-brain chat) ────────────────────────────────────────────────
  jarvis: {
    chat: (data: JarvisChatRequest) =>
      request<JarvisChatResponse>("/api/jarvis/chat", { method: "POST", body: JSON.stringify(data) }),

    // JARVIS-C1: a suggested_action from a chat reply is only a proposal —
    // these are the only two calls that can turn one into (or explicitly
    // not into) a real work order.
    confirmSuggestedAction: (data: JarvisSuggestedActionDecisionRequest) =>
      request<JarvisSuggestedActionDecisionResponse>("/api/jarvis/suggested-actions/confirm", {
        method: "POST", body: JSON.stringify(data),
      }),

    rejectSuggestedAction: (data: JarvisSuggestedActionDecisionRequest) =>
      request<JarvisSuggestedActionDecisionResponse>("/api/jarvis/suggested-actions/reject", {
        method: "POST", body: JSON.stringify(data),
      }),

    // Command Layer audit trail — every proposal ever confirmed/rejected.
    listDecisions: () =>
      request<JarvisSuggestedActionDecisionListResponse>("/api/jarvis/suggested-actions/decisions"),
  },

  // ─── Work Orders (Background Dev Team control plane) ───────────────────────────
  // Returns raw snake_case API shapes — callers must run these through the
  // mapXFromApi functions in lib/workOrderMapper.ts before use. Kept separate
  // from the mapping layer so this file stays a pure transport client, like
  // every other resource above.
  workOrders: {
    listMine: () =>
      request<ApiWorkOrder[]>("/api/work-orders/me"),

    get: (id: string) =>
      request<ApiWorkOrderDetail>(`/api/work-orders/${id}`),

    create: (data: WorkOrderCreateInput) =>
      request<ApiWorkOrder>("/api/work-orders", { method: "POST", body: JSON.stringify(mapWorkOrderCreateToApi(data)) }),

    update: (id: string, data: ApiWorkOrderUpdate) =>
      request<ApiWorkOrder>(`/api/work-orders/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

    addStep: (id: string, data: ApiWorkOrderStepCreate) =>
      request<ApiWorkOrderStep>(`/api/work-orders/${id}/steps`, { method: "POST", body: JSON.stringify(data) }),

    updateStep: (id: string, stepId: string, data: ApiWorkOrderStepUpdate) =>
      request<ApiWorkOrderStep>(`/api/work-orders/${id}/steps/${stepId}`, { method: "PATCH", body: JSON.stringify(data) }),

    addActivityLog: (id: string, data: ApiActivityLogCreate) =>
      request<ApiActivityLogEntry>(`/api/work-orders/${id}/activity-log`, { method: "POST", body: JSON.stringify(data) }),

    addAgentRun: (id: string, data: ApiAgentRunCreate) =>
      request<ApiAgentRun>(`/api/work-orders/${id}/agent-runs`, { method: "POST", body: JSON.stringify(data) }),

    updateAgentRun: (id: string, runId: string, data: ApiAgentRunUpdate) =>
      request<ApiAgentRun>(`/api/work-orders/${id}/agent-runs/${runId}`, { method: "PATCH", body: JSON.stringify(data) }),

    addArtifact: (id: string, data: ApiArtifactCreate) =>
      request<ApiArtifact>(`/api/work-orders/${id}/artifacts`, { method: "POST", body: JSON.stringify(data) }),

    upsertReviewPackage: (id: string, data: ApiReviewPackageCreate) =>
      request<ApiReviewPackage>(`/api/work-orders/${id}/review-package`, { method: "PUT", body: JSON.stringify(data) }),
  },

  // ─── Runner connections (guided pairing, 23.09.2026) ───────────────────────────
  // Replaces "copy a Supabase session token out of browser DevTools" for
  // scripts/run_work_order_daemon.py — approve/list/revoke run through the
  // user's normal session (auth handled by request() like everything else
  // above); request/poll are called by the runner itself, never from this
  // frontend client, hence no wrappers for those two here.
  runnerConnections: {
    listMine: () =>
      request<RunnerConnection[]>("/api/runner-connections"),

    approve: (data: { user_code: string; label?: string }) =>
      request<RunnerConnection>("/api/runner-connections/pairing/approve", {
        method: "POST", body: JSON.stringify(data),
      }),

    revoke: (id: string) =>
      request<{ revoked: boolean }>(`/api/runner-connections/${id}/revoke`, { method: "POST" }),
  },
};

export interface RunnerConnection {
  id: string;
  label: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}
