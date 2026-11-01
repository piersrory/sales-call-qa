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


class AssessmentRecord(BaseModel):
    """What gets saved for each assessed call: the verdicts plus how they were produced,
    so runs with different models or prompt versions can be compared on accuracy and cost."""

    call_id: str
    model: str  # the model that answered, which can differ from the one asked if it fell back
    prompt_version: str
    input_tokens: int
    output_tokens: int
    seconds: float
    verdicts: list[ItemVerdict]  # one per rubric criterion, in rubric order
