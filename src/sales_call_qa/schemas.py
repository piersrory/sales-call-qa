"""Data shapes shared by the generator and, later, the assessor."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from sales_call_qa.markets import Market


class Speaker(StrEnum):
    AGENT = "Agent"
    CUSTOMER = "Customer"


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "n/a"


class Turn(BaseModel):
    timestamp: str = Field(description="Time since the call started, as mm:ss")
    speaker: Speaker
    text: str


class Dialogue(BaseModel):
    """What Claude writes: only the turns of the call."""

    turns: list[Turn]


class Call(BaseModel):
    """One call as a phone system would hand it over: metadata and turns, no labels."""

    call_id: str
    market: Market
    agent_id: str
    agent_name: str
    customer_name: str
    product: str
    started_at: datetime
    turns: list[Turn]

    def transcript(self) -> str:
        return "\n".join(f"[{t.timestamp}] {t.speaker}: {t.text}" for t in self.turns)


class ItemVerdict(BaseModel):
    criterion: str  # rubric item id, e.g. "recording_disclosure"
    verdict: Verdict  # pass, fail or n/a
    evidence: str  # exact words from the transcript
    timestamp: str  # mm:ss of the evidence
    reason: str  # one sentence


class Assessment(BaseModel):
    verdicts: list[ItemVerdict]
