-- ============================================================
-- Migration 017: Link Supabase Auth to public.users
-- Adds auth_id column so each public.users row links to
-- the corresponding auth.users (Supabase Auth) record.
-- Run in Supabase SQL editor BEFORE testing auth.
-- ============================================================

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS auth_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE;

-- Index for fast auth_id lookups (used on every page load)
CREATE INDEX IF NOT EXISTS idx_users_auth_id ON public.users(auth_id);

COMMENT ON COLUMN public.users.auth_id IS
'Links to Supabase Auth user (auth.users.id). Set when user is created via supabase.auth.signUp().';
