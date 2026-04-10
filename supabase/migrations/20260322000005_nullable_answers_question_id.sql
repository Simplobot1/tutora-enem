-- Allow multimodal fallback answers to be persisted without promoting ad hoc
-- content into public.questions before normalization/provenance are reliable.

ALTER TABLE public.answers
ALTER COLUMN question_id DROP NOT NULL;
