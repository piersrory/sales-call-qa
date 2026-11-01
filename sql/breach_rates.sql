-- Breach rate by market and week, with a rolling 4-week average.
-- One run only: the set-up the evaluation chose (Haiku, prompt v2).

WITH per_call AS (
    SELECT c.call_id,
           c.market,
           date_trunc('week', c.started_at) AS week,
           bool_or(a.verdict = 'fail')      AS has_breach
    FROM calls c
    JOIN assessments a USING (call_id)
    WHERE a.model = 'claude-haiku-5-5' AND a.prompt_version = 'v2'
    GROUP BY c.call_id, c.market, week
),
weekly AS (
    SELECT market, week, count(*) AS calls, avg(has_breach::int) AS breach_rate
    FROM per_call
    GROUP BY market, week
)
SELECT market, week, calls,
       round(breach_rate, 2) AS breach_rate,
       round(avg(breach_rate) OVER (
           PARTITION BY market ORDER BY week
           ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 2) AS rolling_4_weeks
FROM weekly
ORDER BY market, week;