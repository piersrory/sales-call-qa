-- Do policies sold on a call with a breach get cancelled in the cooling-off period more often?
-- The pattern is planted in the fake data: this shows the question to ask of real data, not a finding.
WITH per_call AS (
    SELECT call_id, bool_or(verdict = 'fail') AS has_breach
    FROM assessments
    WHERE model = 'claude-haiku-5-5' AND prompt_version = 'v2'
    GROUP BY call_id
)
SELECT p.has_breach,
       count(*)                                      AS policies_sold,
       round(avg(s.cancelled_in_cooling_off::int), 2) AS cancellation_rate
FROM per_call p
JOIN sales s USING (call_id)
WHERE s.sold
GROUP BY p.has_breach;
