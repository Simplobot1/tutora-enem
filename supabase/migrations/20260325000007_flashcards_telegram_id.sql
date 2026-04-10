-- Allow bot-originated Anki decks to be owned by telegram_id without requiring auth.users.

ALTER TABLE public.flashcards
ALTER COLUMN user_id DROP NOT NULL;

ALTER TABLE public.flashcards
ADD COLUMN IF NOT EXISTS telegram_id BIGINT REFERENCES public.bot_users(telegram_id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS flashcards_telegram_id_idx
ON public.flashcards (telegram_id);
