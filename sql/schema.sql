-- Raw → cleaned → summary: raw_events keeps each VAPI payload untouched, calls is one
-- cleaned row per call, and the SQL in this folder builds the summaries.

CREATE TABLE raw_events (
    call_id     text PRIMARY KEY,
    payload     jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    status      text NOT NULL DEFAULT 'received',   -- received, assessed or failed
    error       text
);

CREATE TABLE calls (                                -- one row per call
    call_id    text PRIMARY KEY REFERENCES raw_events,
    market     text NOT NULL,
    agent_id   text,
    started_at timestamptz NOT NULL,
    transcript text NOT NULL                        -- redacted
);

CREATE TABLE assessment_runs (                      -- one row per call, model and prompt version
    call_id        text REFERENCES calls,
    model          text,
    prompt_version text,
    input_tokens   int,
    output_tokens  int,
    seconds        numeric,
    assessed_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (call_id, model, prompt_version)
);

CREATE TABLE assessments (                          -- one row per run and rubric item
    call_id           text,
    model             text,
    prompt_version    text,
    criterion         text,
    verdict           text NOT NULL CHECK (verdict IN ('pass', 'fail', 'n/a')),
    evidence          text,
    evidence_verified boolean,
    PRIMARY KEY (call_id, model, prompt_version, criterion),
    FOREIGN KEY (call_id, model, prompt_version) REFERENCES assessment_runs
);

CREATE TABLE sales (
    call_id                  text PRIMARY KEY,
    market                   text,
    agent_id                 text,
    product                  text,
    currency                 text,
    quoted_monthly_premium   numeric,
    sold                     boolean,
    cancelled_in_cooling_off boolean,
    started_at               timestamptz
);

CREATE TABLE fx_rates (currency text PRIMARY KEY, to_aud numeric NOT NULL);

CREATE TABLE reviews (
    call_id          text,
    criterion        text,
    reviewer_verdict text CHECK (reviewer_verdict IN ('pass', 'fail', 'n/a')),
    note             text,
    reviewed_at      timestamptz NOT NULL DEFAULT now()
);
