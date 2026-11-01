-- Data checks: each query should return no rows. Any row returned is a problem to look at.

-- Every assessment run has a verdict for all 8 rubric items
SELECT call_id, model, prompt_version, count(*) AS items
FROM assessments
GROUP BY call_id, model, prompt_version
HAVING count(*) <> 8;

-- No call is missing its market or start time
SELECT call_id FROM calls WHERE market IS NULL OR started_at IS NULL;

-- Every sale has a matching call
SELECT s.call_id FROM sales s LEFT JOIN calls c USING (call_id) WHERE c.call_id IS NULL;

-- No call is stuck without an assessment (received but never finished, or failed)
SELECT call_id, status, received_at FROM raw_events WHERE status <> 'assessed';
