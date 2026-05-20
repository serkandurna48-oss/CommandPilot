-- Migration: add review_context_used column to daily_plans
-- Safe for existing rows: ADD COLUMN IF NOT EXISTS with a default of false.
-- Idempotent: no-op if the column already exists.
--
-- Run this before deploying backend code that writes review_context_used.
-- Fresh installs from supabase/schema.sql already include this column.

alter table public.daily_plans
  add column if not exists review_context_used boolean default false;
