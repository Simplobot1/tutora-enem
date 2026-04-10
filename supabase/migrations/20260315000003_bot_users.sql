-- Migration: Standalone bot_users table for Telegram bot
-- Avoids dependency on auth.users (which requires Supabase Auth flow)

CREATE TABLE public.bot_users (
    telegram_id BIGINT PRIMARY KEY,
    first_name  TEXT,
    username    TEXT,
    mood        TEXT CHECK (mood IN ('animada', 'normal', 'cansada', 'ansiosa')),
    mood_updated_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Add telegram_id to study_sessions and answers (replaces user_id for bot flows)
ALTER TABLE public.study_sessions
    ADD COLUMN IF NOT EXISTS telegram_id BIGINT REFERENCES public.bot_users(telegram_id) ON DELETE CASCADE;

ALTER TABLE public.answers
    ADD COLUMN IF NOT EXISTS telegram_id BIGINT REFERENCES public.bot_users(telegram_id) ON DELETE CASCADE;

-- Indexes
CREATE INDEX IF NOT EXISTS study_sessions_telegram_id_idx ON public.study_sessions(telegram_id);
CREATE INDEX IF NOT EXISTS answers_telegram_id_idx        ON public.answers(telegram_id);

-- RLS: service_role bypasses, so only need to enable
ALTER TABLE public.bot_users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on bot_users" ON public.bot_users
    FOR ALL TO service_role USING (true) WITH CHECK (true);
