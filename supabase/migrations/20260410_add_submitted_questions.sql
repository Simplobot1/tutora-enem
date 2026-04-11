CREATE TABLE IF NOT EXISTS public.submitted_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES public.study_sessions(id) ON DELETE SET NULL,
    telegram_id BIGINT REFERENCES public.bot_users(telegram_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    alternatives JSONB NOT NULL DEFAULT '[]'::jsonb,
    correct_alternative CHAR(1),
    explanation TEXT,
    subject TEXT,
    topic TEXT,
    source_truth TEXT,
    answered_correct BOOLEAN,
    final_error_type TEXT,
    retry_attempts INTEGER NOT NULL DEFAULT 0,
    sent_to_anki BOOLEAN NOT NULL DEFAULT FALSE,
    apkg_generated BOOLEAN NOT NULL DEFAULT FALSE,
    apkg_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS submitted_questions_telegram_id_idx
ON public.submitted_questions (telegram_id);

CREATE INDEX IF NOT EXISTS submitted_questions_answered_correct_idx
ON public.submitted_questions (answered_correct);

CREATE INDEX IF NOT EXISTS submitted_questions_sent_to_anki_idx
ON public.submitted_questions (sent_to_anki);

ALTER TABLE public.submitted_questions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on submitted_questions" ON public.submitted_questions
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE TRIGGER submitted_questions_updated_at
BEFORE UPDATE ON public.submitted_questions
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
