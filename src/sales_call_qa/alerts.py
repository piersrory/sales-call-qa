"""Tell a person about a possible breach within seconds, in Slack."""

import os

import httpx

from sales_call_qa.schemas import AssessmentRecord, Verdict


def breach_message(record: AssessmentRecord) -> str | None:
    """One message per call listing every failed item with its evidence, or None if it's clean."""
    fails = [v for v in record.verdicts if v.verdict == Verdict.FAIL]
    if not fails:
        return None
    lines = [f"Possible breach on {record.call_id}:"]
    for v in fails:
        unchecked = (
            "" if v.evidence_verified else " _(quote not found in the transcript)_"
        )
        lines.append(
            f"• *{v.criterion}* at {v.timestamp}: {v.reason}\n> {v.evidence}{unchecked}"
        )
    return "\n".join(lines)


async def alert(record: AssessmentRecord) -> None:
    url = os.environ.get("SLACK_WEBHOOK_URL")
    message = breach_message(record)
    if not url or message is None:
        return  # no Slack set up, or nothing to report
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json={"text": message})
        response.raise_for_status()
