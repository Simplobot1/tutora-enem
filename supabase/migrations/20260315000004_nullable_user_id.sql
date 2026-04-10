-- Migration: make user_id nullable in bot-used tables
-- Bot identifies users by telegram_id, not Supabase auth UUID

ALTER TABLE public.study_sessions ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE public.answers ALTER COLUMN user_id DROP NOT NULL;
