"""Send the test calls through the webhook in VAPI's format, the same path a live call takes.

uv run uvicorn sales_call_qa.api:app --port 8001     # in one terminal
uv run python -m sales_call_qa.replay                 # in another
"""

import os

import httpx
from dotenv import load_dotenv

from sales_call_qa.assess import load_call
from sales_call_qa.generate_calls import REPO_ROOT
from sales_call_qa.schemas import Call, Speaker

URL = "http://127.0.0.1:8001/webhooks/vapi"
ROLES = {Speaker.AGENT: "bot", Speaker.CUSTOMER: "user"}


def seconds(timestamp: str) -> int:
    minutes, secs = timestamp.split(":")
    return int(minutes) * 60 + int(secs)


def vapi_payload(call: Call) -> dict:
    """The fields of an end-of-call report that call_from_vapi reads. The market, agent and
    customer go in the call's metadata, since a test call isn't from the AU voice agent."""
    return {
        "message": {
            "type": "end-of-call-report",
            "startedAt": call.started_at.isoformat(),
            "call": {
                "id": call.call_id,
                "metadata": {
                    "call_id": call.call_id,
                    "market": call.market,
                    "agent_id": call.agent_id,
                    "agent_name": call.agent_name,
                    "customer_name": call.customer_name,
                },
            },
            "artifact": {
                "messages": [
                    {
                        "role": ROLES[t.speaker],
                        "message": t.text,
                        "secondsFromStart": seconds(t.timestamp),
                    }
                    for t in call.turns
                ]
            },
        }
    }


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    headers = {"Authorization": f"Bearer {os.environ['VAPI_WEBHOOK_SECRET']}"}
    call_ids = sorted(p.stem for p in (REPO_ROOT / "data" / "calls").glob("*.json"))
    with httpx.Client(timeout=30) as client:
        for call_id in call_ids:
            response = client.post(
                URL, json=vapi_payload(load_call(call_id)), headers=headers
            )
            print(call_id, response.status_code)


if __name__ == "__main__":
    main()
