ALTER TABLE public.submitted_questions
  ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'text',
  ADD COLUMN IF NOT EXISTS ocr_raw_text TEXT,
  ADD COLUMN IF NOT EXISTS ocr_confidence FLOAT;

CREATE INDEX IF NOT EXISTS submitted_questions_source_idx
ON public.submitted_questions (source);
