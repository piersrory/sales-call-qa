from sales_call_qa.alerts import breach_message
from sales_call_qa.schemas import AssessmentRecord, CheckedVerdict, Verdict


def record(*verdicts: CheckedVerdict) -> AssessmentRecord:
    return AssessmentRecord(
        call_id="call-001", model="claude-haiku-5-5", prompt_version="v2",
        input_tokens=0, output_tokens=0, seconds=0, verdicts=list(verdicts),
    )


def verdict(criterion: str, result: Verdict, verified: bool | None = True) -> CheckedVerdict:
    return CheckedVerdict(
        criterion=criterion, verdict=result, evidence=f"words for {criterion}",
        timestamp="00:10", reason=f"reason for {criterion}", evidence_verified=verified,
    )


def test_a_clean_call_sends_nothing():
    assert breach_message(record(verdict("recording_disclosure", Verdict.PASS))) is None


def test_every_breach_goes_in_one_message_with_its_evidence():
    message = breach_message(record(
        verdict("recording_disclosure", Verdict.FAIL),
        verdict("identity_check", Verdict.PASS),
        verdict("no_pressure_selling", Verdict.FAIL),
    ))
    assert "call-001" in message
    assert "words for recording_disclosure" in message and "words for no_pressure_selling" in message
    assert "identity_check" not in message


def test_an_unverified_quote_is_marked_in_the_alert():
    message = breach_message(record(verdict("recording_disclosure", Verdict.FAIL, verified=False)))
    assert "quote not found in the transcript" in message
