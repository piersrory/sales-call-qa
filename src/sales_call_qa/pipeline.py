"""What happens to each call that arrives: store it, assess it, record the outcome."""

import os

import psycopg
from psycopg.types.json import Jsonb

import logging

import anthropic
import httpx

from sales_call_qa.assess import assess, format_transcript, redacted_turns
from sales_call_qa.schemas import Call, AssessmentRecord
from sales_call_qa.vapi import call_from_vapi
from sales_call_qa.alerts import alert

log = logging.getLogger(__name__)


# The local Docker database by default; a deployed server sets DATABASE_URL instead
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/postgres"
)


def save_raw(conn: psycopg.Connection, call_id: str, payload: dict) -> bool:
    """Store the payload untouched. Returns False if this call was already received,
    so a repeated delivery changes nothing."""
    cursor = conn.execute(
        "INSERT INTO raw_events (call_id, payload) VALUES (%s, %s) ON CONFLICT (call_id) DO NOTHING",
        (call_id, Jsonb(payload)),
    )
    return cursor.rowcount == 1


def save_call(conn: psycopg.Connection, call: Call) -> None:
    """One cleaned row per call. Only the redacted transcript is stored."""
    conn.execute(
        "INSERT INTO calls (call_id, market, agent_id, started_at, transcript)"
        " VALUES (%s, %s, %s, %s, %s) ON CONFLICT (call_id) DO NOTHING",
        (
            call.call_id,
            call.market,
            call.agent_id,
            call.started_at,
            format_transcript(redacted_turns(call)),
        ),
    )


# The best set-up from the evaluation: Haiku with prompt v2 (100% recall, 83% precision)
MODEL = "claude-haiku-5-5"


def save_assessment(conn: psycopg.Connection, record: AssessmentRecord) -> None:
    """One assessment_runs row (model, tokens, time) and one assessments row per rubric item."""
    conn.execute(
        "INSERT INTO assessment_runs (call_id, model, prompt_version, input_tokens, output_tokens, seconds)"
        " VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (
            record.call_id,
            record.model,
            record.prompt_version,
            record.input_tokens,
            record.output_tokens,
            record.seconds,
        ),
    )
    with conn.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO assessments (call_id, model, prompt_version, criterion, verdict, evidence, evidence_verified)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            [
                (
                    record.call_id,
                    record.model,
                    record.prompt_version,
                    v.criterion,
                    v.verdict,
                    v.evidence,
                    v.evidence_verified,
                )
                for v in record.verdicts
            ],
        )


def store(payload: dict) -> Call | None:
    """Save a newly arrived call. Returns None if it had already arrived."""
    call = call_from_vapi(payload)
    with psycopg.connect(DATABASE_URL) as conn:  # commits when the block ends
        if not save_raw(conn, call.call_id, payload):
            return None
        save_call(conn, call)
    return call


def set_status(
    conn: psycopg.Connection, call_id: str, status: str, error: str | None = None
) -> None:
    conn.execute(
        "UPDATE raw_events SET status = %s, error = %s WHERE call_id = %s",
        (status, error, call_id),
    )


async def process_call(payload: dict) -> None:
    """Everything that happens to an arriving call. Runs after the webhook has replied,
    so every outcome is recorded in raw_events.status: nobody is watching to see an error."""
    call = store(payload)
    if call is None:
        log.info("Already received, skipping")
        return
    try:
        async with anthropic.AsyncAnthropic(max_retries=5) as client:
            record = await assess(client, call, MODEL)
        if record is None:
            raise RuntimeError("Claude didn't return a usable assessment")
        with psycopg.connect(DATABASE_URL) as conn:
            save_assessment(conn, record)
            set_status(conn, call.call_id, "assessed")
        log.info("%s: assessed", call.call_id)
    except (
        Exception
    ) as e:  # any failure must be recorded, or the call looks stuck forever
        log.exception("%s: assessment failed", call.call_id)
        with psycopg.connect(DATABASE_URL) as conn:
            set_status(conn, call.call_id, "failed", str(e))
        return
    # Outside the try above: the assessment is already saved, so a Slack outage
    # must not mark it failed
    try:
        await alert(record)
    except httpx.HTTPError:
        log.exception("%s: Slack alert failed", call.call_id)
