-- Enable Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. Users Profile (Linked to auth.users)
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT,
    avatar_url TEXT,
    preferences JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Materials (NotebookLM Ingestion)
CREATE TABLE public.materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT,
    type TEXT CHECK (type IN ('pdf', 'audio', 'text', 'flashcard_set')),
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding VECTOR(1536), -- Standard size for OpenAI embeddings
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Questions (ENEM Database)
CREATE TABLE public.questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    alternatives JSONB NOT NULL, -- Format: [{"label": "A", "text": "..."}, ...]
    correct_alternative CHAR(1) NOT NULL,
    explanation TEXT,
    subject TEXT, -- e.g., 'Ciências da Natureza'
    topic TEXT,   -- e.g., 'Genética'
    year INTEGER,
    source TEXT DEFAULT 'ENEM',
    difficulty TEXT CHECK (difficulty IN ('easy', 'medium', 'hard')),
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Study Sessions
CREATE TABLE public.study_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
    type TEXT CHECK (type IN ('quiz', 'review', 'socratic_drill')),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 5. Answers (User Interactions)
CREATE TABLE public.answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
    question_id UUID REFERENCES public.questions(id) ON DELETE CASCADE NOT NULL,
    session_id UUID REFERENCES public.study_sessions(id) ON DELETE SET NULL,
    selected_alternative CHAR(1),
    is_correct BOOLEAN NOT NULL,
    error_type TEXT, -- Socratic classification (e.g., 'Conceptual', 'Interpretation', 'Calculation')
    feedback_received TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Flashcards (Anki integration)
CREATE TABLE public.flashcards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
    question_id UUID REFERENCES public.questions(id) ON DELETE SET NULL, -- Optional link to original mistake
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    ease_factor FLOAT DEFAULT 2.5,
    interval INTEGER DEFAULT 0,
    next_review_at TIMESTAMPTZ DEFAULT NOW(),
    last_reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. View: Performance by Topic
CREATE OR REPLACE VIEW public.performance_by_topic AS
SELECT 
    u.id as user_id,
    q.subject,
    q.topic,
    COUNT(a.id) as total_attempts,
    COUNT(a.id) FILTER (WHERE a.is_correct) as correct_answers,
    ROUND(
        (COUNT(a.id) FILTER (WHERE a.is_correct)::DECIMAL / NULLIF(COUNT(a.id), 0)) * 100, 
        2
    ) as accuracy_percentage,
    MODE() WITHIN GROUP (ORDER BY a.error_type) as most_common_error
FROM public.users u
JOIN public.answers a ON u.id = a.user_id
JOIN public.questions q ON a.question_id = q.id
GROUP BY u.id, q.subject, q.topic;

-- 8. Row Level Security (RLS)
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.materials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.study_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flashcards ENABLE ROW LEVEL SECURITY;

-- Policies
-- Users: Can only read/update their own profile
CREATE POLICY "Users can manage their own profile" ON public.users
    FOR ALL USING (auth.uid() = id);

-- Materials: Readable by all authenticated users
CREATE POLICY "Materials are readable by authenticated users" ON public.materials
    FOR SELECT USING (auth.role() = 'authenticated');

-- Questions: Readable by all authenticated users
CREATE POLICY "Questions are readable by authenticated users" ON public.questions
    FOR SELECT USING (auth.role() = 'authenticated');

-- Study Sessions: Private to the owner
CREATE POLICY "Users can manage their own sessions" ON public.study_sessions
    FOR ALL USING (auth.uid() = user_id);

-- Answers: Private to the owner
CREATE POLICY "Users can manage their own answers" ON public.answers
    FOR ALL USING (auth.uid() = user_id);

-- Flashcards: Private to the owner
CREATE POLICY "Users can manage their own flashcards" ON public.flashcards
    FOR ALL USING (auth.uid() = user_id);

-- 9. Automatic Updated At Trigger
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at BEFORE UPDATE ON public.users
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
