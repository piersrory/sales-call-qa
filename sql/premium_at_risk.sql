-- Annual premium on policies sold during a call with at least one breach, in AUD.
-- Exchange rates are illustrative (see fx_rates); a real report would use dated rates.
SELECT s.market,
       count(*)                                                 AS policies,
       round(sum(s.quoted_monthly_premium * fx.to_aud * 12))    AS annual_premium_aud
FROM sales s
JOIN fx_rates fx USING (currency)
WHERE s.sold
  AND s.call_id IN (
      SELECT call_id FROM assessments
      WHERE verdict = 'fail'
        AND model = 'claude-haiku-5-5' AND prompt_version = 'v2')
GROUP BY s.market
ORDER BY annual_premium_aud DESC;
