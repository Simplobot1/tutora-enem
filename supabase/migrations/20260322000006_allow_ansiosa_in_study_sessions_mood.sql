-- Align study_sessions.mood with bot_users.mood and story 0.2.

ALTER TABLE public.study_sessions
DROP CONSTRAINT IF EXISTS study_sessions_mood_check;

ALTER TABLE public.study_sessions
ADD CONSTRAINT study_sessions_mood_check
CHECK (mood IS NULL OR mood IN ('animada', 'normal', 'cansada', 'ansiosa'));
