-- Agents ranked by breach rate within their own market (1 = most breaches).
WITH per_call AS (
    SELECT c.call_id, c.market, c.agent_id, bool_or(a.verdict = 'fail') AS has_breach
    FROM calls c
    JOIN assessments a USING (call_id)
    WHERE a.model = 'claude-haiku-5-5' AND a.prompt_version = 'v2'
      AND c.agent_id <> 'vapi'  -- the voice agent's demo calls aren't a sales agent
    GROUP BY c.call_id, c.market, c.agent_id
)
SELECT market, agent_id, count(*) AS calls,
       round(avg(has_breach::int), 2) AS breach_rate,
       rank() OVER (PARTITION BY market ORDER BY avg(has_breach::int) DESC) AS rank_in_market
FROM per_call
GROUP BY market, agent_id
ORDER BY market, rank_in_market;
