-- Fix missing fields required by the bot runtime and analytics.

ALTER TABLE public.study_sessions
ADD COLUMN IF NOT EXISTS mood TEXT
CHECK (mood IN ('cansada', 'normal', 'animada'));

ALTER TABLE public.questions
ADD COLUMN IF NOT EXISTS material_id UUID REFERENCES public.materials(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS number INTEGER,
ADD COLUMN IF NOT EXISTS enem_frequency_score NUMERIC(5,2);

ALTER TABLE public.answers
ADD COLUMN IF NOT EXISTS time_spent_seconds INTEGER
CHECK (time_spent_seconds IS NULL OR time_spent_seconds >= 0);

ALTER TABLE public.flashcards
ADD COLUMN IF NOT EXISTS anki_card_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_questions_material_id
ON public.questions (material_id);

CREATE INDEX IF NOT EXISTS idx_questions_enem_frequency_score_desc
ON public.questions (enem_frequency_score DESC NULLS LAST);

CREATE OR REPLACE VIEW public.performance_by_topic AS
WITH topic_attempts AS (
    SELECT
        a.user_id,
        q.subject,
        q.topic,
        a.id,
        a.is_correct,
        a.error_type,
        a.created_at
    FROM public.answers a
    JOIN public.questions q ON q.id = a.question_id
),
topic_rollup AS (
    SELECT
        user_id,
        subject,
        topic,
        COUNT(id) AS total_attempts,
        COUNT(id) FILTER (WHERE is_correct) AS correct_answers,
        ROUND(
            (
                COUNT(id) FILTER (WHERE is_correct)::NUMERIC
                / NULLIF(COUNT(id), 0)
            ) * 100,
            2
        ) AS accuracy_pct,
        MODE() WITHIN GROUP (ORDER BY error_type) AS dominant_error_type,
        MAX(created_at) AS last_studied_at
    FROM topic_attempts
    GROUP BY user_id, subject, topic
),
recent_window AS (
    SELECT
        user_id,
        subject,
        topic,
        ROUND(AVG(CASE WHEN is_correct THEN 100.0 ELSE 0.0 END), 2) AS recent_accuracy_pct
    FROM topic_attempts
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY user_id, subject, topic
),
previous_window AS (
    SELECT
        user_id,
        subject,
        topic,
        ROUND(AVG(CASE WHEN is_correct THEN 100.0 ELSE 0.0 END), 2) AS previous_accuracy_pct
    FROM topic_attempts
    WHERE created_at >= NOW() - INTERVAL '14 days'
      AND created_at < NOW() - INTERVAL '7 days'
    GROUP BY user_id, subject, topic
)
SELECT
    tr.user_id,
    tr.subject,
    tr.topic,
    tr.total_attempts,
    tr.correct_answers,
    tr.accuracy_pct,
    tr.accuracy_pct AS accuracy_percentage,
    tr.dominant_error_type,
    tr.dominant_error_type AS most_common_error,
    tr.last_studied_at,
    CASE
        WHEN rw.recent_accuracy_pct IS NULL AND pw.previous_accuracy_pct IS NULL THEN 'insufficient_data'
        WHEN rw.recent_accuracy_pct IS NULL OR pw.previous_accuracy_pct IS NULL THEN 'stable'
        WHEN rw.recent_accuracy_pct >= pw.previous_accuracy_pct + 5 THEN 'improving'
        WHEN rw.recent_accuracy_pct <= pw.previous_accuracy_pct - 5 THEN 'declining'
        ELSE 'stable'
    END AS trend
FROM topic_rollup tr
LEFT JOIN recent_window rw
    ON rw.user_id = tr.user_id
   AND rw.subject = tr.subject
   AND rw.topic = tr.topic
LEFT JOIN previous_window pw
    ON pw.user_id = tr.user_id
   AND pw.subject = tr.subject
   AND pw.topic = tr.topic;
