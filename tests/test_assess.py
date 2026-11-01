from sales_call_qa.assess import applicable_criteria, load_call, with_market_rows
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
        verdicts = with_market_rows(call, model_answer(call))
        assert [v.criterion for v in verdicts] == [c.id for c in RUBRIC]


def test_criteria_outside_the_market_are_filled_in_as_not_applicable():
    call = load_call("call-002")  # UK, where the general advice warning doesn't apply
    verdicts = {v.criterion: v for v in with_market_rows(call, model_answer(call))}
    assert verdicts["general_advice_warning"].verdict == Verdict.NOT_APPLICABLE
    assert "UK" in verdicts["general_advice_warning"].reason
