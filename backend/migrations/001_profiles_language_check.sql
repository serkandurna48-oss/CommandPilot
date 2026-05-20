-- Migration: add CHECK constraint to profiles.language
-- Safe for existing rows: sets any null/invalid language to 'en' before adding the constraint.
-- Idempotent: uses IF NOT EXISTS / DO NOTHING patterns where possible.

-- 1. Ensure the column exists with a default (safe if already present).
ALTER TABLE profiles
  ALTER COLUMN language SET DEFAULT 'en';

-- 2. Normalize any existing null or unknown values to 'en'.
UPDATE profiles
SET language = 'en'
WHERE language IS NULL
   OR language NOT IN ('en', 'de');

-- 3. Add the CHECK constraint (skip if already exists — Postgres 9.x+).
--    Supabase runs Postgres 15, so DO $$ blocks work fine.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'profiles_language_check'
      AND conrelid = 'profiles'::regclass
  ) THEN
    ALTER TABLE profiles
      ADD CONSTRAINT profiles_language_check
      CHECK (language IN ('en', 'de'));
  END IF;
END;
$$;
