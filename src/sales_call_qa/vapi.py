"""Turn VAPI's end-of-call report into the Call the assessor understands."""

from datetime import datetime

from sales_call_qa.markets import PRODUCTS, Market
from sales_call_qa.schemas import Call, Speaker, Turn

# Who said it. Other roles (the system prompt, tool calls) aren't part of the conversation.
SPEAKERS = {"bot": Speaker.AGENT, "user": Speaker.CUSTOMER}


def mmss(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60:02d}:{whole % 60:02d}"


def call_from_vapi(payload: dict) -> Call:
    message = payload["message"]
    # Live calls come from the AU voice agent. Replayed test calls say which market,
    # agent and customer they're from in the call's metadata.
    meta = message["call"].get("metadata") or {}
    market = Market(meta.get("market", "AU"))
    return Call(
        call_id=meta.get("call_id", message["call"]["id"]),
        market=market,
        agent_id=meta.get("agent_id", "vapi"),
        agent_name=meta.get("agent_name", "Sam"),
        customer_name=meta.get("customer_name", ""),  # unknown on a live call
        product=PRODUCTS[market].name,
        started_at=datetime.fromisoformat(message["startedAt"]),
        turns=[
            Turn(
                timestamp=mmss(m["secondsFromStart"]),
                speaker=SPEAKERS[m["role"]],
                text=m["message"],
            )
            for m in message["artifact"]["messages"]
            if m["role"] in SPEAKERS
        ],
    )
