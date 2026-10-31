# Sales call QA

Automated compliance QA for sales calls. Claude checks each call against a rubric, every verdict quotes the transcript as evidence, and breaches are flagged for a person to review.

Work in progress.

## Setup

```bash
uv sync
cp .env.example .env          # add your ANTHROPIC_API_KEY
uv run pre-commit install     # gitleaks blocks any commit containing a secret (brew install gitleaks)
uv run pytest
```

## Test data

```bash
uv run generate-calls --dry-run   # print the plan for each call, no API calls
uv run generate-calls             # write 40 calls with Claude
```

This writes:

- `data/calls/*.json`: one fake life insurance sales call each, across AU, UK, CA and NZ
- `data/labels.csv`: the answer key, with the expected verdict for every call and criterion
- `data/sales.csv`: a CRM-style export (quoted premium, currency, sold, cancelled in the cooling-off period) to join against

Each call's plan (market, outcome, which rules the agent breaks) is decided in code from a fixed seed before Claude writes anything, so the answer key is known in advance. The data deliberately makes badly sold policies more likely to be cancelled in the cooling-off period, so the analytics has a pattern to find. The brand, [rubric](src/sales_call_qa/rubric.py) and [products](src/sales_call_qa/markets.py) are made up and illustrative, not legal advice.
