-- Migration: Add pessimistic locking support to study_sessions
-- Purpose: Implement FOR UPDATE mechanism to prevent race conditions in session updates
-- M2-S2: Pessimistic locking + race condition mitigation

-- Function: Get active session with pessimistic lock
CREATE OR REPLACE FUNCTION get_active_session_with_lock(
  p_telegram_id BIGINT,
  p_flow TEXT,
  p_lock_id UUID,
  p_lock_timestamp TIMESTAMP WITH TIME ZONE
)
RETURNS TABLE(
  id UUID,
  telegram_id BIGINT,
  type TEXT,
  status TEXT,
  metadata JSONB,
  started_at TIMESTAMP WITH TIME ZONE,
  finished_at TIMESTAMP WITH TIME ZONE,
  mood TEXT
) AS $$
DECLARE
  v_session_id UUID;
BEGIN
  -- Acquire lock on the session row
  SELECT ss.id INTO v_session_id
  FROM study_sessions ss
  WHERE ss.telegram_id = p_telegram_id
    AND ss.status = 'active'
    AND (ss.metadata->>'flow')::TEXT = p_flow
  ORDER BY ss.started_at DESC
  LIMIT 1
  FOR UPDATE;

  -- If session found, return it with lock metadata
  IF v_session_id IS NOT NULL THEN
    RETURN QUERY
    SELECT
      ss.id,
      ss.telegram_id,
      ss.type,
      ss.status,
      jsonb_set(
        jsonb_set(ss.metadata, '{pessimistic_lock_id}', to_jsonb(p_lock_id::TEXT)),
        '{lock_timestamp}',
        to_jsonb(p_lock_timestamp::TEXT)
      ) as metadata,
      ss.started_at,
      ss.finished_at,
      ss.mood
    FROM study_sessions ss
    WHERE ss.id = v_session_id;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Create index for faster active session lookups
CREATE INDEX IF NOT EXISTS idx_study_sessions_telegram_status
ON study_sessions(telegram_id, status)
WHERE status = 'active';

-- Grant permission to anon and authenticated roles
GRANT EXECUTE ON FUNCTION get_active_session_with_lock TO anon, authenticated;

-- Add comment for documentation
COMMENT ON FUNCTION get_active_session_with_lock IS
  'Acquires a pessimistic lock (FOR UPDATE) on the active session row and returns it with lock metadata.
   Used in M2-S2 to prevent race conditions during session updates.';
