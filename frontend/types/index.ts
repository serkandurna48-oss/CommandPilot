// ─── Life Areas ────────────────────────────────────────────────────────────────
export type LifeAreaSlug =
  | "work"
  | "study"
  | "business"
  | "sport"
  | "health"
  | "admin"
  | "social"
  | "content"
  | "finance"
  | "personal"
  | string;

export const LIFE_AREA_COLORS: Record<string, string> = {
  work:     "#3b82f6",
  study:    "#8b5cf6",
  business: "#10b981",
  sport:    "#f59e0b",
  health:   "#ef4444",
  admin:    "#6b7280",
  social:   "#ec4899",
  content:  "#f97316",
  finance:  "#14b8a6",
  personal: "#a78bfa",
};

// ─── Check-in ──────────────────────────────────────────────────────────────────
export interface FixedEvent {
  title: string;
  time?: string;
  duration_minutes?: number;
  life_area?: string;
}

export interface CheckinCreate {
  user_id?: string;
  checkin_date?: string;
  wake_time?: string;
  sleep_quality?: number;
  energy_level?: number;
  body_status?: string;
  mood?: string;
  fixed_events: FixedEvent[];
  important_tasks: string[];
  raw_input?: string;
  available_hours?: number;
  day_constraints?: string;
}

export interface Checkin extends CheckinCreate {
  id: string;
  created_at: string;
}

// ─── Daily Plan ────────────────────────────────────────────────────────────────
export type BlockType =
  | "deep_work"
  | "admin"
  | "sport"
  | "break"
  | "social"
  | "learning"
  | "personal"
  | "other";

export interface TimeBlock {
  start_time: string;
  end_time: string;
  title: string;
  description?: string;
  life_area?: string;
  block_type?: BlockType;
}

export interface Priority {
  title: string;
  description?: string;
  life_area?: string;
  why?: string;
}

export interface DailyPlan {
  id: string;
  user_id: string;
  checkin_id?: string;
  plan_date: string;
  status_summary?: string;
  day_mode?: string;
  main_win?: string;
  top_priorities: Priority[];
  time_blocks: TimeBlock[];
  energy_strategy?: string;
  not_today_list: string[];
  evening_review_questions: string[];
  motivational_closing?: string;
  model_used?: string;
  generated_at?: string;
  created_at: string;
  review_context_used?: boolean;
}

// ─── Evening Review ────────────────────────────────────────────────────────────
export interface ReviewCreate {
  user_id?: string;
  plan_id?: string;
  review_date?: string;
  completed_items: string[];
  missed_items: string[];
  energy_end?: number;
  biggest_win?: string;
  lessons?: string;
  carry_over_to_tomorrow: string[];
  raw_reflection?: string;
  overall_day_rating?: number;
}

export interface EveningReview extends ReviewCreate {
  id: string;
  created_at: string;
}

// ─── User Rules ────────────────────────────────────────────────────────────────
export interface RuleCreate {
  user_id?: string;
  title: string;
  rule_text: string;
  category?: string;
  life_area_id?: string;
  is_active: boolean;
  priority: number;
}

export interface UserRule extends RuleCreate {
  id: string;
  created_at: string;
  updated_at: string;
}

// ─── Rule update (partial, excludes user_id) ──────────────────────────────────
export interface RuleUpdate {
  title?: string;
  rule_text?: string;
  category?: string;
  life_area_id?: string;
  is_active?: boolean;
  priority?: number;
}

// ─── API responses ─────────────────────────────────────────────────────────────
export interface ApiError {
  detail: string;
}

export type GeneratePlanRequest = {
  checkin_id: string;
  user_id?: string;
  language?: "de" | "en";
};
