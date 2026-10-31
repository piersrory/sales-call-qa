from sales_call_qa.generate_calls import MIN_TURNS, check_dialogue, make_plans
from sales_call_qa.markets import Market
from sales_call_qa.rubric import RUBRIC
from sales_call_qa.schemas import Dialogue, Speaker, Turn, Verdict

PLANS = make_plans(40, seed=7)
GOOD_TIMESTAMPS = [f"{s // 60:02d}:{s % 60:02d}" for s in range(0, MIN_TURNS * 15, 15)]


def dialogue(timestamps: list[str], first: Speaker = Speaker.AGENT) -> Dialogue:
    other = Speaker.CUSTOMER if first == Speaker.AGENT else Speaker.AGENT
    return Dialogue(turns=[
        Turn(timestamp=ts, speaker=(first, other)[i % 2], text="...")
        for i, ts in enumerate(timestamps)
    ])


def test_plans_are_reproducible():
    assert make_plans(40, seed=7) == PLANS


def test_a_bigger_run_extends_a_smaller_one():
    assert make_plans(5, seed=7) == PLANS[:5]


def test_every_criterion_has_enough_passes_and_fails_to_measure():
    for criterion in RUBRIC:
        verdicts = [plan.labels()[criterion.id] for plan in PLANS]
        assert verdicts.count(Verdict.FAIL) >= 3, criterion.id
        assert verdicts.count(Verdict.PASS) >= 3, criterion.id


def test_breaches_are_only_planted_where_the_criterion_applies():
    for plan in PLANS:
        for criterion in RUBRIC:
            if criterion.id in plan.breaches:
                assert criterion.applies(plan.market, plan.sold, plan.vulnerable)


def test_only_sold_policies_are_cancelled():
    assert all(plan.sold for plan in PLANS if plan.cancelled_in_cooling_off)


def test_markets_are_balanced():
    counts = [sum(plan.market == market for plan in PLANS) for market in Market]
    assert max(counts) - min(counts) <= 1


def test_check_dialogue_accepts_a_usable_call():
    assert check_dialogue(dialogue(GOOD_TIMESTAMPS)) == []


def test_check_dialogue_rejects_timestamps_going_backwards():
    assert "timestamps go backwards" in check_dialogue(dialogue(GOOD_TIMESTAMPS[::-1]))


def test_check_dialogue_rejects_the_customer_speaking_first():
    assert "the customer speaks first" in check_dialogue(dialogue(GOOD_TIMESTAMPS, first=Speaker.CUSTOMER))


def test_check_dialogue_rejects_malformed_timestamps():
    problems = check_dialogue(dialogue(["0:05", *GOOD_TIMESTAMPS[1:]]))
    assert any("mm:ss" in problem for problem in problems)
