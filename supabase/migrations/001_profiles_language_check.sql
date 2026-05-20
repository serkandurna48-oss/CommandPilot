-- Migration: add CHECK constraint to profiles.language
-- Safe for existing data: normalises null/invalid values to 'en' first.
-- Idempotent: skips the ALTER TABLE if the constraint already exists.

-- 1. Normalise any null or unrecognised language values to 'en'.
update public.profiles
set language = 'en'
where language is null
   or language not in ('en', 'de');

-- 2. Add the CHECK constraint only if it does not already exist.
do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'profiles_language_check'
  ) then
    alter table public.profiles
      add constraint profiles_language_check
      check (language in ('en', 'de'));
  end if;
end $$;
