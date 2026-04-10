-- Migration: Add telegram_id to users and adjust for bot access
-- Bot uses service_role key (bypasses RLS), so no policy changes needed.

-- 1. Add telegram_id to users
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS telegram_id BIGINT UNIQUE,
  ADD COLUMN IF NOT EXISTS mood TEXT CHECK (mood IN ('animada', 'normal', 'cansada', 'ansiosa')),
  ADD COLUMN IF NOT EXISTS mood_updated_at TIMESTAMPTZ;

-- 2. Index for fast lookup by telegram_id
CREATE INDEX IF NOT EXISTS users_telegram_id_idx ON public.users(telegram_id);

-- 3. Allow upsert by telegram_id (needed for bot to auto-create users)
-- service_role bypasses RLS, but anon needs this for upsert
CREATE POLICY "Service role full access on users" ON public.users
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access on study_sessions" ON public.study_sessions
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access on answers" ON public.answers
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access on questions" ON public.questions
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access on flashcards" ON public.flashcards
  FOR ALL TO service_role USING (true) WITH CHECK (true);
