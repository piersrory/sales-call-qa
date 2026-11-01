from sales_call_qa.assess import (
    applicable_criteria,
    check_assessment,
    format_transcript,
    load_call,
    quote_found,
    redacted_turns,
    verify_evidence,
    with_market_rows,
)
from sales_call_qa.rubric import RUBRIC
from sales_call_qa.schemas import Assessment, ItemVerdict, Verdict


def model_answer(call) -> Assessment:
    """A stand-in for Claude's reply: a pass for every criterion it was asked about."""
    return Assessment(verdicts=[
        ItemVerdict(criterion=c.id, verdict=Verdict.PASS, evidence="...", timestamp="00:00", reason="...")
        for c in applicable_criteria(call.market)
    ])


def test_every_call_ends_up_with_one_row_per_criterion_in_rubric_order():
    for call_id in ["call-001", "call-002"]:  # AU, then UK
        call = load_call(call_id)
        verdicts = with_market_rows(call, verify_evidence(model_answer(call), redacted_turns(call)))
        assert [v.criterion for v in verdicts] == [c.id for c in RUBRIC]


def test_criteria_outside_the_market_are_filled_in_as_not_applicable():
    call = load_call("call-002")  # UK, where the general advice warning doesn't apply
    verdicts = {v.criterion: v for v in with_market_rows(call, verify_evidence(model_answer(call), redacted_turns(call)))}
    assert verdicts["general_advice_warning"].verdict == Verdict.NOT_APPLICABLE
    assert "UK" in verdicts["general_advice_warning"].reason
    assert verdicts["general_advice_warning"].evidence_verified is None  # nothing to check


CALL = load_call("call-001")
TURNS = redacted_turns(CALL)
QUOTE = "just letting you know this call is recorded"  # said by the agent at 00:00


def honest_answer() -> Assessment:
    """Every criterion asked about, each quoting real words with the right timestamp."""
    return Assessment(verdicts=[
        ItemVerdict(criterion=c.id, verdict=Verdict.PASS, evidence=QUOTE, timestamp="00:00", reason="...")
        for c in applicable_criteria(CALL.market)
    ])


def test_an_honest_answer_has_no_problems():
    assert check_assessment(CALL, honest_answer()) == []


def test_a_missing_criterion_is_caught():
    answer = honest_answer()
    answer.verdicts.pop()
    assert any("missing" in p for p in check_assessment(CALL, answer))


def test_a_repeated_criterion_is_caught():
    answer = honest_answer()
    answer.verdicts.append(answer.verdicts[0])
    assert any("more than one" in p for p in check_assessment(CALL, answer))


TRANSCRIPT = format_transcript(TURNS)


def test_an_invented_quote_fails_the_check():
    assert not quote_found("this call is not being recorded", TRANSCRIPT)


def test_a_real_quote_passes_the_check():
    assert quote_found(QUOTE, TRANSCRIPT)


def test_formatting_around_a_real_quote_is_forgiven():
    for quote in [
        f'"{QUOTE}"',                  # wrapped in quotation marks
        f"[00:00] Agent: {QUOTE}",     # with the transcript's prefix
        QUOTE.upper(),                 # different case
        QUOTE.replace(" ", "   "),     # extra spaces
    ]:
        assert quote_found(quote, TRANSCRIPT), quote


def test_curly_quotes_match_straight_ones():
    assert quote_found("we’ll keep it straight", "Agent: We'll keep it straight.")


def test_an_empty_quote_is_not_found():
    assert not quote_found("", TRANSCRIPT)


def test_an_invented_quote_is_flagged_not_dropped():
    answer = honest_answer()
    answer.verdicts[0].evidence = "this call is not being recorded"
    verdicts = verify_evidence(answer, TURNS)
    assert len(verdicts) == len(answer.verdicts)  # kept, so it's counted and reviewed
    assert verdicts[0].evidence_verified is False
    assert all(v.evidence_verified for v in verdicts[1:])
