"""Generate fake sales calls with compliance breaches planted on purpose.

Each call's plan (market, outcome, which rules the agent breaks) is decided in code from
a fixed seed before Claude writes a word, so the answer key is known in advance. Claude
only writes the dialogue.

    uv run generate-calls --dry-run    # print the plans, no API calls
    uv run generate-calls              # write data/calls/*.json, labels.csv and sales.csv

Re-running skips calls that already exist, so an interrupted run picks up where it stopped.
"""

import argparse
import asyncio
import csv
import logging
import random
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
import pydantic
from dotenv import load_dotenv

from sales_call_qa.markets import PRODUCTS, TIMEZONES, Market, Product
from sales_call_qa.rubric import RUBRIC
from sales_call_qa.schemas import Call, Dialogue, Speaker, Verdict

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "claude-opus-5-5"
LAST_CALL_DAY = date(2026, 10, 30)  # calls are spread over the 4 weeks up to this day
MIN_TURNS = 16
MAX_ATTEMPTS = 3
TIMESTAMP = re.compile(r"^\d{2}:[0-5]\d$")

AGENTS = {
    Market.AU: ("Mia", "Jack", "Priya"),
    Market.UK: ("Oliver", "Amelia", "Hassan"),
    Market.CA: ("Ethan", "Chloé", "Arjun"),
    Market.NZ: ("Aroha", "Sam", "Ravi"),
}
CUSTOMERS = {
    Market.AU: ("Sarah Nguyen", "Liam O'Brien", "Chloe Patel", "Tom Wilson",
                "Grace Chen", "Daniel Kelly", "Emma Rossi", "Josh Taylor"),
    Market.UK: ("James Walker", "Sophie Clarke", "Mohammed Ali", "Hannah Evans",
                "Callum Reid", "Emily Shah", "Isla Morgan", "Ryan Hughes"),
    Market.CA: ("Liam Tremblay", "Olivia Roy", "Noah Gagnon", "Emma Wong",
                "Lucas Singh", "Ava MacDonald", "Benjamin Côté", "Sophia Bouchard"),
    Market.NZ: ("Hemi Walker", "Charlotte Smith", "Ana Fifita", "Oliver Brown",
                "Mereana Ngata", "Jack Wilson", "Isla Taylor", "Wiremu Parata"),
}
# (who the customer is, whether they show signs of vulnerability)
PERSONAS = (
    ("a nurse in their thirties with two young children, taking the call on a break", False),
    ("a recently retired teacher who wants to leave something for the grandchildren", False),
    ("a self-employed electrician who is wary of salespeople and asks pointed questions", False),
    ("a first-time home buyer who has just taken out a mortgage", False),
    ("a busy small-business owner who keeps trying to speed the call up", False),
    ("someone in their fifties who was recently diagnosed with high blood pressure", False),
    ("someone in their seventies whose partner died two months ago, who gets muddled by the numbers", True),
    ("someone who has just lost their job and mentions that money is very tight", True),
    ("someone recovering from a stroke who often asks for things to be repeated", True),
)

SYSTEM_PROMPT = """You write realistic transcripts of sales calls. Each transcript is test \
data for an automated compliance checker, so it must follow its brief exactly.

- Everything under "The agent does correctly" must clearly happen in the call.
- Everything under "Breaches to plant" must also clearly happen, but naturally, the way a \
rushed or pushy agent really would. Don't exaggerate it, and don't let anyone point it out.
- Nothing else goes wrong: add no other compliance problems.
- Never mention compliance, rules or breaches.
- The customer called in after seeing an advert, or asked for a call back.
- The customer acts in character: they ask questions, hesitate and push back.
- When the agent checks identity, use realistic but invented personal details.
- Write 20 to 45 turns. Timestamps are mm:ss from the start of the call and always go up. \
The call lasts 4 to 9 minutes, and the agent speaks first."""


@dataclass(frozen=True)
class CallPlan:
    """Everything decided about a call before Claude writes it, including the answer key."""

    call_id: str
    market: Market
    agent_id: str
    agent_name: str
    customer_name: str
    persona: str
    vulnerable: bool
    sold: bool
    cancelled_in_cooling_off: bool
    monthly_premium: int
    started_at: datetime
    breaches: tuple[str, ...]

    @property
    def product(self) -> Product:
        return PRODUCTS[self.market]

    def labels(self) -> dict[str, Verdict]:
        """The verdict a perfect checker would give for each criterion."""
        labels = {}
        for criterion in RUBRIC:
            if not criterion.applies(self.market, self.sold, self.vulnerable):
                labels[criterion.id] = Verdict.NOT_APPLICABLE
            elif criterion.id in self.breaches:
                labels[criterion.id] = Verdict.FAIL
            else:
                labels[criterion.id] = Verdict.PASS
        return labels


def make_plans(n: int, seed: int) -> list[CallPlan]:
    """Plan n calls. Plan i never depends on n, so a bigger run extends a smaller one."""
    rng = random.Random(seed)
    breach_counts: Counter[str] = Counter()
    markets = list(Market)
    plans = []
    for i in range(n):
        market = markets[i % len(markets)]
        agent = rng.randrange(len(AGENTS[market]))
        persona, vulnerable = rng.choice(PERSONAS)
        sold = rng.random() < 0.6
        low, high = PRODUCTS[market].monthly_premium_range
        local_start = datetime.combine(
            LAST_CALL_DAY - timedelta(days=rng.randrange(28)),
            time(rng.randrange(9, 17), rng.randrange(60)),
            tzinfo=ZoneInfo(TIMEZONES[market]),
        )

        # 30% of calls are clean, 50% have one breach and 20% have two. Planting the
        # least-used breaches first gives every criterion enough failures to measure.
        n_breaches = rng.choices((0, 1, 2), weights=(3, 5, 2))[0]
        candidates = [c.id for c in RUBRIC if c.applies(market, sold, vulnerable)]
        rng.shuffle(candidates)
        candidates.sort(key=lambda criterion_id: breach_counts[criterion_id])
        breaches = tuple(sorted(candidates[:n_breaches]))
        breach_counts.update(breaches)

        # Badly sold policies are cancelled in the cooling-off period more often. This is
        # planted so the analytics has a pattern to find; with real data it's a question.
        cancelled = sold and rng.random() < (0.3 if breaches else 0.08)

        plans.append(
            CallPlan(
                call_id=f"call-{i + 1:03d}",
                market=market,
                agent_id=f"{market}-{agent + 1:02d}",
                agent_name=AGENTS[market][agent],
                customer_name=rng.choice(CUSTOMERS[market]),
                persona=persona,
                vulnerable=vulnerable,
                sold=sold,
                cancelled_in_cooling_off=cancelled,
                monthly_premium=rng.randint(low, high),
                started_at=local_start.astimezone(UTC),
                breaches=breaches,
            )
        )
    return plans


def brief(plan: CallPlan) -> str:
    """The user message for one call: who's talking, what happens and what goes wrong."""
    product = plan.product
    applicable = [c for c in RUBRIC if c.applies(plan.market, plan.sold, plan.vulnerable)]
    correct = [c.requirement for c in applicable if c.id not in plan.breaches]
    planted = [c.breach for c in applicable if c.id in plan.breaches]
    outcome = (
        f"The customer buys, at {plan.monthly_premium} {product.currency} a month."
        if plan.sold
        else "The customer decides not to buy on this call."
    )
    return "\n".join([
        f"Market: {plan.market} (use local spelling, phrasing and currency: {product.currency})",
        f"Product: {product.name}",
        "Product facts:",
        *[f"- {fact}" for fact in product.facts],
        f"Agent: {plan.agent_name}",
        f"Customer: {plan.customer_name}, {plan.persona}"
        + (". Make their vulnerability clear from what they say." if plan.vulnerable else ""),
        f"Outcome: {outcome}",
        "",
        "The agent does correctly:",
        *[f"- {requirement}" for requirement in correct],
        "",
        "Breaches to plant:",
        *([f"- {breach}" for breach in planted] or ["- None. This is a clean call."]),
    ])


def check_dialogue(dialogue: Dialogue) -> list[str]:
    """Problems that would make a transcript useless as test data. Empty means usable."""
    turns = dialogue.turns
    problems = []
    if len(turns) < MIN_TURNS:
        problems.append(f"only {len(turns)} turns, need at least {MIN_TURNS}")
    if turns and turns[0].speaker != Speaker.AGENT:
        problems.append("the customer speaks first")
    if {t.speaker for t in turns} != set(Speaker):
        problems.append("only one person speaks")
    bad = [t.timestamp for t in turns if not TIMESTAMP.match(t.timestamp)]
    if bad:
        problems.append(f"timestamps not in mm:ss form: {bad[:3]}")
    else:
        seconds = [int(t.timestamp[:2]) * 60 + int(t.timestamp[3:]) for t in turns]
        if seconds != sorted(seconds):
            problems.append("timestamps go backwards")
    return problems


def fallback_options(model: str) -> dict:
    """If Claude declines a request, re-run it server-side on the model Anthropic
    recommends for that case. Haiku has no server-side fallback, so it gets none."""
    if model.startswith("claude-haiku"):
        return {}
    return {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}


async def write_call(client: anthropic.AsyncAnthropic, plan: CallPlan, model: str) -> Call | None:
    """Ask Claude to write one call. Returns None if it can't produce a usable one."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.beta.messages.parse(
                model=model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": brief(plan)}],
                output_format=Dialogue,
                output_config={"effort": "medium"},
                **fallback_options(model),
            )
        except pydantic.ValidationError:
            log.warning("%s: attempt %d returned cut-off JSON, retrying", plan.call_id, attempt)
            continue
        except anthropic.APIStatusError as e:
            if e.status_code != 429 and e.status_code < 500:
                raise  # a bad request or key won't fix itself, so stop the whole run
            log.warning("%s: API error %s after the SDK's retries, skipping", plan.call_id, e.status_code)
            return None
        except anthropic.APIConnectionError:
            log.warning("%s: network error after the SDK's retries, skipping", plan.call_id)
            return None

        if response.stop_reason == "refusal":
            log.warning("%s: Claude declined to write this call, skipping", plan.call_id)
            return None
        dialogue = response.parsed_output
        if response.stop_reason == "max_tokens" or dialogue is None:
            log.warning("%s: attempt %d was cut off, retrying", plan.call_id, attempt)
            continue
        problems = check_dialogue(dialogue)
        if problems:
            log.warning("%s: attempt %d unusable (%s), retrying", plan.call_id, attempt, "; ".join(problems))
            continue
        return Call(
            call_id=plan.call_id,
            market=plan.market,
            agent_id=plan.agent_id,
            agent_name=plan.agent_name,
            customer_name=plan.customer_name,
            product=plan.product.name,
            started_at=plan.started_at,
            turns=dialogue.turns,
        )
    log.error("%s: no usable transcript after %d attempts", plan.call_id, MAX_ATTEMPTS)
    return None


async def generate(plans: list[CallPlan], model: str, concurrency: int, calls_dir: Path) -> None:
    calls_dir.mkdir(parents=True, exist_ok=True)
    todo = [p for p in plans if not (calls_dir / f"{p.call_id}.json").exists()]
    log.info("Writing %d calls with %s (%d already done)", len(todo), model, len(plans) - len(todo))
    limit = asyncio.Semaphore(concurrency)

    async with anthropic.AsyncAnthropic(max_retries=5) as client:

        async def write_and_save(plan: CallPlan) -> None:
            async with limit:
                call = await write_call(client, plan, model)
            if call:
                (calls_dir / f"{plan.call_id}.json").write_text(call.model_dump_json(indent=2))
                log.info("%s: written", plan.call_id)

        await asyncio.gather(*(write_and_save(p) for p in todo))


def write_answer_key(plans: list[CallPlan], out_dir: Path) -> None:
    """labels.csv (expected verdict per call and criterion) and sales.csv (the CRM side),
    for the calls that were actually written."""
    written = [p for p in plans if (out_dir / "calls" / f"{p.call_id}.json").exists()]
    with open(out_dir / "labels.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["call_id", "criterion", "expected"])
        for plan in written:
            for criterion_id, verdict in plan.labels().items():
                writer.writerow([plan.call_id, criterion_id, verdict])
    with open(out_dir / "sales.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["call_id", "market", "agent_id", "product", "currency",
                         "quoted_monthly_premium", "sold", "cancelled_in_cooling_off", "started_at"])
        for plan in written:
            writer.writerow([plan.call_id, plan.market, plan.agent_id, plan.product.name,
                             plan.product.currency, plan.monthly_premium, plan.sold,
                             plan.cancelled_in_cooling_off, plan.started_at.isoformat()])
    log.info("Wrote labels.csv and sales.csv for %d calls", len(written))


def summarise(plans: list[CallPlan]) -> str:
    markets = Counter(p.market for p in plans)
    lines = [
        f"{len(plans)} calls ({', '.join(f'{m} {n}' for m, n in markets.items())}), "
        f"{sum(p.sold for p in plans)} sold, "
        f"{sum(p.cancelled_in_cooling_off for p in plans)} cancelled in the cooling-off period",
        f"{'criterion':<24}{'fail':>6}{'pass':>6}{'n/a':>6}",
    ]
    for criterion in RUBRIC:
        counts = Counter(p.labels()[criterion.id] for p in plans)
        lines.append(
            f"{criterion.id:<24}{counts[Verdict.FAIL]:>6}{counts[Verdict.PASS]:>6}"
            f"{counts[Verdict.NOT_APPLICABLE]:>6}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=40, help="number of calls (default 40)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--concurrency", type=int, default=3, help="calls written in parallel")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--dry-run", action="store_true", help="print the plans without calling Claude")
    args = parser.parse_args()
    # Library loggers stay at WARNING; this script's own progress messages show at INFO
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    log.setLevel(logging.INFO)

    plans = make_plans(args.n, args.seed)
    print(summarise(plans))
    if args.dry_run:
        for p in plans:
            print(f"{p.call_id}  {p.market}  {'sold' if p.sold else 'not sold':<8}  {', '.join(p.breaches) or 'clean'}")
        return

    load_dotenv(REPO_ROOT / ".env")
    asyncio.run(generate(plans, args.model, args.concurrency, args.out / "calls"))
    write_answer_key(plans, args.out)


if __name__ == "__main__":
    main()
